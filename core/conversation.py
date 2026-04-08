from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from storage.database import Database
from storage.models import ChatMessage, Session

logger = logging.getLogger(__name__)

MAX_CONTEXT_MESSAGES = 10
MAX_CONTEXT_TOKENS_ESTIMATE = 4000  # ~4 chars per token for Chinese


class ConversationManager:
    def __init__(self, db: Database, session_timeout: int = 600, llm=None):
        self._db = db
        self._timeout = session_timeout
        self._llm = llm  # For context compression

    async def get_or_create_session(
        self, chat_id: int, topic: str, articles_json: str
    ) -> Session:
        existing = await self._db.get_active_session(chat_id)

        if existing:
            updated_at = datetime.fromisoformat(existing["updated_at"])
            elapsed = (datetime.now(timezone.utc) - updated_at).total_seconds()
            same_topic = existing["topic"] == topic
            not_expired = elapsed <= self._timeout

            if same_topic and not_expired:
                await self._db.touch_session(existing["id"])
                return Session(
                    id=existing["id"],
                    chat_id=chat_id,
                    topic=existing["topic"],
                    updated_at=updated_at,
                )

        # Create new session
        session_id = str(uuid.uuid4())
        await self._db.save_session(
            session_id=session_id,
            chat_id=chat_id,
            topic=topic,
            articles_json=articles_json,
        )
        return Session(id=session_id, chat_id=chat_id, topic=topic)

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        await self._db.add_message(session_id=session_id, role=role, content=content)
        await self._db.touch_session(session_id)

    async def get_context(self, session_id: str, max_messages: int = MAX_CONTEXT_MESSAGES) -> list[ChatMessage]:
        rows = await self._db.get_messages(session_id)
        messages = [
            ChatMessage(role=r["role"], content=r["content"])
            for r in rows
        ]

        # Check if compression is needed (by count or estimated token size)
        total_chars = sum(len(m.content) for m in messages)
        estimated_tokens = total_chars // 4
        needs_compression = len(messages) > max_messages or estimated_tokens > MAX_CONTEXT_TOKENS_ESTIMATE

        if needs_compression and self._llm and len(messages) > 2:
            # Compress older messages, keep recent ones
            split = max(len(messages) - 4, 1)  # Keep last 4 messages
            old_messages = messages[:split]
            recent_messages = messages[split:]
            try:
                compressed = await self._llm.compress_context(old_messages)
                return [ChatMessage(role="assistant", content=f"[对话摘要] {compressed}")] + recent_messages
            except Exception:
                logger.warning("Context compression failed, falling back to truncation")

        # Fallback: simple truncation
        if len(messages) > max_messages:
            messages = messages[-max_messages:]
        return messages

    async def has_active_session(self, chat_id: int) -> bool:
        existing = await self._db.get_active_session(chat_id)
        if not existing:
            return False
        updated_at = datetime.fromisoformat(existing["updated_at"])
        elapsed = (datetime.now(timezone.utc) - updated_at).total_seconds()
        return elapsed <= self._timeout
