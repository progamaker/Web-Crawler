import asyncio
import csv
import os
import re
from datetime import datetime
from config import get_config
from crawler.notifier import Notifier
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

PRODUCT_URLS_FILE = "data/product_urls.txt"
PRICES_FILE       = "data/prices.csv"

cfg = get_config()
PRODUCT_NAME     = cfg["product_name"]
PRODUCT_KEYWORDS = cfg["keywords"]

# Инициализируем notifier — если токен не задан, уведомления просто отключатся
notifier = Notifier(
    token   = cfg.get("telegram_token", ""),
    chat_id = cfg.get("telegram_chat_id", ""),
)


def extract_clean_price(text: str) -> str:
    match = re.search(r'[\d\s]+₽', text)
    return match.group(0).strip() if match else ""


def matches_product(text: str) -> bool:
    text_lower = text.lower()
    numbers = [kw for kw in PRODUCT_KEYWORDS if kw.isdigit()]
    colors  = [kw for kw in PRODUCT_KEYWORDS if not kw.isdigit()]
    return all(n in text_lower for n in numbers) and \
           (any(c in text_lower for c in colors) if colors else True)


def get_domain(url: str) -> str:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.replace("www.", "")
    return host.split(".")[0]


def price_to_int(price: str) -> int:
    digits = re.sub(r"[^\d]", "", price)
    return int(digits) if digits else 0


def parse_price_from_page(soup: BeautifulSoup, url: str) -> str:
    domain = get_domain(url)

    if domain == "optogadzhet":
        tag = soup.find("div", class_="card-item__price--current")
        if tag:
            price = extract_clean_price(tag.get_text(strip=True))
            if price:
                return price
        ins = soup.find("ins")
        if ins:
            return extract_clean_price(ins.get_text(strip=True))

    elif domain == "igadget16":
        ins = soup.find("ins") or soup.find("p", class_="drop-card__price")
        if ins:
            return extract_clean_price(ins.get_text(strip=True))

    elif domain == "tatphone":
        tag = soup.find("span", class_="woocommerce-Price-amount")
        if tag:
            return extract_clean_price(tag.get_text(strip=True))

    elif domain == "citilink":
        for tag in soup.find_all(["span", "div"], class_=lambda c: c and "price" in c.lower() if c else False):
            classes = " ".join(tag.get("class", []))
            if any(x in classes.lower() for x in ["old", "cross", "sale", "previous"]):
                continue
            candidate = extract_clean_price(tag.get_text(strip=True))
            digits = re.sub(r"[^\d]", "", candidate)
            if candidate and digits and int(digits) > 10000:
                return candidate

    for tag in soup.find_all(["span", "div", "p"], class_=lambda c: c and "price" in c.lower() if c else False):
        classes = " ".join(tag.get("class", []))
        if any(x in classes.lower() for x in ["old", "cross", "sale", "before", "previous"]):
            continue
        candidate = extract_clean_price(tag.get_text(strip=True))
        digits = re.sub(r"[^\d]", "", candidate)
        if candidate and digits and int(digits) > 5000:
            return candidate

    return ""


def load_urls() -> list[str]:
    if not os.path.exists(PRODUCT_URLS_FILE):
        print(f"❌ Файл {PRODUCT_URLS_FILE} не найден.")
        print("   Сначала запусти: python3 main.py")
        return []
    with open(PRODUCT_URLS_FILE, encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]
    print(f"📋 Загружено {len(urls)} URL из {PRODUCT_URLS_FILE}\n")
    return urls


