from __future__ import annotations
import logging
from datetime import datetime, timezone
import httpx
from sources.base import BaseSource
from storage.models import Article

logger = logging.getLogger(__name__)
REDDIT_USER_AGENT = "AssistBot/1.0 (news aggregator)"

class RedditSource(BaseSource):
    def __init__(self, subreddit: str, topics: list[str]):
        super().__init__(name=f"Reddit r/{subreddit}", topics=topics)
        self.subreddit = subreddit

    async def fetch(self) -> list[Article]:
        url = f"https://www.reddit.com/r/{self.subreddit}/hot.json?limit=25"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers={"User-Agent": REDDIT_USER_AGENT})
                response.raise_for_status()
        except Exception:
            logger.warning("Reddit fetch failed for r/%s", self.subreddit)
            return []
        data = response.json()
        articles = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
            content = post.get("selftext", "")
            link = post.get("url", "")
            if post.get("is_self"):
                link = f"https://reddit.com{post.get('permalink', '')}"
            articles.append(Article(
                title=post.get("title", ""),
                url=link,
                source=self.name,
                published_at=created,
                content=content or post.get("title", ""),
                language="en",
            ))
        return articles
