import json
import logging
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory

import config
from models.database import init_db
from models import repository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_UPLOAD_SIZE_MB * 1024 * 1024 * config.MAX_PHOTOS

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    return send_from_directory(str(config.BASE_DIR / 'templates'), 'index.html')


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(str(config.UPLOAD_FOLDER), filename)


@app.route('/api/health')
def health():
    from services.provider_registry import get_status
    return jsonify(get_status())


@app.route('/api/regions')
def get_regions():
    if not config.REGIONS_FILE.exists():
        from models.database import _ensure_regions
        _ensure_regions()
    if not config.REGIONS_FILE.exists():
        return jsonify([])
    try:
        data = json.loads(config.REGIONS_FILE.read_text(encoding='utf-8'))
        return jsonify([{'state_id': r['state_id'], 'name': r['name']} for r in data])
    except Exception as exc:
        logger.error('get_regions: %s', exc)
        return jsonify({'error': 'Не вдалося завантажити регіони'}), 500


@app.route('/api/cities/<int:state_id>')
def get_cities(state_id):
    if not config.REGIONS_FILE.exists():
        return jsonify([])
    try:
        data = json.loads(config.REGIONS_FILE.read_text(encoding='utf-8'))
        for region in data:
            if region['state_id'] == state_id:
                return jsonify(region.get('cities', []))
        return jsonify([])
    except Exception as exc:
        logger.error('get_cities(%d): %s', state_id, exc)
        return jsonify({'error': 'Помилка завантаження міст'}), 500


@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    errors = _validate_evaluate_request(request)
    if errors:
        return jsonify({'error': '; '.join(errors)}), 400

    photos = request.files.getlist('photos[]')
    if not photos or all(f.filename == '' for f in photos):
        return jsonify({'error': 'Необхідно завантажити хоча б одне фото'}), 400
    if len(photos) > config.MAX_PHOTOS:
        return jsonify({'error': f'Максимум {config.MAX_PHOTOS} фото'}), 400

    state_id = int(request.form['state_id'])
    city_id = int(request.form['city_id'])
    realty_type = request.form['realty_type']
    rooms_count = int(request.form['rooms_count'])
    floor = _int_or_none(request.form.get('floor'))
    total_floors = _int_or_none(request.form.get('total_floors'))
    year_built = _int_or_none(request.form.get('year_built'))
    user_area = _float_or_none(request.form.get('user_area'))
    user_description = request.form.get('user_description', '').strip()

    saved_paths = []
    photo_ids = []
    try:
        for photo in photos:
            if photo.filename == '':
                continue
            if not _allowed(photo.filename):
                return jsonify({'error': f'Непідтримуваний формат: {photo.filename}'}), 400
            uid = uuid.uuid4().hex + '.jpg'
            raw_path = config.UPLOAD_FOLDER / ('_raw_' + uid)
            final_path = config.UPLOAD_FOLDER / uid
            photo.save(str(raw_path))
            saved_paths.append(raw_path)
            photo_ids.append(uid)

            from services.vision_service import prepare_image
            prepare_image(raw_path, final_path)
            raw_path.unlink(missing_ok=True)

        final_paths = [config.UPLOAD_FOLDER / pid for pid in photo_ids]

        from services.vision_service import analyze_photos
        vision = analyze_photos(final_paths, user_description=user_description or None)

        if user_area and user_area > 0:
            final_area = user_area
            area_source = 'user'
        elif vision.get('estimated_area_midpoint'):
            final_area = round(vision['estimated_area_midpoint'], 1)
            area_source = 'estimated'
        else:
            final_area = _default_area(realty_type, rooms_count)
            area_source = 'estimated'

        from services.price_service import get_base_price
        price_info = get_base_price(state_id, city_id, realty_type, rooms_count)

        from services.rules_engine import calculate_price, CONDITION_LABELS
        price_result = calculate_price(
            base_price_per_m2=price_info['price_per_m2'],
            area=final_area,
            condition_score=vision['condition_score'],
            floor=floor,
            total_floors=total_floors,
            year_built=year_built,
            realty_type=realty_type,
            area_source=area_source,
        )

        state_name, city_name = _resolve_names(state_id, city_id)

        from services.provider_registry import decide_mode
        mode = decide_mode()
        use_llm = mode in ('full', 'full_with_cached_prices')

        explanation_data = {
            'city_name': city_name,
            'state_name': state_name,
            'realty_type': realty_type,
            'rooms_count': rooms_count,
            'final_area': final_area,
            'area_source': area_source,
            'floor': floor,
            'total_floors': total_floors,
            'year_built': year_built,
            'condition_score': vision['condition_score'],
            'condition_label': vision['condition_label'],
            'defects': vision.get('defects', []),
            'features': vision.get('features', []),
            'base_price_per_m2': price_info['price_per_m2'],
            'price_source': price_info['source'],
            'user_description': user_description,
            'coefficients': price_result['coefficients'],
            **price_result,
        }

        from services.explanation_service import generate
        explanation = generate(explanation_data, use_llm=use_llm)

        factors = []
        for d in vision.get('defects', []):
            factors.append({'type': 'negative', 'text': d})
        for f in vision.get('features', []):
            factors.append({'type': 'positive', 'text': f})

        evaluation = {
            'final_price': price_result['final_price'],
            'price_min': price_result['price_min'],
            'price_max': price_result['price_max'],
            'currency': 'USD',
            'final_area': final_area,
            'area_source': area_source,
            'condition_score': vision['condition_score'],
            'condition_label': vision['condition_label'],
            'base_price_per_m2': price_info['price_per_m2'],
            'price_source': price_info['source'],
            'price_sample_size': price_info.get('sample_size', 0),
            'coefficients': price_result['coefficients'],
            'factors': factors,
            'explanation': explanation,
            'mode': mode,
            'photos_analyzed': len(final_paths),
            'state_id': state_id,
            'state_name': state_name,
            'city_id': city_id,
            'city_name': city_name,
            'realty_type': realty_type,
            'rooms_count': rooms_count,
            'floor': floor,
            'total_floors': total_floors,
            'year_built': year_built,
            'user_area': user_area,
            'user_description': user_description,
        }

        return jsonify({'evaluation': evaluation, 'photo_ids': photo_ids})

    except Exception as exc:
        logger.exception('evaluate: %s', exc)
        for p in saved_paths:
            p.unlink(missing_ok=True)
        return jsonify({'error': f'Внутрішня помилка: {exc}'}), 500


