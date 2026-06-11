import requests
import time
import logging
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class Fetcher:
    def __init__(self, delay: float = 1.0, timeout: int = 10):
        self.delay   = delay
        self.timeout = timeout
        self._last_request_time = 0

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "ru-RU,ru;q=0.9",
        })

        self._robots_cache: dict[str, RobotFileParser] = {}

    def _get_robots(self, url: str) -> RobotFileParser:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self._robots_cache:
            robots_url = f"{domain}/robots.txt"
            rp = RobotFileParser()
            try:
                resp = self.session.get(robots_url, timeout=5)
                rp.parse(resp.text.splitlines())
            except Exception as e:
                logger.warning(f"Не удалось загрузить robots.txt: {e}")
            self._robots_cache[domain] = rp

        return self._robots_cache[domain]

    def is_allowed(self, url: str) -> bool:
        try:
            rp = self._get_robots(url)
            return rp.can_fetch(self.session.headers["User-Agent"], url)
        except Exception:
            return True

    def _wait(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def fetch(self, url: str) -> str | None:
        logger.info(f"  → Проверяю robots.txt...")
        if not self.is_allowed(url):
            logger.info(f"  → Запрещено robots.txt: {url}")
            return None

        logger.info(f"  → Делаю запрос...")
        self._wait()

        # Три попытки с экспоненциальной задержкой: 5с → 10с → 20с
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                self._last_request_time = time.time()
                response.raise_for_status()

                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type:
                    logger.info(f"  → Пропускаю не-HTML: {url}")
                    return None

                return response.text

            except requests.RequestException as e:
                # Последняя попытка — просто логируем и уходим
                if attempt == max_retries - 1:
                    logger.warning(f"  → Ошибка после {max_retries} попыток: {e}")
                    return None

                # Экспоненциальная задержка: 5с, 10с, 20с
                wait_time = 5 * (2 ** attempt)
                logger.warning(
                    f"  → Попытка {attempt + 1}/{max_retries} не удалась: {e}. "
                    f"Повтор через {wait_time}с..."
                )
                time.sleep(wait_time)

        return None