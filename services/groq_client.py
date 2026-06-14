import base64
import logging
from pathlib import Path
import httpx
from config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_VISION_MODEL, GROQ_TEXT_MODEL

logger = logging.getLogger(__name__)


class GroqUnavailable(Exception):
    pass


def _headers() -> dict:
    return {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json',
    }


def _image_to_data_uri(image_path: str | Path) -> str:
    data = Path(image_path).read_bytes()
    b64 = base64.b64encode(data).decode()
    return f'data:image/jpeg;base64,{b64}'


def chat_with_vision(prompt: str, image_paths: list, model: str | None = None) -> str:
    if not GROQ_API_KEY:
        raise GroqUnavailable('GROQ_API_KEY не встановлено')

    content = [{'type': 'text', 'text': prompt}]
    for path in image_paths:
        content.append({
            'type': 'image_url',
            'image_url': {'url': _image_to_data_uri(path)},
        })

    payload = {
        'model': model or GROQ_VISION_MODEL,
        'messages': [{'role': 'user', 'content': content}],
        'max_tokens': 1500,
        'temperature': 0.3,
    }
    try:
        resp = httpx.post(
            f'{GROQ_BASE_URL}/chat/completions',
            headers=_headers(),
            json=payload,
            timeout=60,
        )
        if resp.status_code == 429:
            raise GroqUnavailable(f'Groq rate limit (429): {resp.text[:200]}')
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except GroqUnavailable:
        raise
    except httpx.TimeoutException:
        raise GroqUnavailable('Groq timeout')
    except Exception as exc:
        raise GroqUnavailable(str(exc))


def chat_text_only(prompt: str, model: str | None = None) -> str:
    if not GROQ_API_KEY:
        raise GroqUnavailable('GROQ_API_KEY не встановлено')

    payload = {
        'model': model or GROQ_TEXT_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 1000,
        'temperature': 0.5,
    }
    try:
        resp = httpx.post(
            f'{GROQ_BASE_URL}/chat/completions',
            headers=_headers(),
            json=payload,
            timeout=30,
        )
        if resp.status_code == 429:
            raise GroqUnavailable(f'Groq rate limit (429): {resp.text[:200]}')
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except GroqUnavailable:
        raise
    except httpx.TimeoutException:
        raise GroqUnavailable('Groq timeout')
    except Exception as exc:
        raise GroqUnavailable(str(exc))


def is_available(timeout: float = 3.0) -> bool:
    if not GROQ_API_KEY:
        return False
    try:
        resp = httpx.get(
            f'{GROQ_BASE_URL}/models',
            headers=_headers(),
            timeout=timeout,
        )
        return resp.status_code < 500
    except Exception:
        return False
