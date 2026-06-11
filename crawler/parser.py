from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import logging

logger = logging.getLogger(__name__)

class Parser:
    def __init__(self, allowed_domains: list[str] | None = None):
        self.allowed_domains = allowed_domains

    def _normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        normalized = parsed._replace(fragment="")
        return urlunparse(normalized)

    def _is_valid_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if self.allowed_domains:
            return any(
                parsed.netloc == domain or parsed.netloc.endswith(f".{domain}")
                for domain in self.allowed_domains
            )
        return True

    def extract_links(self, html: str, base_url: str) -> list[str]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if not href or href.startswith(("javascript:", "mailto:", "tel:")):
                continue
            absolute_url = urljoin(base_url, href)
            normalized = self._normalize_url(absolute_url)
            if self._is_valid_url(normalized):
                links.append(normalized)
        return links

    def extract_data(self, html: str, url: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        full_text = soup.get_text(separator=" ")
        full_text_lower = full_text.lower()

        search_words = ["iphone", "15", "black"]
        word_stats = {}

        for word in search_words:
            count = full_text_lower.count(word)
            contexts = []
            start = 0
            found = 0
            while found < 3:
                idx = full_text_lower.find(word, start)
                if idx == -1:
                    break
                snippet_start = max(0, idx - 50)
                snippet_end = min(len(full_text), idx + len(word) + 50)
                snippet = " ".join(full_text[snippet_start:snippet_end].split())
                contexts.append(snippet)
                start = idx + 1
                found += 1

            word_stats[word] = {"count": count, "contexts": contexts}

        return {
            "url": url,
            "title": soup.title.string.strip() if soup.title else None,
            "meta_description": self._get_meta(soup, "description"),
            "headings": {
                "h1": [h.get_text(strip=True) for h in soup.find_all("h1")],
                "h2": [h.get_text(strip=True) for h in soup.find_all("h2")],
            },
            "links_count": len(soup.find_all("a", href=True)),
            "images_count": len(soup.find_all("img")),
            "text_length": len(full_text),
            "word_stats": word_stats,
        }

    def _get_meta(self, soup: BeautifulSoup, name: str) -> str | None:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return None