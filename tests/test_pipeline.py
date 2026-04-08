from datetime import datetime, timezone
from unittest.mock import AsyncMock
from storage.models import Article
from core.pipeline import Pipeline


def make_articles(n: int) -> list[Article]:
    return [
        Article(
            title=f"Article {i}",
            url=f"https://example.com/{i}",
            source="Src",
            published_at=datetime(2026, 4, 8, i % 24, 0, tzinfo=timezone.utc),
            content=f"Content for article {i}",
        )
        for i in range(n)
    ]


async def test_pipeline_fetches_and_summarizes():
    mock_source = AsyncMock()
    mock_source.fetch = AsyncMock(return_value=make_articles(3))

    mock_llm = AsyncMock()
    mock_llm.summarize = AsyncMock(return_value="Summary of 3 articles")

    mock_db = AsyncMock()
    mock_db.get_cached_article = AsyncMock(return_value=None)
    mock_db.cache_article = AsyncMock()

    pipeline = Pipeline(llm=mock_llm, db=mock_db, max_articles=20, max_concurrency=5, cache_ttl=3600)
    summary, articles = await pipeline.run(sources=[mock_source], topic="ai")

    assert summary == "Summary of 3 articles"
    assert len(articles) == 3
    mock_llm.summarize.assert_called_once()


async def test_pipeline_deduplicates_by_url():
    articles_a = [
        Article(title="A", url="https://example.com/1", source="S1",
                published_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc), content="C1"),
        Article(title="B", url="https://example.com/2", source="S1",
                published_at=datetime(2026, 4, 8, 9, 0, tzinfo=timezone.utc), content="C2"),
    ]
    articles_b = [
        Article(title="A dup", url="https://example.com/1", source="S2",
                published_at=datetime(2026, 4, 8, 10, 0, tzinfo=timezone.utc), content="C1 dup"),
        Article(title="C", url="https://example.com/3", source="S2",
                published_at=datetime(2026, 4, 8, 8, 0, tzinfo=timezone.utc), content="C3"),
    ]

    source_a = AsyncMock()
    source_a.fetch = AsyncMock(return_value=articles_a)
    source_b = AsyncMock()
    source_b.fetch = AsyncMock(return_value=articles_b)

    mock_llm = AsyncMock()
    mock_llm.summarize = AsyncMock(return_value="Summary")
    mock_db = AsyncMock()
    mock_db.get_cached_article = AsyncMock(return_value=None)
    mock_db.cache_article = AsyncMock()

    pipeline = Pipeline(llm=mock_llm, db=mock_db, max_articles=20, max_concurrency=5, cache_ttl=3600)
    _, articles = await pipeline.run(sources=[source_a, source_b], topic="ai")

    urls = [a.url for a in articles]
    assert len(urls) == 3  # deduped
    assert len(set(urls)) == 3


async def test_pipeline_limits_max_articles():
    mock_source = AsyncMock()
    mock_source.fetch = AsyncMock(return_value=make_articles(30))

    mock_llm = AsyncMock()
    mock_llm.summarize = AsyncMock(return_value="Summary")
    mock_db = AsyncMock()
    mock_db.get_cached_article = AsyncMock(return_value=None)
    mock_db.cache_article = AsyncMock()

    pipeline = Pipeline(llm=mock_llm, db=mock_db, max_articles=10, max_concurrency=5, cache_ttl=3600)
    _, articles = await pipeline.run(sources=[mock_source], topic="ai")

    assert len(articles) == 10


async def test_pipeline_source_failure_continues():
    good_source = AsyncMock()
    good_source.fetch = AsyncMock(return_value=make_articles(2))
    bad_source = AsyncMock()
    bad_source.fetch = AsyncMock(side_effect=Exception("Network error"))

    mock_llm = AsyncMock()
    mock_llm.summarize = AsyncMock(return_value="Summary")
    mock_db = AsyncMock()
    mock_db.get_cached_article = AsyncMock(return_value=None)
    mock_db.cache_article = AsyncMock()

    pipeline = Pipeline(llm=mock_llm, db=mock_db, max_articles=20, max_concurrency=5, cache_ttl=3600)
    summary, articles = await pipeline.run(sources=[bad_source, good_source], topic="ai")

    assert len(articles) == 2
    assert summary == "Summary"


async def test_pipeline_all_sources_fail():
    bad_source = AsyncMock()
    bad_source.fetch = AsyncMock(side_effect=Exception("Fail"))

    mock_llm = AsyncMock()
    mock_db = AsyncMock()

    pipeline = Pipeline(llm=mock_llm, db=mock_db, max_articles=20, max_concurrency=5, cache_ttl=3600)
    summary, articles = await pipeline.run(sources=[bad_source], topic="ai")

    assert articles == []
    assert "不可用" in summary
