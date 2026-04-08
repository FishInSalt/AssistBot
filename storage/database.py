from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite

from storage.models import Article


class Database:
    def __init__(self, db_path: str = "assistbot.db"):
        self._path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS custom_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                topics TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, url)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                articles TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS article_cache (
                url TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                language TEXT,
                published_at TIMESTAMP,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    async def _execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        return await self._conn.execute(sql, params)

    async def _commit(self) -> None:
        await self._conn.commit()

    # --- Article Cache ---

    async def cache_article(self, article: Article) -> None:
        await self._execute(
            """INSERT OR REPLACE INTO article_cache
               (url, title, source, content, summary, language, published_at, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (article.url, article.title, article.source, article.content,
             article.summary, article.language,
             article.published_at.isoformat() if article.published_at else None,
             datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")),
        )
        await self._commit()

    async def get_cached_article(self, url: str, cache_ttl: int = 0) -> Article | None:
        if cache_ttl > 0:
            cursor = await self._execute(
                """SELECT * FROM article_cache
                   WHERE url = ? AND datetime(cached_at) > datetime('now', ? || ' seconds')""",
                (url, str(-cache_ttl)),
            )
        else:
            cursor = await self._execute("SELECT * FROM article_cache WHERE url = ?", (url,))
        row = await cursor.fetchone()
        if row is None:
            return None
        published_at = datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
        return Article(
            title=row["title"],
            url=row["url"],
            source=row["source"],
            content=row["content"],
            language=row["language"],
            published_at=published_at,
            summary=row["summary"],
        )

    # --- Custom Feeds ---

    async def add_custom_feed(self, chat_id: int, name: str, url: str, topics: list[str]) -> None:
        await self._execute(
            "INSERT OR REPLACE INTO custom_feeds (chat_id, name, url, topics) VALUES (?, ?, ?, ?)",
            (chat_id, name, url, json.dumps(topics)),
        )
        await self._commit()

    async def remove_custom_feed(self, chat_id: int, url: str) -> bool:
        cursor = await self._execute(
            "DELETE FROM custom_feeds WHERE chat_id = ? AND url = ?",
            (chat_id, url),
        )
        await self._commit()
        return cursor.rowcount > 0

    async def get_custom_feeds(self, chat_id: int) -> list[dict]:
        cursor = await self._execute(
            "SELECT name, url, topics FROM custom_feeds WHERE chat_id = ?",
            (chat_id,),
        )
        rows = await cursor.fetchall()
        return [{"name": r["name"], "url": r["url"], "topics": json.loads(r["topics"])} for r in rows]

    # --- Sessions ---

    async def save_session(self, session_id: str, chat_id: int, topic: str, articles_json: str) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")
        await self._execute(
            """INSERT OR REPLACE INTO sessions (id, chat_id, topic, articles, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, chat_id, topic, articles_json, now, now),
        )
        await self._commit()

    async def get_active_session(self, chat_id: int) -> dict | None:
        cursor = await self._execute(
            "SELECT * FROM sessions WHERE chat_id = ? ORDER BY updated_at DESC LIMIT 1",
            (chat_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def touch_session(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S+00:00")
        await self._execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        await self._commit()

    # --- Messages ---

    async def add_message(self, session_id: str, role: str, content: str) -> None:
        await self._execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        await self._commit()

    async def get_messages(self, session_id: str) -> list[dict]:
        cursor = await self._execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
