import logging
from services import openrouter_client, domria_client, groq_client
from services import price_service

logger = logging.getLogger(__name__)

_cached_mode = None
_cache_ts = None


def decide_mode(force_refresh: bool = False) -> str:
    global _cached_mode, _cache_ts
    import time
    if not force_refresh and _cached_mode and _cache_ts and (time.time() - _cache_ts < 30):
        return _cached_mode

    llm_ok = groq_client.is_available(timeout=3.0) or openrouter_client.is_available(timeout=3.0)
    domria_ok = domria_client.DomRiaClient().is_available(timeout=3.0)
    cache_age = price_service.max_cache_age_days()

    if llm_ok and domria_ok:
        mode = 'full'
    elif llm_ok and not domria_ok and cache_age < 30:
        mode = 'full_with_cached_prices'
    elif not llm_ok and _local_available() and (domria_ok or cache_age < 30):
        mode = 'degraded'
    else:
        mode = 'offline'

    _cached_mode = mode
    _cache_ts = time.time()
    logger.info('Режим роботи: %s (groq=%s, openrouter=%s, domria=%s)',
                mode,
                groq_client.is_available(timeout=1.0),
                openrouter_client.is_available(timeout=1.0),
                domria_ok)
    return mode


def get_status() -> dict:
    from config import OPENROUTER_API_KEY, DOMRIA_API_KEY, GROQ_API_KEY

    groq_status = 'not_configured'
    if GROQ_API_KEY:
        groq_status = 'ok' if groq_client.is_available(timeout=3.0) else 'unavailable'

    openrouter_status = 'not_configured'
    if OPENROUTER_API_KEY:
        openrouter_status = 'ok' if openrouter_client.is_available(timeout=3.0) else 'unavailable'

    domria_status = 'not_configured'
    if DOMRIA_API_KEY:
        domria_status = 'ok' if domria_client.DomRiaClient().is_available(timeout=3.0) else 'unavailable'

    local_vision = 'ready' if _local_available() else 'not_installed'
    cache_age = price_service.max_cache_age_days()
    mode = decide_mode(force_refresh=True)

    return {
        'groq': groq_status,
        'openrouter': openrouter_status,
        'domria': domria_status,
        'local_vision': local_vision,
        'current_mode': mode,
        'cache_age_days': round(cache_age, 1) if cache_age < 999 else None,
    }


def _local_available() -> bool:
    from config import ENABLE_LOCAL_VISION
    if not ENABLE_LOCAL_VISION:
        return False
    try:
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False
