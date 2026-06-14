# RealtyVision

Веб-застосунок для оцінки ринкової вартості житлової нерухомості за фотографіями та характеристиками об'єкта. Аналіз виконується за допомогою мультимодальних AI-моделей (Groq / OpenRouter), актуальні ціни отримуються з DOM.RIA API.

---

## Можливості

- Завантаження до 10 фотографій квартири або будинку
- AI-аналіз стану приміщень: оцінка від 1 до 5, виявлення дефектів та переваг
- Автоматична оцінка площі за фото (якщо не вказана вручну)
- Отримання актуальних ринкових цін через DOM.RIA API з 7-денним кешем
- Розрахунок фінальної вартості за формулою з коефіцієнтами стану, поверху та року побудови
- Генерація текстового пояснення розрахунку через LLM
- Збереження оцінок в локальну базу даних (SQLite) та перегляд історії
- Градація режимів: `full` → `full_with_cached_prices` → `degraded` → `offline`

---

## Вимоги

- **Python 3.10+** (рекомендовано 3.11 або 3.12)
- Операційна система: Windows 10/11
- Інтернет-з'єднання для роботи з API
- API-ключі (дивись розділ нижче)

---

## Перший запуск

### 1. Клонувати репозиторій

```
git clone https://github.com/YOUR_USERNAME/RealtyVision.git
cd RealtyVision
```

### 2. Налаштувати змінні середовища

Скопіювати файл прикладу та заповнити ключі:

```
copy .env.example .env
```

Відкрити `.env` у будь-якому текстовому редакторі та вставити ключі:

```
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-v1-...
DOMRIA_API_KEY=...
PORT=8000
```

### 3. Запустити через батник

```
run.bat
```

Батник автоматично:
- Створить віртуальне середовище `venv`
- Встановить залежності з `requirements.txt`
- Запустить сервер на `http://127.0.0.1:8000`

При повторних запусках — просто `run.bat`, встановлення пропускається.

---

## Зупинка сервера

```
stop.bat
```

---

## Де отримати API-ключі

| Сервіс | URL | Примітка |
|--------|-----|----------|
| **Groq** | https://console.groq.com/keys | Безкоштовно, реєстрація через Google |
| **OpenRouter** | https://openrouter.ai/keys | Fallback для Groq; є безкоштовні моделі |
| **DOM.RIA** | https://developers.ria.com | Ключ видається після реєстрації |

Groq — основний LLM-провайдер (vision + text). OpenRouter — резервний. DOM.RIA — джерело ринкових цін.

---

## Структура проєкту

```
RealtyVision/
├── app.py                      # Flask-додаток, всі API-маршрути
├── config.py                   # Конфігурація з .env
├── requirements.txt
├── .env.example                # Шаблон змінних середовища
├── run.bat                     # Запуск (Windows)
├── stop.bat                    # Зупинка сервера
│
├── models/
│   ├── database.py             # Ініціалізація SQLite, статичний список регіонів
│   └── repository.py           # CRUD: оцінки та фото
│
├── services/
│   ├── groq_client.py          # Groq API (vision + text)
│   ├── openrouter_client.py    # OpenRouter API (fallback)
│   ├── domria_client.py        # DOM.RIA API
│   ├── price_service.py        # Отримання цін з кешем
│   ├── vision_service.py       # Аналіз фото: Groq -> OpenRouter -> local CLIP
│   ├── explanation_service.py  # Генерація пояснення: LLM або шаблон
│   ├── rules_engine.py         # Формула ціни та коефіцієнти
│   └── provider_registry.py    # Вибір режиму роботи
│
├── templates/
│   └── index.html              # Vue 3 SPA (один HTML-файл)
│
├── static/
│   ├── css/style.css
│   ├── js/app.js               # Vue 3 логіка
│   └── img/logo.svg
│
├── prompts/
│   ├── vision_analysis.txt     # Промпт для аналізу фото
│   └── explanation.txt         # Промпт для генерації пояснення
│
├── data/
│   └── price_fallback.json     # Статичні ціни для offline-режиму
│
└── uploads/                    # Завантажені фото (створюється автоматично)
```

---

## API-маршрути

| Метод | Шлях | Опис |
|-------|------|------|
| GET | `/` | Головна сторінка |
| GET | `/api/health` | Статус провайдерів |
| GET | `/api/regions` | Список областей |
| GET | `/api/cities/<state_id>` | Міста в області |
| POST | `/api/evaluate` | Основна оцінка (multipart: photos[] + поля форми) |
| POST | `/api/save` | Збереження результату в історію |
| GET | `/api/history?browser_id=<uuid>` | Список збережених оцінок |
| GET | `/api/history/<id>?browser_id=<uuid>` | Деталі оцінки |
| DELETE | `/api/history/<id>?browser_id=<uuid>` | Видалення запису |
| GET | `/uploads/<filename>` | Завантажені фото |

---

## Формула розрахунку

```
final_price = base_price_per_m2 x area x condition_coeff x floor_coeff x year_coeff
```

**Коефіцієнт стану** (condition_score 1–5):

| Оцінка | Стан | Коефіцієнт |
|--------|------|------------|
| 1 | Потребує капремонту | 0.65 |
| 2 | Незадовільний | 0.80 |
| 3 | Житловий стан | 1.00 |
| 4 | Євроремонт | 1.18 |
| 5 | Преміум | 1.40 |

**Коефіцієнт поверху** (тільки квартира): 1-й поверх → 0.93, останній → 0.96, решта → 1.00–1.02.

**Коефіцієнт року**: до 1960 → 0.85, 1960–1989 → 0.90, 1990–2009 → 1.00, 2010–2019 → 1.10, від 2020 → 1.15.

Діапазон ціни: ±15% якщо площа вказана, ±20% якщо оцінена за фото.

---

## Режими роботи

| Режим | Vision | Ціни | Пояснення |
|-------|--------|------|-----------|
| `full` | Groq VLM | DOM.RIA live | Groq LLM |
| `full_with_cached_prices` | Groq VLM | Кеш (до 30 днів) | Groq LLM |
| `degraded` | Local CLIP | DOM.RIA / кеш | Шаблон |
| `offline` | Пропуск | Статичний файл | Шаблон |

---

## Офлайн-відеоаналіз (опціонально)

Для роботи без API встановити додаткові залежності (~2 ГБ):

```
venv\Scripts\activate
pip install transformers torch
```

Встановити в `.env`:
```
ENABLE_LOCAL_VISION=true
```

---

## Запуск тестів

```
venv\Scripts\activate
python -m pytest tests/ -v
```

---

## Залежності

| Бібліотека | Призначення |
|-----------|-------------|
| Flask 3.x | HTTP-сервер |
| httpx | Асинхронні HTTP-запити до API |
| python-dotenv | Читання .env |
| Pillow | Обробка та стиснення фото |
