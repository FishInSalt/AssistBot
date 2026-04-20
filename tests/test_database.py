import pytest
from datetime import datetime, timezone
from storage.models import Article


async def test_cache_article_and_retrieve(db):
    article = Article(
        title="Test Article",
        url="https://example.com/1",
        source="TestSource",
        published_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
        content="Some content",
        language="zh",
        summary="A test summary",
    )
    await db.cache_article(article)
    cached = await db.get_cached_article("https://example.com/1")
    assert cached is not None
    assert cached.title == "Test Article"
    assert cached.summary == "A test summary"


async def test_get_cached_article_miss(db):
    cached = await db.get_cached_article("https://nonexistent.com")
    assert cached is None


async def test_cache_article_upsert(db):
    article = Article(
        title="Original",
        url="https://example.com/1",
        source="Src",
        published_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
        content="Content",
    )
    await db.cache_article(article)
    article.summary = "New summary"
    await db.cache_article(article)
    cached = await db.get_cached_article("https://example.com/1")
    assert cached.summary == "New summary"


async def test_cache_ttl_expired(db):
    """Cached article with expired TTL should return None."""
    article = Article(
        title="Old",
        url="https://example.com/old",
        source="Src",
        published_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
        content="Content",
    )
    await db.cache_article(article)
    # Manually set cached_at to old timestamp
    await db._execute(
        "UPDATE article_cache SET cached_at = '2020-01-01T00:00:00' WHERE url = ?",
        ("https://example.com/old",),
    )
    await db._commit()
    cached = await db.get_cached_article("https://example.com/old", cache_ttl=3600)
    assert cached is None


async def test_save_and_get_custom_feed(db):
    await db.add_custom_feed(chat_id=123, name="MyFeed", url="https://example.com/rss", topics=["ai"])
    feeds = await db.get_custom_feeds(chat_id=123)
    assert len(feeds) == 1
    assert feeds[0]["name"] == "MyFeed"
    assert feeds[0]["topics"] == ["ai"]


async def test_remove_custom_feed(db):
    await db.add_custom_feed(chat_id=123, name="MyFeed", url="https://example.com/rss", topics=["ai"])
    removed = await db.remove_custom_feed(chat_id=123, url="https://example.com/rss")
    assert removed is True
    feeds = await db.get_custom_feeds(chat_id=123)
    assert len(feeds) == 0


async def test_save_and_load_session(db):
    await db.save_session(
        session_id="s1",
        chat_id=123,
        topic="ai",
        articles_json='[{"title":"t1"}]',
    )
    session_row = await db.get_active_session(chat_id=123)
    assert session_row is not None
    assert session_row["topic"] == "ai"


async def test_save_and_load_messages(db):
    await db.save_session(session_id="s1", chat_id=123, topic="ai", articles_json="[]")
    await db.add_message(session_id="s1", role="user", content="hello")
    await db.add_message(session_id="s1", role="assistant", content="hi")
    messages = await db.get_messages(session_id="s1")
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
