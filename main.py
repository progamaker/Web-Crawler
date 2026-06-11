import logging
from config import get_config
from crawler.crawler import Crawler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    cfg = get_config()

    print(f"📖 Товар: {cfg['product_name']}")
    print(f"🔑 Ключевые слова: {cfg['keywords']}")
    print(f"🔗 Релевантные части URL: {cfg['relevant_url_parts']}")
    print(f"🌐 Сайты: {cfg['allowed_domains']}")
    print(f"📄 Лимит: {cfg['max_pages']} страниц / {cfg['max_pages_per_domain']} на сайт\n")

    crawler = Crawler(
        seed_urls=cfg["seed_urls"],
        allowed_domains=cfg["allowed_domains"],
        product_keywords=cfg["keywords"],
        url_must_contain=cfg["url_must_contain"],
        relevant_url_parts=cfg["relevant_url_parts"],
        skip_urls=cfg["skip_urls"],
        max_pages=cfg["max_pages"],
        max_pages_per_domain=cfg["max_pages_per_domain"],
        max_depth=cfg["max_depth"],
        delay=cfg["delay"],
        output_dir="data",
    )
    crawler.run()

    print(f"\n✅ Краулинг завершён.")
    print(f"Найденные страницы: data/product_urls.txt")
    print(f"Запусти теперь: python3 price_checker_v2.py")