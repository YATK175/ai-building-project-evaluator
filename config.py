import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
OPENROUTER_PRIMARY_MODEL = os.getenv('OPENROUTER_PRIMARY_MODEL', 'x-ai/grok-4-fast:free')
OPENROUTER_FALLBACK_MODELS = [
    m.strip() for m in os.getenv(
        'OPENROUTER_FALLBACK_MODELS',
        'qwen/qwen2.5-vl-72b-instruct:free,google/gemma-3-27b-it:free'
    ).split(',') if m.strip()
]

GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_BASE_URL = 'https://api.groq.com/openai/v1'
GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'meta-llama/llama-4-scout-17b-16e-instruct')
GROQ_TEXT_MODEL = os.getenv('GROQ_TEXT_MODEL', 'llama-3.3-70b-versatile')

DOMRIA_API_KEY = os.getenv('DOMRIA_API_KEY', '')
DOMRIA_BASE_URL = 'https://developers.ria.com'

ENABLE_LOCAL_VISION = os.getenv('ENABLE_LOCAL_VISION', 'true').lower() == 'true'

PORT = int(os.getenv('PORT', 8000))

UPLOAD_FOLDER = BASE_DIR / 'uploads'
DATA_FOLDER = BASE_DIR / 'data'
PROMPTS_FOLDER = BASE_DIR / 'prompts'
DB_PATH = BASE_DIR / 'realtyvision.db'

PRICE_CACHE_FILE = DATA_FOLDER / 'price_cache.json'
PRICE_FALLBACK_FILE = DATA_FOLDER / 'price_fallback.json'
REGIONS_FILE = DATA_FOLDER / 'regions.json'

PRICE_CACHE_TTL_DAYS = 7
MAX_UPLOAD_SIZE_MB = 8
MAX_PHOTOS = 10
MAX_IMAGE_SIZE = 1280
SITE_REFERER = 'https://skp-degree.com.ua'
