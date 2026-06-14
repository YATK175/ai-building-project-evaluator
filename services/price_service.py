import json
import logging
from datetime import datetime, timedelta
from config import PRICE_CACHE_FILE, PRICE_FALLBACK_FILE, PRICE_CACHE_TTL_DAYS

logger = logging.getLogger(__name__)


def get_base_price(
    state_id: int,
    city_id: int,
    realty_type: str,
    rooms_count: int,
) -> dict:
    cache_key = f'{state_id}_{city_id}_{realty_type}_{rooms_count}'

    cached = _read_cache(cache_key)
    if cached and _is_fresh(cached, PRICE_CACHE_TTL_DAYS):
        logger.info('Ціна з кешу (свіжа): %s = %.0f USD/м²', cache_key, cached['price_per_m2'])
        return {
            'price_per_m2': cached['price_per_m2'],
            'sample_size': cached.get('sample_size', 0),
            'source': 'cache',
        }

    try:
        from services.domria_client import DomRiaClient
        result = DomRiaClient().search_median_price(state_id, city_id, realty_type, rooms_count)
        if result:
            _write_cache(cache_key, result)
            logger.info('Ціна з DOM.RIA live: %s = %.0f USD/м²', cache_key, result['price_per_m2'])
            return {
                'price_per_m2': result['price_per_m2'],
                'sample_size': result['sample_size'],
                'source': 'domria_live',
            }
    except Exception as exc:
        logger.warning('DOM.RIA недоступний: %s', exc)

    if cached:
        logger.info('Ціна зі старого кешу: %s = %.0f USD/м²', cache_key, cached['price_per_m2'])
        return {
            'price_per_m2': cached['price_per_m2'],
            'sample_size': cached.get('sample_size', 0),
            'source': 'cache_stale',
        }

    price = _fallback_price(state_id, city_id, realty_type, rooms_count)
    logger.info('Ціна зі статичного fallback: %s = %.0f USD/м²', cache_key, price)
    return {'price_per_m2': price, 'sample_size': 0, 'source': 'fallback'}


def max_cache_age_days() -> float:
    cache = _load_cache()
    if not cache:
        return 999.0
    now = datetime.now()
    oldest = 0.0
    for entry in cache.values():
        try:
            fetched = datetime.fromisoformat(entry['fetched_at'])
            age = (now - fetched).total_seconds() / 86400
            if age > oldest:
                oldest = age
        except Exception:
            pass
    return oldest


def _read_cache(key: str) -> dict | None:
    cache = _load_cache()
    return cache.get(key)


def _load_cache() -> dict:
    if not PRICE_CACHE_FILE.exists():
        return {}
    try:
        return json.loads(PRICE_CACHE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def _write_cache(key: str, result: dict):
    cache = _load_cache()
    cache[key] = {
        'price_per_m2': result['price_per_m2'],
        'sample_size': result.get('sample_size', 0),
        'fetched_at': datetime.now().isoformat(timespec='seconds'),
        'ttl_days': PRICE_CACHE_TTL_DAYS,
    }
    PRICE_CACHE_FILE.parent.mkdir(exist_ok=True)
    PRICE_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')


def _is_fresh(entry: dict, ttl_days: int) -> bool:
    try:
        fetched = datetime.fromisoformat(entry['fetched_at'])
        return datetime.now() - fetched < timedelta(days=ttl_days)
    except Exception:
        return False


def _fallback_price(state_id: int, city_id: int, realty_type: str, rooms_count: int) -> float:
    if not PRICE_FALLBACK_FILE.exists():
        return 700.0 if realty_type == 'apartment' else 500.0

    try:
        fb = json.loads(PRICE_FALLBACK_FILE.read_text(encoding='utf-8'))
    except Exception:
        return 700.0

    cities = fb.get('cities', {})
    key = str(city_id)
    if key in cities and realty_type in cities[key]:
        base = cities[key][realty_type]
    else:
        states = fb.get('default_per_state', {})
        skey = str(state_id)
        if skey in states and realty_type in states[skey]:
            base = states[skey][realty_type]
        else:
            base = 700 if realty_type == 'apartment' else 500

    multiplier = fb.get('rooms_multiplier', {}).get(str(rooms_count), 1.0)
    return round(base * multiplier, 2)
