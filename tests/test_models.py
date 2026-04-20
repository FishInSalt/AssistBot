from datetime import datetime, timezone
from storage.models import Article, Session, ChatMessage


def test_article_creation():
    article = Article(
        title="Test Title",
        url="https://example.com/1",
        source="TestSource",
        published_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
        content="Some content here",
        language="zh",
    )
    assert article.title == "Test Title"
    assert article.language == "zh"


def test_article_default_language():
    article = Article(
        title="Test",
        url="https://example.com/2",
        source="TestSource",
        published_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
        content="Content",
    )
    assert article.language == "zh"


def test_session_creation():
    session = Session(
        id="test-uuid",
        chat_id=12345,
        topic="ai",
    )
    assert session.id == "test-uuid"
    assert session.articles == []
    assert session.is_expired(timeout_seconds=600) is False


def test_session_expired():
    session = Session(
        id="test-uuid",
        chat_id=12345,
        topic="ai",
        updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    assert session.is_expired(timeout_seconds=600) is True


def test_chat_message_creation():
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
