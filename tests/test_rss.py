from unittest.mock import AsyncMock, patch, MagicMock
from sources.rss import RSSSource

SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
    <title>Test Feed</title>
    <item>
        <title>Article One</title>
        <link>https://example.com/1</link>
        <description>First article description that is long enough to be useful for summarization purposes and testing.</description>
        <pubDate>Tue, 08 Apr 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
        <title>Article Two</title>
        <link>https://example.com/2</link>
        <description>Second article short desc.</description>
        <pubDate>Tue, 08 Apr 2026 09:00:00 GMT</pubDate>
    </item>
</channel>
</rss>"""

def test_rss_source_implements_base():
    from sources.base import BaseSource
    source = RSSSource(name="Test", url="https://example.com/rss", topics=["test"])
    assert isinstance(source, BaseSource)

async def test_rss_parse_articles():
    source = RSSSource(name="TestFeed", url="https://example.com/rss", topics=["test"])
    mock_response = MagicMock()
    mock_response.text = SAMPLE_FEED
    mock_response.raise_for_status = MagicMock()
    with patch("sources.rss.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        articles = await source.fetch()
    assert len(articles) == 2
    assert articles[0].title == "Article One"
    assert articles[0].source == "TestFeed"
    assert articles[0].url == "https://example.com/1"
    assert "First article" in articles[0].content

async def test_rss_fetch_failure_returns_empty():
    source = RSSSource(name="Bad", url="https://bad.example.com/rss", topics=["test"])
    with patch("sources.rss.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        articles = await source.fetch()
    assert articles == []