@app.route('/api/save', methods=['POST'])
def save_evaluation():
    body = request.get_json(silent=True) or {}
    browser_id = body.get('browser_id', '').strip()
    evaluation = body.get('evaluation')
    input_data = body.get('input', {})
    photo_ids = body.get('photo_ids', [])

    if not browser_id or not evaluation:
        return jsonify({'error': 'Відсутній browser_id або evaluation'}), 400

    input_merged = {
        'state_id': evaluation.get('state_id'),
        'state_name': evaluation.get('state_name', ''),
        'city_id': evaluation.get('city_id'),
        'city_name': evaluation.get('city_name', ''),
        'realty_type': evaluation.get('realty_type'),
        'rooms_count': evaluation.get('rooms_count'),
        'floor': evaluation.get('floor'),
        'total_floors': evaluation.get('total_floors'),
        'year_built': evaluation.get('year_built'),
        'user_area': evaluation.get('user_area'),
        'user_description': evaluation.get('user_description', ''),
        **input_data,
    }

    try:
        eval_id = repository.save_evaluation(browser_id, evaluation, input_merged, photo_ids)
        return jsonify({'id': eval_id, 'status': 'saved'})
    except Exception as exc:
        logger.exception('save_evaluation: %s', exc)
        return jsonify({'error': str(exc)}), 500


@app.route('/api/history')
def get_history():
    browser_id = request.args.get('browser_id', '').strip()
    if not browser_id:
        return jsonify({'error': 'Відсутній browser_id'}), 400
    return jsonify(repository.get_history(browser_id))


@app.route('/api/history/<int:eval_id>', methods=['GET', 'DELETE'])
def history_item(eval_id):
    browser_id = request.args.get('browser_id', '').strip()
    if not browser_id:
        return jsonify({'error': 'Відсутній browser_id'}), 400

    if request.method == 'DELETE':
        filenames = repository.delete_evaluation(eval_id, browser_id)
        if filenames is None:
            return jsonify({'error': 'Запис не знайдено'}), 404
        for fname in filenames:
            (config.UPLOAD_FOLDER / fname).unlink(missing_ok=True)
        return jsonify({'status': 'deleted'})

    data = repository.get_evaluation(eval_id, browser_id)
    if data is None:
        return jsonify({'error': 'Запис не знайдено'}), 404
    for photo in data.get('photos', []):
        photo['url'] = f"/uploads/{photo['filename']}"
    return jsonify(data)


def _validate_evaluate_request(req) -> list:
    errors = []
    for field in ('state_id', 'city_id', 'realty_type', 'rooms_count'):
        if not req.form.get(field):
            errors.append(f'Поле {field} обовʼязкове')
    rt = req.form.get('realty_type')
    if rt and rt not in ('apartment', 'house'):
        errors.append('realty_type має бути apartment або house')
    rc = req.form.get('rooms_count')
    if rc:
        try:
            v = int(rc)
            if not 1 <= v <= 10:
                errors.append('rooms_count має бути від 1 до 10')
        except ValueError:
            errors.append('rooms_count має бути цілим числом')
    return errors


def _int_or_none(val) -> int | None:
    try:
        return int(val) if val else None
    except (TypeError, ValueError):
        return None


def _float_or_none(val) -> float | None:
    try:
        return float(val) if val else None
    except (TypeError, ValueError):
        return None


def _default_area(realty_type: str, rooms_count: int) -> float:
    base = {'apartment': 40, 'house': 80}.get(realty_type, 50)
    return base + rooms_count * 12


def _resolve_names(state_id: int, city_id: int) -> tuple[str, str]:
    if not config.REGIONS_FILE.exists():
        return '', ''
    try:
        regions = json.loads(config.REGIONS_FILE.read_text(encoding='utf-8'))
        state_name = ''
        city_name = ''
        for region in regions:
            if region['state_id'] == state_id:
                state_name = region['name']
                for city in region.get('cities', []):
                    if city['city_id'] == city_id:
                        city_name = city['name']
                        break
                break
        return state_name, city_name
    except Exception:
        return '', ''


if __name__ == '__main__':
    config.UPLOAD_FOLDER.mkdir(exist_ok=True)
    config.DATA_FOLDER.mkdir(exist_ok=True)
    init_db()
    app.run(host='127.0.0.1', port=config.PORT, debug=False)
