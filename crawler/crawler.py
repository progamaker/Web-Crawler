from collections import deque
from urllib.parse import urlparse
import logging
import os
from .fetcher import Fetcher
from .parser import Parser
from .storage import Storage

logger = logging.getLogger(__name__)

class Crawler:
    def __init__(
        self,
        seed_urls: list[str],
        allowed_domains: list[str] | None = None,
        product_keywords: list[str] | None = None,
        url_must_contain: str | None = None,
        relevant_url_parts: list[str] | None = None,
        skip_urls: list[str] | None = None,
        max_pages: int = 300,
        max_pages_per_domain: int = 100,
        max_depth: int = 3,
        delay: float = 1.0,
        output_dir: str = "data",
    ):
        self.seed_urls           = seed_urls
        self.max_pages           = max_pages
        self.max_pages_per_domain = max_pages_per_domain
        self.max_depth           = max_depth
        self.product_keywords    = [kw.lower() for kw in (product_keywords or [])]
        self.url_must_contain    = url_must_contain
        self.skip_urls           = [s.lower() for s in (skip_urls or [])]

        # Части URL которые считаем "релевантными" для нашего товара
        # Краулер добавляет в очередь только ссылки которые содержат
        # хотя бы одну из этих подстрок ИЛИ ведут на страницу товара
        self.relevant_url_parts  = [p.lower() for p in (relevant_url_parts or [])]

        self.fetcher = Fetcher(delay=delay)
        self.parser  = Parser(allowed_domains=allowed_domains)
        self.storage = Storage(output_dir=output_dir)

        self.visited: set[str]              = set()
        self.queue:   deque[tuple[str,int]] = deque()
        self._domain_counts: dict[str, int] = {}

        os.makedirs(output_dir, exist_ok=True)
        self.product_urls_path = os.path.join(output_dir, "product_urls.txt")
        open(self.product_urls_path, "w").close()
        self._product_url_count = 0
        self._skipped_count     = 0

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc.replace("www.", "")

    def _domain_limit_reached(self, url: str) -> bool:
        return self._domain_counts.get(self._get_domain(url), 0) >= self.max_pages_per_domain

    def _increment_domain(self, url: str):
        domain = self._get_domain(url)
        self._domain_counts[domain] = self._domain_counts.get(domain, 0) + 1

    def _should_skip(self, url: str) -> bool:
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in self.skip_urls)

    def _is_relevant_url(self, url: str) -> bool:
        """
        Определяем стоит ли вообще заходить на эту страницу.

        Логика:
        - Страница товара (/product/) — всегда релевантна, проверим содержимое
        - URL содержит relevant_url_parts — релевантна (это наш раздел каталога)
        - Остальное — только глубина 0 и 1 (навигация по сайту)

        Это позволяет стартовать с главной страницы и не уходить в
        ненужные разделы (наушники, планшеты и т.д.)
        """
        url_lower = url.lower()

        # Страница товара — всегда идём
        if "/product/" in url_lower or "/products/" in url_lower:
            return True

        # Нет ограничений по релевантности — идём везде
        if not self.relevant_url_parts:
            return True

        # URL содержит релевантную часть — идём
        return any(part in url_lower for part in self.relevant_url_parts)

    def _is_product_page(self, url: str, html: str) -> bool:
        from bs4 import BeautifulSoup

        url_patterns = ["/product/", "/products/", "/tovar/", "/item/"]
        if not any(p in url.lower() for p in url_patterns):
            return False

        if self.url_must_contain:
            if self.url_must_contain.lower() not in url.lower():
                return False

        if self.product_keywords:
            soup      = BeautifulSoup(html, "lxml")
            page_text = soup.get_text().lower()
            numbers   = [kw for kw in self.product_keywords if kw.isdigit()]
            colors    = [kw for kw in self.product_keywords if not kw.isdigit()]
            if not all(n in page_text for n in numbers):
                return False
            if colors and not any(c in page_text for c in colors):
                return False

        return True

    def _save_product_url(self, url: str):
        with open(self.product_urls_path, "a", encoding="utf-8") as f:
            f.write(url + "\n")
        self._product_url_count += 1
        logger.info(f"  📦 Товар найден! URL #{self._product_url_count}: {url}")

    def _log_domain_stats(self):
        logger.info("\n📊 Страниц обработано по доменам:")
        for domain, count in sorted(self._domain_counts.items()):
            bar = "█" * (count // 2)
            logger.info(f"  {domain:<30} {count:>3} {bar}")
        logger.info(f"\n  ⏭️  Пропущено по skip_urls: {self._skipped_count}")

    def run(self):
        logger.info(f"Старт краулера")
        logger.info(f"Seed URLs: {self.seed_urls}")
        logger.info(f"Ключевые слова: {self.product_keywords}")
        logger.info(f"Релевантные части URL: {self.relevant_url_parts}")
        logger.info(f"Лимит: {self.max_pages} всего / {self.max_pages_per_domain} на домен")

        for url in self.seed_urls:
            self.queue.append((url, 0))
            self.visited.add(url)

        while self.queue and self.storage.count < self.max_pages:
            url, depth = self.queue.popleft()

            if self._should_skip(url):
                self._skipped_count += 1
                continue

            if self._domain_limit_reached(url):
                continue

            logger.info(f"[{self.storage.count + 1}/{self.max_pages}] "
                       f"Глубина {depth} [{self._get_domain(url)}]: {url}")

            html = self.fetcher.fetch(url)
            if html is None:
                continue

            self._increment_domain(url)

            if self._is_product_page(url, html):
                self._save_product_url(url)

            data = self.parser.extract_data(html, url)
            self.storage.save(data)

            if depth < self.max_depth:
                links     = self.parser.extract_links(html, url)
                new_links = 0
                for link in links:
                    if link not in self.visited:
                        # Глубина 0-1: идём по всем ссылкам (навигация по сайту)
                        # Глубина 2+: только по релевантным (экономим лимит)
                        if depth < 2 or self._is_relevant_url(link):
                            self.visited.add(link)
                            self.queue.append((link, depth + 1))
                            new_links += 1
                logger.info(f"  → {len(links)} ссылок, {new_links} новых")

        self._log_domain_stats()
        logger.info(f"\n✅ Готово. Страниц обработано: {self.storage.count}")
        logger.info(f"Страниц товаров найдено: {self._product_url_count}")