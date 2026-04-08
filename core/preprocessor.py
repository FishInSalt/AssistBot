from __future__ import annotations
import logging
from bs4 import BeautifulSoup
from storage.models import Article

logger = logging.getLogger(__name__)

class Preprocessor:
    """Three-level article content extraction."""
    def extract(self, article: Article) -> str:
        content = article.content
        if not content:
            return ""
        if not self._looks_like_html(content):
            return content
        return self._structural_extract(content)

    def _looks_like_html(self, text: str) -> bool:
        return "<" in text and (">" in text) and any(
            tag in text.lower() for tag in ("<p", "<h1", "<h2", "<div", "<article")
        )

    def _structural_extract(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        parts: list[str] = []
        paragraphs = soup.find_all("p")
        for p in paragraphs[:2]:
            text = p.get_text(strip=True)
            if text:
                parts.append(text)
        for tag in soup.find_all(["h2", "h3", "strong", "b"]):
            text = tag.get_text(strip=True)
            if text and text not in parts:
                parts.append(text)
        if paragraphs:
            last_text = paragraphs[-1].get_text(strip=True)
            if last_text and last_text not in parts:
                parts.append(last_text)
        return "\n\n".join(parts) if parts else soup.get_text(strip=True)
