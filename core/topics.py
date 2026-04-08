from __future__ import annotations

import logging
from sources.base import BaseSource
from sources.rss import RSSSource
from sources.reddit import RedditSource
from config import SourcesConfig

logger = logging.getLogger(__name__)

# Chinese keyword → topic tag mapping
KEYWORD_MAP: dict[str, list[str]] = {
    "ai": ["ai", "AI", "人工智能", "机器学习", "深度学习", "大模型", "LLM", "GPT", "Claude"],
    "tech": ["科技", "技术", "tech", "互联网", "数码", "编程"],
    "international": ["国际", "世界", "全球", "地缘", "外交", "international", "world"],
    "general": ["综合", "热点", "热榜", "general"],
}


class TopicMatcher:
    def __init__(self, sources_config: SourcesConfig, llm):
        self._sources_config = sources_config
        self._llm = llm
        self._all_topics = self._collect_topics()

    def _collect_topics(self) -> set[str]:
        topics: set[str] = set()
        for rss in self._sources_config.rss:
            topics.update(rss.topics)
        for reddit in self._sources_config.reddit:
            topics.update(reddit.topics)
        return topics

    def available_topics(self) -> list[str]:
        return sorted(self._all_topics)

    def add_custom_topics(self, custom_feeds: list[dict]) -> None:
        for feed in custom_feeds:
            self._all_topics.update(feed["topics"])

    async def match(self, user_input: str) -> str | None:
        # Level 1: keyword matching
        user_lower = user_input.lower()
        for topic, keywords in KEYWORD_MAP.items():
            if topic not in self._all_topics:
                continue
            for kw in keywords:
                if kw.lower() in user_lower:
                    return topic

        # Level 2: LLM fallback
        if self._llm:
            try:
                result = await self._llm.extract_topic(user_input, list(self._all_topics))
                if result:
                    return result
            except Exception:
                logger.warning("LLM topic extraction failed", exc_info=True)

        return None

    def get_sources_for_topic(self, topic: str, custom_feeds: list[dict] | None = None) -> list[BaseSource]:
        sources: list[BaseSource] = []
        for rss in self._sources_config.rss:
            if topic in rss.topics:
                sources.append(RSSSource(name=rss.name, url=rss.url, topics=rss.topics))
        for reddit in self._sources_config.reddit:
            if topic in reddit.topics:
                sources.append(RedditSource(subreddit=reddit.subreddit, topics=reddit.topics))
        # Include user's custom feeds that match the topic
        if custom_feeds:
            for feed in custom_feeds:
                if topic in feed["topics"]:
                    sources.append(RSSSource(name=feed["name"], url=feed["url"], topics=feed["topics"]))
        return sources
