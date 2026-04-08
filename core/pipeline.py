from __future__ import annotations

import asyncio
import logging
from core.preprocessor import Preprocessor
from llm.base import BaseLLM
from sources.base import BaseSource
from storage.database import Database
from storage.models import Article

logger = logging.getLogger(__name__)


LEVEL3_THRESHOLD = 50  # If extracted content is shorter than this, trigger Level 3 LLM summary


class Pipeline:
    def __init__(self, llm: BaseLLM, db: Database, max_articles: int = 20,
                 max_concurrency: int = 5, cache_ttl: int = 3600):
        self._llm = llm
        self._db = db
        self._max_articles = max_articles
        self._cache_ttl = cache_ttl
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._preprocessor = Preprocessor()

    async def run(self, sources: list[BaseSource], topic: str) -> tuple[str, list[Article]]:
        # Fetch from all sources concurrently
        articles = await self._fetch_all(sources)

        if not articles:
            return "数据源暂时不可用，请稍后再试。", []

        # Dedup by URL
        seen: set[str] = set()
        unique: list[Article] = []
        for a in articles:
            if a.url not in seen:
                seen.add(a.url)
                unique.append(a)

        # Sort by published_at descending, limit
        unique.sort(key=lambda a: a.published_at, reverse=True)
        unique = unique[: self._max_articles]

        # Preprocess articles (3-level)
        for article in unique:
            cached = await self._db.get_cached_article(article.url, cache_ttl=self._cache_ttl)
            if cached and cached.summary:
                article.summary = cached.summary
            else:
                # Level 1 & 2: preprocessor
                original_content = article.content
                extracted = self._preprocessor.extract(article)
                article.content = extracted

                # Level 3: if extracted content is too short but original was substantial, use LLM
                if len(extracted) < LEVEL3_THRESHOLD and len(original_content) > LEVEL3_THRESHOLD:
                    try:
                        article.summary = await self._llm.summarize_single(article)
                    except Exception:
                        logger.warning("Level 3 LLM summary failed for %s", article.url)

                await self._db.cache_article(article)

        # Summarize with LLM
        try:
            summary = await self._llm.summarize(unique, topic)
        except Exception:
            logger.error("LLM summarize failed", exc_info=True)
            summary = self._fallback_summary(unique, topic)

        return summary, unique

    async def _fetch_all(self, sources: list[BaseSource]) -> list[Article]:
        async def fetch_one(source: BaseSource) -> list[Article]:
            async with self._semaphore:
                try:
                    return await source.fetch()
                except Exception:
                    logger.warning("Source %s failed", source.name, exc_info=True)
                    return []

        results = await asyncio.gather(*[fetch_one(s) for s in sources])
        all_articles: list[Article] = []
        for batch in results:
            all_articles.extend(batch)
        return all_articles

    def _fallback_summary(self, articles: list[Article], topic: str) -> str:
        lines = [f"📋 【{topic} 最新资讯】\n"]
        for i, a in enumerate(articles[:10], 1):
            lines.append(f"{i}. {a.title}\n   🔗 {a.url}\n")
        lines.append("\n⚠️ LLM 分析暂不可用，以上为原始文章列表。")
        return "\n".join(lines)
