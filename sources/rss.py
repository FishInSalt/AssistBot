from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import feedparser
import httpx
from sources.base import BaseSource
from storage.models import Article

logger = logging.getLogger(__name__)

class RSSSource(BaseSource):
    def __init__(self, name: str, url: str, topics: list[str]):
        super().__init__(name=name, topics=topics)
        self.url = url

    async def fetch(self) -> list[Article]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
        except Exception:
            logger.warning("RSS fetch failed for %s (%s)", self.name, self.url)
            return []
        feed = await asyncio.to_thread(feedparser.parse, response.text)
        articles = []
        for entry in feed.entries:
            published_at = self._parse_date(entry)
            content = entry.get("summary", "") or entry.get("description", "")
            articles.append(Article(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                source=self.name,
                published_at=published_at,
                content=content,
                language=self._detect_language(content),
            ))
        return articles

    def _parse_date(self, entry) -> datetime:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime
            return datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
        if hasattr(entry, "published") and entry.published:
            try:
                return parsedate_to_datetime(entry.published)
            except Exception:
                pass
        return datetime.now(timezone.utc)

    def _detect_language(self, text: str) -> str:
        if not text:
            return "zh"
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        return "zh" if chinese_chars / max(len(text), 1) > 0.1 else "en"