def load_history() -> list[dict]:
    if not os.path.exists(PRICES_FILE):
        return []
    with open(PRICES_FILE, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_csv(new_results: list[dict]):
    os.makedirs("data", exist_ok=True)
    fieldnames = ["дата", "магазин", "товар", "цена", "url"]
    file_exists = os.path.exists(PRICES_FILE)
    with open(PRICES_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(new_results)
    print(f"  💾 Добавлено {len(new_results)} записей в data/prices.csv")


def check_and_notify(new_results: list[dict], history: list[dict], today: str):
    """
    Сравниваем новые цены с историей и отправляем уведомления если:
    1. Цена упала по сравнению с прошлым запуском
    2. Новый исторический минимум
    3. Итоговая сводка (всегда)
    """
    # Последняя цена каждого магазина ДО сегодня
    prev_prices: dict[str, tuple[int, str]] = {}  # shop → (int, str)
    for row in history:
        if row.get("дата", "") < today:
            prev_prices[row["магазин"]] = (price_to_int(row["цена"]), row["цена"])

    # Исторический минимум по всем данным ДО сегодня
    all_hist = [price_to_int(r["цена"]) for r in history
                if price_to_int(r["цена"]) > 0 and r.get("дата", "") < today]
    hist_min = min(all_hist) if all_hist else None

    for r in new_results:
        shop    = r["магазин"]
        cur_int = price_to_int(r["цена"])
        url     = r["url"]

        # 1. Цена упала
        if shop in prev_prices:
            prev_int, prev_str = prev_prices[shop]
            if cur_int < prev_int:
                diff = prev_int - cur_int
                notifier.price_dropped(shop, prev_str, r["цена"], diff, url)

        # 2. Новый исторический минимум
        if hist_min and cur_int < hist_min:
            notifier.new_historic_minimum(shop, r["цена"], url)

    # 3. Итоговая сводка — всегда после каждого запуска
    if new_results:
        best = min(new_results, key=lambda x: price_to_int(x["цена"]))
        notifier.daily_summary(PRODUCT_NAME, new_results, best)


def print_table(new_results: list[dict], history: list[dict], today: str):
    prev_prices: dict[str, int] = {}
    for row in history:
        if row.get("дата", "") < today:
            prev_prices[row["магазин"]] = price_to_int(row["цена"])

    print("\n" + "═" * 75)
    print(f"  {'МАГАЗИН':<14} {'ЦЕНА':<14} {'ИЗМЕНЕНИЕ':<12} {'ТОВАР'}")
    print("═" * 75)

    for r in new_results:
        name  = r["товар"][:32] + "..." if len(r["товар"]) > 32 else r["товар"]
        cur   = price_to_int(r["цена"])
        prev  = prev_prices.get(r["магазин"])

        if prev and cur and prev != cur:
            diff   = cur - prev
            arrow  = "↓" if diff < 0 else "↑"
            change = f"{arrow} {abs(diff):,}₽".replace(",", " ")
        else:
            change = "—" if prev else "новый"

        print(f"  {r['магазин']:<14} {r['цена']:<14} {change:<12} {name}")

    print("═" * 75)

    prices_numeric = [(price_to_int(r["цена"]), r["магазин"], r["цена"])
                      for r in new_results if price_to_int(r["цена"]) > 0]
    if prices_numeric:
        best = min(prices_numeric)
        print(f"\n  🏆 Лучшая цена: {best[2]} в {best[1]}")

    all_prices = [(price_to_int(r["цена"]), r["магазин"], r["цена"], r.get("дата", "—"))
                  for r in history if price_to_int(r["цена"]) > 0]
    if all_prices:
        hist_min = min(all_prices)
        print(f"  📉 Исторический минимум: {hist_min[2]} в {hist_min[1]} ({hist_min[3]})")
    print()


async def main():
    urls = load_urls()
    if not urls:
        return

    today   = datetime.now().strftime("%Y-%m-%d")
    history = load_history()

    print(f"🛍️  Товар: {PRODUCT_NAME}")
    print(f"📅 Дата: {today}")
    print(f"🔑 Ключевые слова: {PRODUCT_KEYWORDS}")
    print("⚡ Открываю браузер...\n")

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="ru-RU",
        )
        page = await context.new_page()

        for url in urls:
            domain = get_domain(url)
            print(f"🔍 {domain}: ...{url[-45:]}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=40000)
                await page.wait_for_timeout(3000)

                html  = await page.content()
                soup  = BeautifulSoup(html, "lxml")
                h1    = soup.find("h1")
                name  = h1.get_text(strip=True) if h1 else "—"
                price = parse_price_from_page(soup, url)

                if price and matches_product(name):
                    print(f"  ✅ {price}  —  {name[:55]}")
                    results.append({
                        "дата":    today,
                        "магазин": domain,
                        "товар":   name,
                        "цена":    price,
                        "url":     url,
                    })
                elif price:
                    print(f"  ⚠️  Цена {price} найдена, но товар не совпадает: {name[:40]}")
                else:
                    print(f"  ⚠️  Цена не найдена")

            except Exception as e:
                print(f"  ❌ Ошибка: {e}")

            await asyncio.sleep(1)

        await browser.close()

    print_table(results, history, today)
    check_and_notify(results, history, today)
    save_csv(results)


if __name__ == "__main__":
    asyncio.run(main())