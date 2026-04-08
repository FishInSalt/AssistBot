from datetime import datetime, timezone
from unittest.mock import AsyncMock
from core.conversation import ConversationManager
from storage.models import ChatMessage


async def test_new_session_created():
    mock_db = AsyncMock()
    mock_db.get_active_session = AsyncMock(return_value=None)
    mock_db.save_session = AsyncMock()
    mock_db.add_message = AsyncMock()
    mock_db.get_messages = AsyncMock(return_value=[])

    mgr = ConversationManager(db=mock_db, session_timeout=600)
    session = await mgr.get_or_create_session(chat_id=123, topic="ai", articles_json="[]")

    assert session.topic == "ai"
    assert session.chat_id == 123
    mock_db.save_session.assert_called_once()


async def test_existing_session_reused():
    mock_db = AsyncMock()
    mock_db.get_active_session = AsyncMock(return_value={
        "id": "existing-id",
        "chat_id": 123,
        "topic": "ai",
        "articles": "[]",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    mock_db.touch_session = AsyncMock()
    mock_db.get_messages = AsyncMock(return_value=[])

    mgr = ConversationManager(db=mock_db, session_timeout=600)
    session = await mgr.get_or_create_session(chat_id=123, topic="ai", articles_json="[]")

    assert session.id == "existing-id"
    mock_db.save_session.assert_not_called()


async def test_expired_session_creates_new():
    mock_db = AsyncMock()
    mock_db.get_active_session = AsyncMock(return_value={
        "id": "old-id",
        "chat_id": 123,
        "topic": "ai",
        "articles": "[]",
        "updated_at": "2020-01-01T00:00:00+00:00",
    })
    mock_db.save_session = AsyncMock()
    mock_db.add_message = AsyncMock()
    mock_db.get_messages = AsyncMock(return_value=[])

    mgr = ConversationManager(db=mock_db, session_timeout=600)
    session = await mgr.get_or_create_session(chat_id=123, topic="ai", articles_json="[]")

    assert session.id != "old-id"
    mock_db.save_session.assert_called_once()


async def test_different_topic_creates_new():
    mock_db = AsyncMock()
    mock_db.get_active_session = AsyncMock(return_value={
        "id": "old-id",
        "chat_id": 123,
        "topic": "tech",
        "articles": "[]",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    mock_db.save_session = AsyncMock()
    mock_db.add_message = AsyncMock()
    mock_db.get_messages = AsyncMock(return_value=[])

    mgr = ConversationManager(db=mock_db, session_timeout=600)
    session = await mgr.get_or_create_session(chat_id=123, topic="ai", articles_json="[]")

    assert session.topic == "ai"
    assert session.id != "old-id"


async def test_add_and_get_messages():
    mock_db = AsyncMock()
    mock_db.add_message = AsyncMock()
    mock_db.get_messages = AsyncMock(return_value=[
        {"role": "user", "content": "hello", "created_at": "2026-04-08T10:00:00"},
        {"role": "assistant", "content": "hi", "created_at": "2026-04-08T10:00:01"},
    ])
    mock_db.touch_session = AsyncMock()

    mgr = ConversationManager(db=mock_db, session_timeout=600, llm=None)
    await mgr.add_message(session_id="s1", role="user", content="hello")

    messages = await mgr.get_context(session_id="s1", max_messages=10)
    assert len(messages) == 2
    assert messages[0].role == "user"
