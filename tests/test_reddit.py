from unittest.mock import AsyncMock, patch, MagicMock
from sources.reddit import RedditSource

SAMPLE_REDDIT_JSON = {
    "data": {
        "children": [
            {"data": {"title": "Big AI News", "url": "https://example.com/ai-news",
                      "selftext": "Some discussion about AI developments.",
                      "created_utc": 1744099200.0, "subreddit": "artificial",
                      "permalink": "/r/artificial/comments/abc123/big_ai_news/", "is_self": False}},
            {"data": {"title": "Self Post Discussion", "url": "https://reddit.com/r/artificial/...",
                      "selftext": "What do you think about the latest model?",
                      "created_utc": 1744095600.0, "subreddit": "artificial",
                      "permalink": "/r/artificial/comments/def456/self_post/", "is_self": True}},
        ]
    }
}

def test_reddit_source_implements_base():
    from sources.base import BaseSource
    source = RedditSource(subreddit="artificial", topics=["ai"])
    assert isinstance(source, BaseSource)

async def test_reddit_parse_posts():
    source = RedditSource(subreddit="artificial", topics=["ai"])
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_REDDIT_JSON
    mock_response.raise_for_status = MagicMock()
    with patch("sources.reddit.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        articles = await source.fetch()
    assert len(articles) == 2
    assert articles[0].title == "Big AI News"
    assert articles[0].source == "Reddit r/artificial"
    assert articles[0].language == "en"

async def test_reddit_fetch_failure_returns_empty():
    source = RedditSource(subreddit="bad", topics=["test"])
    with patch("sources.reddit.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        articles = await source.fetch()
    assert articles == []
