import sqlite3
import json
import logging
from pathlib import Path
from config import DB_PATH, REGIONS_FILE, DATA_FOLDER

logger = logging.getLogger(__name__)

_EXCLUDED_REGIONS = {'Донецька', 'Луганська', 'АР Крим', 'Крим'}

_STATIC_REGIONS = [
    {"state_id": 1,  "name": "Вінницька",        "cities": [{"city_id": 1,   "name": "Вінниця"}]},
    {"state_id": 2,  "name": "Волинська",         "cities": [{"city_id": 2,   "name": "Луцьк"}]},
    {"state_id": 3,  "name": "Дніпропетровська",  "cities": [{"city_id": 9,   "name": "Дніпро"}, {"city_id": 184, "name": "Кривий Ріг"}]},
    {"state_id": 5,  "name": "Житомирська",       "cities": [{"city_id": 5,   "name": "Житомир"}]},
    {"state_id": 6,  "name": "Закарпатська",      "cities": [{"city_id": 6,   "name": "Ужгород"}]},
    {"state_id": 7,  "name": "Запорізька",        "cities": [{"city_id": 7,   "name": "Запоріжжя"}]},
    {"state_id": 8,  "name": "Івано-Франківська", "cities": [{"city_id": 8,   "name": "Івано-Франківськ"}]},
    {"state_id": 9,  "name": "м. Київ",           "cities": [{"city_id": 1,   "name": "Київ"}]},
    {"state_id": 10, "name": "Київська",          "cities": [{"city_id": 10,  "name": "Бровари"}, {"city_id": 278, "name": "Бориспіль"}]},
    {"state_id": 11, "name": "Кіровоградська",    "cities": [{"city_id": 12,  "name": "Кропивницький"}]},
    {"state_id": 13, "name": "Львівська",         "cities": [{"city_id": 14,  "name": "Львів"}]},
    {"state_id": 14, "name": "Миколаївська",      "cities": [{"city_id": 15,  "name": "Миколаїв"}]},
    {"state_id": 15, "name": "Одеська",           "cities": [{"city_id": 12,  "name": "Одеса"}]},
    {"state_id": 16, "name": "Полтавська",        "cities": [{"city_id": 16,  "name": "Полтава"}]},
    {"state_id": 17, "name": "Рівненська",        "cities": [{"city_id": 17,  "name": "Рівне"}]},
    {"state_id": 18, "name": "Харківська",        "cities": [{"city_id": 147, "name": "Харків"}]},
    {"state_id": 19, "name": "Сумська",           "cities": [{"city_id": 540, "name": "Суми"}, {"city_id": 541, "name": "Конотоп"}]},
    {"state_id": 20, "name": "Тернопільська",     "cities": [{"city_id": 20,  "name": "Тернопіль"}]},
    {"state_id": 21, "name": "Херсонська",        "cities": [{"city_id": 21,  "name": "Херсон"}]},
    {"state_id": 22, "name": "Хмельницька",       "cities": [{"city_id": 22,  "name": "Хмельницький"}]},
    {"state_id": 23, "name": "Черкаська",         "cities": [{"city_id": 23,  "name": "Черкаси"}]},
    {"state_id": 24, "name": "Чернівецька",       "cities": [{"city_id": 24,  "name": "Чернівці"}]},
    {"state_id": 25, "name": "Чернігівська",      "cities": [{"city_id": 25,  "name": "Чернігів"}]},
]


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    DATA_FOLDER.mkdir(exist_ok=True)
    Path(DB_PATH).parent.mkdir(exist_ok=True)

    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at          TEXT NOT NULL,
                browser_id          TEXT NOT NULL,
                state_id            INTEGER NOT NULL,
                state_name          TEXT NOT NULL,
                city_id             INTEGER NOT NULL,
                city_name           TEXT NOT NULL,
                realty_type         TEXT NOT NULL,
                rooms_count         INTEGER NOT NULL,
                floor               INTEGER,
                total_floors        INTEGER,
                year_built          INTEGER,
                user_area           REAL,
                user_description    TEXT,
                final_area          REAL NOT NULL,
                area_source         TEXT NOT NULL,
                condition_score     INTEGER NOT NULL,
                condition_label     TEXT NOT NULL,
                base_price_per_m2   REAL NOT NULL,
                price_source        TEXT NOT NULL,
                final_price         REAL NOT NULL,
                price_min           REAL NOT NULL,
                price_max           REAL NOT NULL,
                coefficients_json   TEXT NOT NULL,
                factors_json        TEXT NOT NULL,
                explanation         TEXT NOT NULL,
                mode                TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_evaluations_browser
                ON evaluations(browser_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS evaluation_photos (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                evaluation_id   INTEGER NOT NULL,
                filename        TEXT NOT NULL,
                order_index     INTEGER NOT NULL,
                detected_room   TEXT,
                FOREIGN KEY (evaluation_id) REFERENCES evaluations(id) ON DELETE CASCADE
            );
        """)
        conn.commit()
    finally:
        conn.close()

    _ensure_regions()


def _filter_regions(regions: list) -> list:
    return [r for r in regions if r.get('name', '') not in _EXCLUDED_REGIONS]


def _ensure_regions():
    if REGIONS_FILE.exists():
        return
    try:
        from services.domria_client import DomRiaClient
        client = DomRiaClient()
        regions = _filter_regions(client.fetch_all_regions())
        if regions:
            REGIONS_FILE.write_text(json.dumps(regions, ensure_ascii=False, indent=2), encoding='utf-8')
            logger.info('Довідник регіонів завантажено з DOM.RIA (%d областей)', len(regions))
            return
    except Exception as exc:
        logger.warning('Не вдалося завантажити регіони з DOM.RIA: %s', exc)

    REGIONS_FILE.write_text(json.dumps(_STATIC_REGIONS, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info('Використовується вбудований статичний довідник регіонів')
