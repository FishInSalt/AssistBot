from unittest.mock import AsyncMock, patch, MagicMock
from sources.scraper import ScraperSource

SAMPLE_HTML = """
<html>
<head>
    <meta name="description" content="A great article about AI.">
    <meta property="og:description" content="OG description about AI advances.">
    <title>AI Advances in 2026</title>
</head>
<body>
    <article>
        <h1>AI Advances in 2026</h1>
        <p>First paragraph with important information about the topic.</p>
        <p>Second paragraph with more details about AI.</p>
    </article>
</body>
</html>
"""

def test_scraper_implements_base():
    from sources.base import BaseSource
    source = ScraperSource(name="Test", url="https://example.com", topics=["test"])
    assert isinstance(source, BaseSource)

async def test_scraper_extracts_content():
    source = ScraperSource(name="TestSite", url="https://example.com", topics=["ai"])
    mock_response = MagicMock()
    mock_response.text = SAMPLE_HTML
    mock_response.raise_for_status = MagicMock()
    with patch("sources.scraper.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        articles = await source.fetch()
    assert len(articles) == 1
    assert articles[0].title == "AI Advances in 2026"
    assert articles[0].source == "TestSite"

async def test_scraper_failure_returns_empty():
    source = ScraperSource(name="Bad", url="https://bad.example.com", topics=["test"])
    with patch("sources.scraper.httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client
        articles = await source.fetch()
    assert articles == []
