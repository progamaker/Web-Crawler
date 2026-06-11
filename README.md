# Web Crawler & Price Aggregator

Учебный pet-проект — web crawler который обходит сайты магазинов, находит страницы нужного товара и сравнивает цены. Умеет отправлять уведомления в Telegram когда цена падает.

## Что умеет

- Обходит несколько сайтов одновременно с лимитом страниц на домен
- Находит страницы товара по паттерну URL и ключевым словам
- Парсит цены через Playwright (реальный браузер — обходит JS-рендеринг)
- Сохраняет историю цен — видно динамику по дням
- Отправляет уведомления в Telegram при падении цены или новом историческом минимуме
- Соблюдает `robots.txt` и делает паузы между запросами
- Retry с экспоненциальной задержкой при сетевых ошибках
- Умная блокировка доменов при 429 Too Many Requests

## Стек

- Python 3.11+
- [requests](https://pypi.org/project/requests/) — HTTP запросы в краулере
- [BeautifulSoup4](https://pypi.org/project/beautifulsoup4/) — парсинг HTML
- [Playwright](https://playwright.dev/python/) — браузерный парсинг цен (JS-сайты)
- [lxml](https://pypi.org/project/lxml/) — быстрый HTML парсер

## Структура проекта

```
web-crawler/
├── crawler/
│   ├── __init__.py
│   ├── crawler.py      # BFS обход, лимиты по доменам, фильтрация URL
│   ├── fetcher.py      # HTTP запросы, robots.txt, retry, блокировка 429
│   ├── parser.py       # извлечение ссылок и данных из HTML
│   ├── storage.py      # сохранение результатов краулинга
│   └── notifier.py     # Telegram уведомления
├── data/
│   ├── product_urls.txt  # найденные страницы товаров (генерируется)
│   ├── prices.csv        # история цен (накапливается)
│   └── results.csv       # результаты краулинга
├── config.txt          # ← все настройки здесь
├── config.py           # чтение config.txt
├── main.py             # запуск краулера
├── price_checker.py # запуск парсера цен
└── requirements.txt
```

## Быстрый старт

### 1. Клонируй репозиторий

```bash
git clone https://github.com/progamaker/web-crawler.git
cd web-crawler
```

### 2. Создай виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Установи зависимости

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Настрой `config.txt`

```ini
product_name     = iPhone 16 128GB Black
keywords         = 16, 128, черн, black
url_must_contain = iphone-16-128

seed_urls =
    https://optogadzhet.ru/product-category/apple/iphone/
    https://tatphone.ru/iphone16

allowed_domains =
    optogadzhet.ru
    tatphone.ru

max_pages            = 600
max_pages_per_domain = 150
```

### 5. Запусти

```bash
# Шаг 1 — краулер находит страницы товаров
python3 main.py

# Шаг 2 — парсер собирает цены
python3 price_checker.py
```

## Как работает пайплайн

```
config.txt
    ↓
main.py (краулер)
  • стартует с seed_urls
  • обходит страницы по BFS
  • фильтрует по url_must_contain и keywords
  • сохраняет найденные URL → data/product_urls.txt
    ↓
price_checker_v2.py
  • читает product_urls.txt
  • открывает каждую страницу через Playwright
  • парсит цену и название
  • сравнивает с историей → показывает динамику
  • сохраняет → data/prices.csv
  • отправляет уведомление в Telegram
```

## Настройка Telegram уведомлений

1. Напиши `@BotFather` в Telegram → `/newbot` → получи токен
2. Напиши боту любое сообщение, открой в браузере:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
   Найди `"chat": {"id": ...}` — это твой chat_id
3. Добавь в `config.txt`:
   ```ini
   telegram_token   = 7123456789:AAH...
   telegram_chat_id = 123456789
   ```

Уведомления приходят когда:
- Цена упала по сравнению с прошлым запуском
- Новый исторический минимум
- Итоговая сводка после каждого запуска

## Параметры config.txt

| Параметр | Описание | По умолчанию |
|---|---|---|
| `product_name` | Название товара (для отображения) | — |
| `keywords` | Ключевые слова через запятую | — |
| `url_must_contain` | Подстрока в URL товара | — |
| `seed_urls` | Стартовые страницы (по одной на строку) | — |
| `allowed_domains` | Разрешённые домены | — |
| `skip_urls` | Паттерны URL для пропуска | — |
| `max_pages` | Максимум страниц всего | 600 |
| `max_pages_per_domain` | Максимум страниц на сайт | 150 |
| `max_depth` | Глубина обхода | 2 |
| `delay` | Пауза между запросами (сек) | 1.0 |
| `telegram_token` | Токен Telegram бота | — |
| `telegram_chat_id` | ID чата для уведомлений | — |

## Смена товара

Чтобы следить за другим товаром — меняешь только `config.txt`:

```ini
product_name     = Samsung Galaxy S25 256GB Black
keywords         = s25, 256, черн, black
url_must_contain = galaxy-s25-256
```

## Известные ограничения

- Citilink блокирует краулер (429) — для него используй прямую ссылку в `product_urls.txt`
- MVideo и DNS требуют Playwright даже для основного краулинга
- Некоторые сайты меняют CSS-классы — тогда нужно обновить селекторы в `price_checker.py`

## Лицензия

MIT
