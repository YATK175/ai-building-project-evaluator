import logging
from pathlib import Path
from config import PROMPTS_FOLDER

logger = logging.getLogger(__name__)

_PRICE_SOURCE_LABELS = {
    'domria_live': 'DOM.RIA (актуальні дані)',
    'cache': 'DOM.RIA (кеш)',
    'cache_stale': 'DOM.RIA (застарілий кеш)',
    'fallback': 'статичний довідник',
}

_AREA_SOURCE_LABELS = {
    'user': 'вказана користувачем',
    'estimated': 'оцінена за фото',
}

_REALTY_TYPE_UA = {
    'apartment': 'квартири',
    'house': 'будинку',
}

_CITY_LOCATIVE = {
    'Суми': 'Сумах',
    'Київ': 'Києві',
    'Львів': 'Львові',
    'Харків': 'Харкові',
    'Одеса': 'Одесі',
    'Дніпро': 'Дніпрі',
    'Запоріжжя': 'Запоріжжі',
    'Вінниця': 'Вінниці',
    'Полтава': 'Полтаві',
    'Черкаси': 'Черкасах',
}


def generate(data: dict, use_llm: bool = True) -> str:
    if use_llm:
        try:
            return _generate_with_llm(data)
        except Exception as exc:
            logger.warning('LLM пояснення недоступне: %s', exc)
    return _generate_template(data)


def _generate_with_llm(data: dict) -> str:
    from services.groq_client import chat_text_only as groq_text, GroqUnavailable
    from services.openrouter_client import chat_text_only as or_text, OpenRouterUnavailable
    prompt_path = PROMPTS_FOLDER / 'explanation.txt'
    template = prompt_path.read_text(encoding='utf-8')
    prompt = template.format(**_build_vars(data))

    try:
        return groq_text(prompt)
    except GroqUnavailable as exc:
        logger.warning('Groq text недоступний (%s), спроба OpenRouter', exc)

    return or_text(prompt)


def _generate_template(data: dict) -> str:
    v = _build_vars(data)
    base_total = round(data['base_price_per_m2'] * data['final_area'])
    template = (
        f"Ціна сформована на основі базової ринкової вартості {v['base_price_per_m2']} USD за квадратний метр "
        f"для {v['realty_type_ua']} у {v['city_name_locative']}. "
        f"Дані про базову ціну отримано з {v['price_source_label']}.\n\n"
        f"При площі {v['final_area']} м² базова сума становить {base_total} USD. "
        f"До цієї суми застосовано коригування: стан об'єкта оцінено як «{v['condition_label']}» "
        f"(коефіцієнт {v['coef_condition']}); поверх {v['floor_info']} "
        f"(коефіцієнт {v['coef_floor']}); рік побудови {v['year_built']} "
        f"(коефіцієнт {v['coef_year']}).\n\n"
        f"Підсумкова орієнтовна ціна: {v['final_price']} USD "
        f"з діапазоном {v['price_min']}–{v['price_max']} USD.\n\n"
        "Це не офіційна експертна оцінка. Для угод з нерухомістю звертайтеся до сертифікованого оцінювача."
    )
    return template


def _build_vars(data: dict) -> dict:
    coef = data.get('coefficients', {})
    city = data.get('city_name', '')
    floor = data.get('floor')
    total_floors = data.get('total_floors')
    floor_info = f"{floor}/{total_floors}" if floor and total_floors else (str(floor) if floor else 'не вказано')

    return {
        'city_name': city,
        'city_name_locative': _CITY_LOCATIVE.get(city, city),
        'state_name': data.get('state_name', ''),
        'realty_type_ua': _REALTY_TYPE_UA.get(data.get('realty_type', 'apartment'), 'квартири'),
        'rooms_count': data.get('rooms_count', ''),
        'final_area': data.get('final_area', ''),
        'area_source': _AREA_SOURCE_LABELS.get(data.get('area_source', 'user'), 'вказана'),
        'floor': floor,
        'total_floors': total_floors,
        'floor_info': floor_info,
        'year_built': data.get('year_built', 'не вказано'),
        'condition_score': data.get('condition_score', 3),
        'condition_label': data.get('condition_label', 'Житловий стан'),
        'defects': ', '.join(data.get('defects', [])) or 'не виявлено',
        'features': ', '.join(data.get('features', [])) or 'не виявлено',
        'user_description': data.get('user_description') or '',
        'base_price_per_m2': data.get('base_price_per_m2', ''),
        'price_source_label': _PRICE_SOURCE_LABELS.get(data.get('price_source', 'fallback'), 'довідник'),
        'coef_condition': coef.get('condition', 1.0),
        'coef_floor': coef.get('floor', 1.0),
        'coef_year': coef.get('year', 1.0),
        'final_price': data.get('final_price', ''),
        'price_min': data.get('price_min', ''),
        'price_max': data.get('price_max', ''),
    }
