from __future__ import annotations
import logging
from datetime import datetime, timezone
import httpx
from bs4 import BeautifulSoup
from sources.base import BaseSource
from storage.models import Article

logger = logging.getLogger(__name__)

class ScraperSource(BaseSource):
    def __init__(self, name: str, url: str, topics: list[str]):
        super().__init__(name=name, topics=topics)
        self.url = url

    async def fetch(self) -> list[Article]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
        except Exception:
            logger.warning("Scraper fetch failed for %s (%s)", self.name, self.url)
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        title = self._extract_title(soup)
        content = self._extract_content(soup)
        return [Article(
            title=title, url=self.url, source=self.name,
            published_at=datetime.now(timezone.utc), content=content,
        )]

    def _extract_title(self, soup: BeautifulSoup) -> str:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"]
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return self.url

    def _extract_content(self, soup: BeautifulSoup) -> str:
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content") and len(og_desc["content"]) > 100:
            return og_desc["content"]
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content") and len(meta_desc["content"]) > 100:
            return meta_desc["content"]
        article = soup.find("article") or soup.find("body")
        if article:
            paragraphs = article.find_all("p")
            text_parts = [p.get_text(strip=True) for p in paragraphs[:5] if p.get_text(strip=True)]
            return "\n\n".join(text_parts)
        return ""
