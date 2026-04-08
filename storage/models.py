from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Article:
    title: str
    url: str
    source: str
    published_at: datetime
    content: str
    language: str = "zh"
    summary: str | None = None


@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Session:
    id: str
    chat_id: int
    topic: str
    articles: list[Article] = field(default_factory=list)
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, timeout_seconds: int) -> bool:
        elapsed = (datetime.now(timezone.utc) - self.updated_at).total_seconds()
        return elapsed > timeout_seconds

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
