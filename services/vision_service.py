import json
import re
import statistics
import logging
from pathlib import Path
from PIL import Image
from config import MAX_IMAGE_SIZE, PROMPTS_FOLDER, ENABLE_LOCAL_VISION

logger = logging.getLogger(__name__)

_VISION_PROMPT = None


def _get_prompt() -> str:
    global _VISION_PROMPT
    if _VISION_PROMPT is None:
        path = PROMPTS_FOLDER / 'vision_analysis.txt'
        _VISION_PROMPT = path.read_text(encoding='utf-8')
    return _VISION_PROMPT


def prepare_image(src_path: Path, dst_path: Path):
    with Image.open(src_path) as img:
        img = img.convert('RGB')
        w, h = img.size
        if max(w, h) > MAX_IMAGE_SIZE:
            ratio = MAX_IMAGE_SIZE / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        img.save(dst_path, 'JPEG', quality=85)


def analyze_photos(image_paths: list, user_description: str | None = None) -> dict:
    from services.provider_registry import decide_mode
    mode = decide_mode()

    if mode in ('full', 'full_with_cached_prices'):
        results = _analyze_with_llm(image_paths, user_description)
        if results:
            return aggregate_vision_results(results)

    if ENABLE_LOCAL_VISION and _local_vision_available():
        results = _analyze_with_local(image_paths)
        if results:
            return aggregate_vision_results(results)

    return _neutral_result()


def _analyze_with_llm(image_paths: list, user_description: str | None = None) -> list | None:
    base_prompt = _get_prompt()
    if user_description:
        prompt = base_prompt + f'\n\nДодатковий опис від власника: «{user_description}»\nВрахуй цю інформацію при оцінці стану та характеристик.'
    else:
        prompt = base_prompt
    results = []
    for path in image_paths:
        raw = _call_vision_api(prompt, path)
        if raw is None:
            return None
        parsed = _parse_json_response(raw)
        if parsed:
            results.append(parsed)
    return results if results else None


def _call_vision_api(prompt: str, path) -> str | None:
    from services.groq_client import chat_with_vision as groq_vision, GroqUnavailable
    from services.openrouter_client import chat_with_vision as or_vision, OpenRouterUnavailable

    try:
        return groq_vision(prompt, [path])
    except GroqUnavailable as exc:
        logger.warning('Groq vision недоступний (%s), спроба OpenRouter', exc)

    try:
        return or_vision(prompt, [path])
    except OpenRouterUnavailable:
        return None


def _analyze_with_local(image_paths: list) -> list | None:
    try:
        analyzer = _get_local_analyzer()
        results = []
        for path in image_paths:
            try:
                result = analyzer.analyze(path)
                results.append(result)
            except Exception as exc:
                logger.warning('Помилка локального аналізу %s: %s', path, exc)
        return results if results else None
    except Exception as exc:
        logger.warning('Локальна модель недоступна: %s', exc)
        return None


_local_analyzer_instance = None


def _get_local_analyzer():
    global _local_analyzer_instance
    if _local_analyzer_instance is None:
        _local_analyzer_instance = LocalVisionAnalyzer()
    return _local_analyzer_instance


def _local_vision_available() -> bool:
    try:
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _parse_json_response(raw: str) -> dict | None:
    cleaned = re.sub(r'```(?:json)?', '', raw).strip()
    try:
        data = json.loads(cleaned)
        if 'condition_score' in data:
            data['condition_score'] = max(1, min(5, int(data['condition_score'])))
        return data
    except Exception:
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1:
            try:
                data = json.loads(cleaned[start:end + 1])
                if 'condition_score' in data:
                    data['condition_score'] = max(1, min(5, int(data['condition_score'])))
                return data
            except Exception:
                pass
    logger.warning('Не вдалося розпарсити JSON відповідь: %.100s', raw)
    return None


def aggregate_vision_results(per_photo_results: list) -> dict:
    valid = [r for r in per_photo_results if r.get('confidence', 1.0) >= 0.3]
    if not valid:
        return _neutral_result()

    condition_score = round(statistics.median(
        r['condition_score'] for r in valid if 'condition_score' in r
    ))

    counted_rooms = set()
    total_area_low = 0.0
    total_area_high = 0.0
    skip_types = {'exterior', 'other', 'hallway', 'balcony'}
    for r in sorted(valid, key=lambda x: -x.get('confidence', 0)):
        room_type = r.get('room_type', 'other')
        if room_type in skip_types:
            continue
        if room_type in counted_rooms:
            continue
        counted_rooms.add(room_type)
        area = r.get('approximate_area_m2')
        if isinstance(area, dict):
            total_area_low += area.get('low', 0)
            total_area_high += area.get('high', 0)

    all_defects = list({d for r in valid for d in r.get('defects', [])})
    all_features = list({f for r in valid for f in r.get('features', [])})

    from services.rules_engine import CONDITION_LABELS
    return {
        'condition_score': condition_score,
        'condition_label': CONDITION_LABELS.get(condition_score, 'Житловий стан'),
        'estimated_area_midpoint': (total_area_low + total_area_high) / 2 if (total_area_low or total_area_high) else None,
        'estimated_area_range': (total_area_low, total_area_high),
        'defects': all_defects,
        'features': all_features,
        'rooms_detected': list(counted_rooms),
    }


def _neutral_result() -> dict:
    from services.rules_engine import CONDITION_LABELS
    return {
        'condition_score': 3,
        'condition_label': CONDITION_LABELS[3],
        'estimated_area_midpoint': None,
        'estimated_area_range': (0, 0),
        'defects': [],
        'features': [],
        'rooms_detected': [],
    }


class LocalVisionAnalyzer:
    def __init__(self):
        self._pipeline = None

    def _ensure_loaded(self):
        if self._pipeline is None:
            from transformers import pipeline as hf_pipeline
            self._pipeline = hf_pipeline(
                'zero-shot-image-classification',
                model='strollingorange/roomLuxuryAnnotater',
            )

    def analyze(self, image_path) -> dict:
        self._ensure_loaded()
        from PIL import Image as PILImage
        image = PILImage.open(image_path)
        labels = [
            'a photo of standard bathroom',
            'a photo of contemporary bathroom',
            'a photo of standard kitchen',
            'a photo of contemporary kitchen',
            'a photo of standard living room',
            'a photo of contemporary living room',
            'a photo of standard bedroom',
            'a photo of contemporary bedroom',
            'a photo of empty unfinished room',
            'a photo of building exterior',
        ]
        result = self._pipeline(image, candidate_labels=labels)
        top = result[0]
        parts = top['label'].replace('a photo of ', '').split()
        tier = parts[0] if parts else 'standard'
        room = '_'.join(parts[1:]) if len(parts) > 1 else 'other'
        score_map = {'empty': 1, 'standard': 3, 'contemporary': 4}
        from services.rules_engine import CONDITION_LABELS
        score = score_map.get(tier, 3)
        return {
            'room_type': self._map_room_type(room),
            'condition_score': score,
            'condition_label': CONDITION_LABELS.get(score, 'Житловий стан'),
            'defects': [],
            'features': [],
            'approximate_area_m2': None,
            'confidence': float(top['score']),
            'source': 'local_clip',
        }

    @staticmethod
    def _map_room_type(raw: str) -> str:
        mapping = {
            'bathroom': 'bathroom',
            'kitchen': 'kitchen',
            'living_room': 'living_room',
            'bedroom': 'bedroom',
            'unfinished_room': 'other',
            'exterior': 'exterior',
        }
        return mapping.get(raw, 'other')
