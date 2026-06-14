import base64
import logging
from pathlib import Path
import httpx
from config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    OPENROUTER_PRIMARY_MODEL, OPENROUTER_FALLBACK_MODELS,
    SITE_REFERER,
)

logger = logging.getLogger(__name__)


class OpenRouterUnavailable(Exception):
    pass


def _headers() -> dict:
    return {
        'Authorization': f'Bearer {OPENROUTER_API_KEY}',
        'HTTP-Referer': SITE_REFERER,
        'X-Title': 'RealtyVision',
        'Content-Type': 'application/json',
    }


def _image_to_data_uri(image_path: str | Path) -> str:
    data = Path(image_path).read_bytes()
    b64 = base64.b64encode(data).decode()
    return f'data:image/jpeg;base64,{b64}'


def chat_with_vision(prompt: str, image_paths: list, model: str | None = None) -> str:
    if not OPENROUTER_API_KEY:
        raise OpenRouterUnavailable('OPENROUTER_API_KEY не встановлено')

    content = [{'type': 'text', 'text': prompt}]
    for path in image_paths:
        content.append({
            'type': 'image_url',
            'image_url': {'url': _image_to_data_uri(path)},
        })

    models_to_try = [model] if model else [OPENROUTER_PRIMARY_MODEL] + OPENROUTER_FALLBACK_MODELS

    last_error = None
    for attempt_model in models_to_try:
        payload = {
            'model': attempt_model,
            'messages': [{'role': 'user', 'content': content}],
            'max_tokens': 1500,
            'temperature': 0.3,
        }
        try:
            resp = httpx.post(
                f'{OPENROUTER_BASE_URL}/chat/completions',
                headers=_headers(),
                json=payload,
                timeout=60,
            )
            if resp.status_code in (429, 500, 502, 503):
                logger.warning('Модель %s повернула %d, перемикаємось', attempt_model, resp.status_code)
                last_error = f'HTTP {resp.status_code}'
                continue
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']
        except httpx.TimeoutException:
            logger.warning('Таймаут для моделі %s', attempt_model)
            last_error = 'timeout'
        except Exception as exc:
            logger.warning('Помилка для моделі %s: %s', attempt_model, exc)
            last_error = str(exc)

    raise OpenRouterUnavailable(f'Усі моделі недоступні. Остання помилка: {last_error}')


def chat_text_only(prompt: str, model: str | None = None) -> str:
    if not OPENROUTER_API_KEY:
        raise OpenRouterUnavailable('OPENROUTER_API_KEY не встановлено')

    models_to_try = [model] if model else [OPENROUTER_PRIMARY_MODEL] + OPENROUTER_FALLBACK_MODELS

    last_error = None
    for attempt_model in models_to_try:
        payload = {
            'model': attempt_model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 1000,
            'temperature': 0.5,
        }
        try:
            resp = httpx.post(
                f'{OPENROUTER_BASE_URL}/chat/completions',
                headers=_headers(),
                json=payload,
                timeout=30,
            )
            if resp.status_code in (429, 500, 502, 503):
                logger.warning('Модель %s повернула %d, перемикаємось', attempt_model, resp.status_code)
                last_error = f'HTTP {resp.status_code}'
                continue
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']
        except httpx.TimeoutException:
            logger.warning('Таймаут для моделі %s', attempt_model)
            last_error = 'timeout'
        except Exception as exc:
            logger.warning('Помилка для моделі %s: %s', attempt_model, exc)
            last_error = str(exc)

    raise OpenRouterUnavailable(f'Усі моделі недоступні. Остання помилка: {last_error}')


def is_available(timeout: float = 3.0) -> bool:
    if not OPENROUTER_API_KEY:
        return False
    try:
        resp = httpx.get(
            f'{OPENROUTER_BASE_URL}/models',
            headers=_headers(),
            timeout=timeout,
        )
        return resp.status_code < 500
    except Exception:
        return False
