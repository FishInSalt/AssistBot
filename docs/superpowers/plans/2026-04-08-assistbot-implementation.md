# AssistBot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram bot that aggregates news from multiple sources and uses LLM to generate Chinese-language summaries with conversational follow-up.

**Architecture:** Single-process Python async app. Telegram bot receives messages, routes them through a pipeline that fetches from data sources (RSS/Reddit/scraper), preprocesses articles, and uses a configurable LLM backend to generate summaries. SQLite stores sessions, article cache, and custom feeds.

**Tech Stack:** Python 3.11+, python-telegram-bot, feedparser, httpx, beautifulsoup4, anthropic SDK (async), openai SDK (async), aiosqlite, PyYAML, pytest + pytest-asyncio

---

## File Structure

```
AssistBot/
├── main.py                    # Entry point: load config, init DB, start bot
├── config.py                  # Config loading (YAML + env vars)
├── config.example.yaml        # Example configuration
├── .gitignore                 # Ignore config.yaml, *.db, __pycache__, .env
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Test dependencies (pytest, pytest-asyncio)
├── storage/
│   ├── __init__.py
│   ├── models.py              # Dataclasses: Article, Session, Message
│   └── database.py            # SQLite operations (async via aiosqlite)
├── sources/
│   ├── __init__.py
│   ├── base.py                # Abstract base class for data sources
│   ├── rss.py                 # RSS/RSSHub source
│   ├── reddit.py              # Reddit JSON API source
│   └── scraper.py             # Web scraper fallback source
├── llm/
│   ├── __init__.py
│   ├── base.py                # Abstract base class for LLM providers
│   ├── claude.py              # Anthropic Claude implementation
│   └── openai_llm.py          # OpenAI implementation
├── core/
│   ├── __init__.py
│   ├── preprocessor.py        # 3-level article content extraction
│   ├── topics.py              # Topic matching (keyword + LLM fallback)
│   ├── pipeline.py            # Fetch → dedup → preprocess → summarize
│   └── conversation.py        # Session state machine + context management
├── bot/
│   ├── __init__.py
│   ├── client.py              # Telegram bot init + startup
│   └── handlers.py            # Command handlers + message routing
└── tests/
    ├── __init__.py
    ├── conftest.py             # Shared fixtures (tmp DB, mock config, fake articles)
    ├── test_models.py          # Article/Session/Message dataclass tests
    ├── test_database.py        # SQLite CRUD tests
    ├── test_config.py          # Config loading tests
    ├── test_rss.py             # RSS source tests
    ├── test_reddit.py          # Reddit source tests
    ├── test_scraper.py         # Scraper tests
    ├── test_preprocessor.py    # 3-level extraction tests
    ├── test_topics.py          # Topic matching tests
    ├── test_llm_base.py        # LLM base class + fallback tests
    ├── test_pipeline.py        # Pipeline integration tests
    ├── test_conversation.py    # Session state machine tests
    └── test_handlers.py        # Bot handler tests
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.gitignore`
- Create: `config.example.yaml`
- Create: `config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create requirements.txt**

```
python-telegram-bot>=21.0
feedparser>=6.0
httpx>=0.27
beautifulsoup4>=4.12
anthropic>=0.40
openai>=1.50
aiosqlite>=0.20
PyYAML>=6.0
```

- [ ] **Step 2: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.24
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
*.db
config.yaml
.env
.venv/
*.egg-info/
dist/
build/
.pytest_cache/
```

- [ ] **Step 4: Create config.example.yaml**

```yaml
telegram:
  # bot_token: set TELEGRAM_BOT_TOKEN env var
  allowed_users: []

llm:
  provider: "claude"
  # api_key: set LLM_API_KEY env var
  summary_model: "claude-haiku-4-5-20251001"
  analysis_model: "claude-sonnet-4-6"

sources:
  rss:
    - name: "机器之心"
      url: "https://www.jiqizhixin.com/rss"
      topics: ["ai"]
    - name: "36氪"
      url: "https://36kr.com/feed"
      topics: ["tech", "ai"]
    - name: "虎嗅"
      url: "https://www.huxiu.com/rss/0.xml"
      topics: ["tech"]
    - name: "少数派"
      url: "https://sspai.com/feed"
      topics: ["tech"]
    - name: "澎湃新闻"
      url: "https://rsshub.app/thepaper/newsDetail_channel/25950"
      topics: ["international"]
    - name: "知乎热榜"
      url: "https://rsshub.app/zhihu/hot"
      topics: ["general"]
  reddit:
    - subreddit: "artificial"
      topics: ["ai"]
    - subreddit: "worldnews"
      topics: ["international"]

db_path: "assistbot.db"
cache_ttl: 3600
max_articles: 20
session_timeout: 600
max_concurrency: 5
source_timeout: 15
```

- [ ] **Step 5: Write failing test for config loading**

Create `tests/__init__.py` (empty file) and `tests/conftest.py`:

```python
import os
import tempfile
import pytest

@pytest.fixture
def tmp_config_file():
    content = """
telegram:
  allowed_users: [111, 222]

llm:
  provider: "claude"
  summary_model: "claude-haiku-4-5-20251001"
  analysis_model: "claude-sonnet-4-6"

sources:
  rss:
    - name: "TestFeed"
      url: "https://example.com/rss"
      topics: ["test"]
  reddit:
    - subreddit: "test"
      topics: ["test"]

db_path: "test.db"
cache_ttl: 3600
max_articles: 20
session_timeout: 600
max_concurrency: 5
source_timeout: 15
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        f.flush()
        yield f.name
    os.unlink(f.name)
```

Create `tests/test_config.py`:

```python
import os
from config import load_config

def test_load_config_from_yaml(tmp_config_file):
    cfg = load_config(tmp_config_file)
    assert cfg.telegram.allowed_users == [111, 222]
    assert cfg.llm.provider == "claude"
    assert cfg.llm.summary_model == "claude-haiku-4-5-20251001"
    assert len(cfg.sources.rss) == 1
    assert cfg.sources.rss[0].name == "TestFeed"
    assert cfg.cache_ttl == 3600
    assert cfg.max_concurrency == 5

def test_env_vars_override_secrets(tmp_config_file, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("LLM_API_KEY", "test-key-456")
    cfg = load_config(tmp_config_file)
    assert cfg.telegram.bot_token == "test-token-123"
    assert cfg.llm.api_key == "test-key-456"

def test_missing_env_vars_returns_none(tmp_config_file, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    cfg = load_config(tmp_config_file)
    assert cfg.telegram.bot_token is None
    assert cfg.llm.api_key is None
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 7: Implement config.py**

```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RSSSource:
    name: str
    url: str
    topics: list[str]


@dataclass
class RedditSource:
    subreddit: str
    topics: list[str]


@dataclass
class SourcesConfig:
    rss: list[RSSSource] = field(default_factory=list)
    reddit: list[RedditSource] = field(default_factory=list)


@dataclass
class TelegramConfig:
    bot_token: str | None = None
    allowed_users: list[int] = field(default_factory=list)


@dataclass
class LLMConfig:
    provider: str = "claude"
    api_key: str | None = None
    summary_model: str = "claude-haiku-4-5-20251001"
    analysis_model: str = "claude-sonnet-4-6"


@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    db_path: str = "assistbot.db"
    cache_ttl: int = 3600
    max_articles: int = 20
    session_timeout: int = 600
    max_concurrency: int = 5
    source_timeout: int = 15


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)

    telegram_raw = raw.get("telegram", {})
    telegram = TelegramConfig(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", telegram_raw.get("bot_token")),
        allowed_users=telegram_raw.get("allowed_users", []),
    )

    llm_raw = raw.get("llm", {})
    llm = LLMConfig(
        provider=llm_raw.get("provider", "claude"),
        api_key=os.environ.get("LLM_API_KEY", llm_raw.get("api_key")),
        summary_model=llm_raw.get("summary_model", "claude-haiku-4-5-20251001"),
        analysis_model=llm_raw.get("analysis_model", "claude-sonnet-4-6"),
    )

    sources_raw = raw.get("sources", {})
    rss_list = [RSSSource(**s) for s in sources_raw.get("rss", [])]
    reddit_list = [RedditSource(**s) for s in sources_raw.get("reddit", [])]
    sources = SourcesConfig(rss=rss_list, reddit=reddit_list)

    return AppConfig(
        telegram=telegram,
        llm=llm,
        sources=sources,
        db_path=raw.get("db_path", "assistbot.db"),
        cache_ttl=raw.get("cache_ttl", 3600),
        max_articles=raw.get("max_articles", 20),
        session_timeout=raw.get("session_timeout", 600),
        max_concurrency=raw.get("max_concurrency", 5),
        source_timeout=raw.get("source_timeout", 15),
    )
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 9: Commit**

```bash
git add requirements.txt requirements-dev.txt .gitignore config.example.yaml config.py tests/
git commit -m "feat: project scaffolding with config loading and tests"
```

---

### Task 2: Data Models

**Files:**
- Create: `storage/__init__.py`
- Create: `storage/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for data models**

Create `storage/__init__.py` (empty file).

Create `tests/test_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'storage.models'`

- [ ] **Step 3: Implement storage/models.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_models.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add storage/ tests/test_models.py
git commit -m "feat: add Article, Session, ChatMessage data models"
```

---

### Task 3: Database Layer

**Files:**
- Create: `storage/database.py`
- Create: `tests/test_database.py`
- Modify: `tests/conftest.py` (add DB fixture)

- [ ] **Step 1: Add DB fixture to conftest.py**

Append to `tests/conftest.py`:

```python
from storage.database import Database

@pytest.fixture
async def db(tmp_path):
    db_path = tmp_path / "test.db"
    database = Database(str(db_path))
    await database.init()
    yield database
    await database.close()
```

Also create `pyproject.toml` (or add to conftest) for pytest-asyncio config:

```python
# Add to conftest.py top
import pytest
pytest_plugins = ['pytest_asyncio']
```

Create `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Write failing tests for database**

Create `tests/test_database.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'storage.database'`

- [ ] **Step 4: Implement storage/database.py**

```python
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
             datetime.now(timezone.utc).isoformat()),
        )
        await self._commit()

    async def get_cached_article(self, url: str, cache_ttl: int = 0) -> Article | None:
        if cache_ttl > 0:
            cursor = await self._execute(
                """SELECT * FROM article_cache
                   WHERE url = ? AND cached_at > datetime('now', ? || ' seconds')""",
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
            "INSERT INTO custom_feeds (chat_id, name, url, topics) VALUES (?, ?, ?, ?)",
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
        now = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_database.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add storage/database.py tests/test_database.py tests/conftest.py
git commit -m "feat: SQLite database layer with article cache, sessions, feeds"
```

---

### Task 4: Data Sources — Base Class + RSS

**Files:**
- Create: `sources/__init__.py`
- Create: `sources/base.py`
- Create: `sources/rss.py`
- Create: `tests/test_rss.py`

- [ ] **Step 1: Write failing tests for RSS source**

Create `sources/__init__.py` (empty file).

Create `tests/test_rss.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_rss.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sources.base'`

- [ ] **Step 3: Implement sources/base.py**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from storage.models import Article


class BaseSource(ABC):
    def __init__(self, name: str, topics: list[str]):
        self.name = name
        self.topics = topics

    @abstractmethod
    async def fetch(self) -> list[Article]:
        ...
```

- [ ] **Step 4: Implement sources/rss.py**

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

from sources.base import BaseSource
from storage.models import Article

logger = logging.getLogger(__name__)


class RSSSource(BaseSource):
    def __init__(self, name: str, url: str, topics: list[str]):
        super().__init__(name=name, topics=topics)
        self.url = url

    async def fetch(self) -> list[Article]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
        except Exception:
            logger.warning("RSS fetch failed for %s (%s)", self.name, self.url)
            return []

        feed = feedparser.parse(response.text)
        articles = []
        for entry in feed.entries:
            published_at = self._parse_date(entry)
            content = entry.get("summary", "") or entry.get("description", "")
            articles.append(Article(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                source=self.name,
                published_at=published_at,
                content=content,
                language=self._detect_language(content),
            ))
        return articles

    def _parse_date(self, entry) -> datetime:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            from time import mktime
            return datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
        if hasattr(entry, "published") and entry.published:
            try:
                return parsedate_to_datetime(entry.published)
            except Exception:
                pass
        return datetime.now(timezone.utc)

    def _detect_language(self, text: str) -> str:
        if not text:
            return "zh"
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        return "zh" if chinese_chars / max(len(text), 1) > 0.1 else "en"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_rss.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add sources/ tests/test_rss.py
git commit -m "feat: base source interface and RSS source implementation"
```

---

### Task 5: Data Sources — Reddit + Scraper

**Files:**
- Create: `sources/reddit.py`
- Create: `sources/scraper.py`
- Create: `tests/test_reddit.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: Write failing tests for Reddit source**

Create `tests/test_reddit.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
from sources.reddit import RedditSource

SAMPLE_REDDIT_JSON = {
    "data": {
        "children": [
            {
                "data": {
                    "title": "Big AI News",
                    "url": "https://example.com/ai-news",
                    "selftext": "Some discussion about AI developments.",
                    "created_utc": 1744099200.0,
                    "subreddit": "artificial",
                    "permalink": "/r/artificial/comments/abc123/big_ai_news/",
                    "is_self": False,
                }
            },
            {
                "data": {
                    "title": "Self Post Discussion",
                    "url": "https://reddit.com/r/artificial/...",
                    "selftext": "What do you think about the latest model?",
                    "created_utc": 1744095600.0,
                    "subreddit": "artificial",
                    "permalink": "/r/artificial/comments/def456/self_post/",
                    "is_self": True,
                }
            },
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
```

- [ ] **Step 2: Write failing tests for scraper**

Create `tests/test_scraper.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_reddit.py tests/test_scraper.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement sources/reddit.py**

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from sources.base import BaseSource
from storage.models import Article

logger = logging.getLogger(__name__)

REDDIT_USER_AGENT = "AssistBot/1.0 (news aggregator)"


class RedditSource(BaseSource):
    def __init__(self, subreddit: str, topics: list[str]):
        super().__init__(name=f"Reddit r/{subreddit}", topics=topics)
        self.subreddit = subreddit

    async def fetch(self) -> list[Article]:
        url = f"https://www.reddit.com/r/{self.subreddit}/hot.json?limit=25"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    url, headers={"User-Agent": REDDIT_USER_AGENT}
                )
                response.raise_for_status()
        except Exception:
            logger.warning("Reddit fetch failed for r/%s", self.subreddit)
            return []

        data = response.json()
        articles = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
            content = post.get("selftext", "")
            link = post.get("url", "")
            if post.get("is_self"):
                link = f"https://reddit.com{post.get('permalink', '')}"

            articles.append(Article(
                title=post.get("title", ""),
                url=link,
                source=self.name,
                published_at=created,
                content=content or post.get("title", ""),
                language="en",
            ))
        return articles
```

- [ ] **Step 5: Implement sources/scraper.py**

```python
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from sources.base import BaseSource
from storage.models import Article

logger = logging.getLogger(__name__)


class ScraperSource(BaseSource):
    def __init__(self, name: str, url: str, topics: list[str]):
        super().__init__(name=name, topics=topics)
        self.url = url

    async def fetch(self) -> list[Article]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(self.url)
                response.raise_for_status()
        except Exception:
            logger.warning("Scraper fetch failed for %s (%s)", self.name, self.url)
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        title = self._extract_title(soup)
        content = self._extract_content(soup)

        return [Article(
            title=title,
            url=self.url,
            source=self.name,
            published_at=datetime.now(timezone.utc),
            content=content,
        )]

    def _extract_title(self, soup: BeautifulSoup) -> str:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"]
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return self.url

    def _extract_content(self, soup: BeautifulSoup) -> str:
        # Try meta descriptions first
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content") and len(og_desc["content"]) > 100:
            return og_desc["content"]
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content") and len(meta_desc["content"]) > 100:
            return meta_desc["content"]

        # Fall back to article/body text
        article = soup.find("article") or soup.find("body")
        if article:
            paragraphs = article.find_all("p")
            text_parts = [p.get_text(strip=True) for p in paragraphs[:5] if p.get_text(strip=True)]
            return "\n\n".join(text_parts)
        return ""
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_reddit.py tests/test_scraper.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add sources/reddit.py sources/scraper.py tests/test_reddit.py tests/test_scraper.py
git commit -m "feat: Reddit and web scraper data sources"
```

---

### Task 6: Article Preprocessor

**Files:**
- Create: `core/__init__.py`
- Create: `core/preprocessor.py`
- Create: `tests/test_preprocessor.py`

- [ ] **Step 1: Write failing tests for preprocessor**

Create `core/__init__.py` (empty file).

Create `tests/test_preprocessor.py`:

```python
from datetime import datetime, timezone
from storage.models import Article
from core.preprocessor import Preprocessor


def make_article(**kwargs) -> Article:
    defaults = {
        "title": "Test",
        "url": "https://example.com/1",
        "source": "Src",
        "published_at": datetime(2026, 4, 8, tzinfo=timezone.utc),
        "content": "",
        "language": "zh",
    }
    defaults.update(kwargs)
    return Article(**defaults)


def test_level1_sufficient_metadata():
    """If content (from RSS description) is > 100 chars, use it directly."""
    long_content = "这是一篇很长的文章描述。" * 20  # > 100 chars
    article = make_article(content=long_content)
    preprocessor = Preprocessor()
    result = preprocessor.extract(article)
    assert result == long_content


def test_level2_structural_extraction():
    """For HTML content, extract title + first paragraphs + subheadings + last paragraph."""
    html_content = """
    <h1>Main Title</h1>
    <p>First important paragraph about the topic.</p>
    <p>Second paragraph with more details.</p>
    <h2>Key Point One</h2>
    <p>Details about key point one.</p>
    <h2>Key Point Two</h2>
    <p>Details about key point two.</p>
    <p>Final conclusion paragraph.</p>
    """
    article = make_article(content=html_content)
    preprocessor = Preprocessor()
    result = preprocessor.extract(article)
    assert "First important paragraph" in result
    assert "Second paragraph" in result
    assert "Key Point One" in result
    assert "Key Point Two" in result
    assert "Final conclusion" in result


def test_short_plain_text_returned_as_is():
    """Short plain text content returned unchanged."""
    article = make_article(content="Short text.")
    preprocessor = Preprocessor()
    result = preprocessor.extract(article)
    assert result == "Short text."


def test_empty_content():
    article = make_article(content="")
    preprocessor = Preprocessor()
    result = preprocessor.extract(article)
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_preprocessor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.preprocessor'`

- [ ] **Step 3: Implement core/preprocessor.py**

```python
from __future__ import annotations

import logging
from bs4 import BeautifulSoup
from storage.models import Article

logger = logging.getLogger(__name__)

METADATA_THRESHOLD = 100


class Preprocessor:
    """Three-level article content extraction."""

    def extract(self, article: Article) -> str:
        content = article.content
        if not content:
            return ""

        # Level 1: If plain-text content is long enough, use directly
        # (typically from RSS <description> or <summary>)
        if not self._looks_like_html(content):
            return content

        # Level 2: Structural extraction from HTML
        return self._structural_extract(content)

    def _looks_like_html(self, text: str) -> bool:
        return "<" in text and (">" in text) and any(
            tag in text.lower() for tag in ("<p", "<h1", "<h2", "<div", "<article")
        )

    def _structural_extract(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        parts: list[str] = []

        # First 2 paragraphs (inverted pyramid core)
        paragraphs = soup.find_all("p")
        for p in paragraphs[:2]:
            text = p.get_text(strip=True)
            if text:
                parts.append(text)

        # Subheadings / bold text (key arguments)
        for tag in soup.find_all(["h2", "h3", "strong", "b"]):
            text = tag.get_text(strip=True)
            if text and text not in parts:
                parts.append(text)

        # Last paragraph (conclusion)
        if paragraphs:
            last_text = paragraphs[-1].get_text(strip=True)
            if last_text and last_text not in parts:
                parts.append(last_text)

        return "\n\n".join(parts) if parts else soup.get_text(strip=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_preprocessor.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add core/ tests/test_preprocessor.py
git commit -m "feat: 3-level article preprocessor for content extraction"
```

---

### Task 7: LLM Layer

**Files:**
- Create: `llm/__init__.py`
- Create: `llm/base.py`
- Create: `llm/claude.py`
- Create: `llm/openai_llm.py`
- Create: `tests/test_llm_base.py`

- [ ] **Step 1: Write failing tests for LLM layer**

Create `llm/__init__.py` (empty file).

Create `tests/test_llm_base.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from storage.models import Article, ChatMessage
from llm.base import BaseLLM, create_llm


class MockLLM(BaseLLM):
    def __init__(self):
        self.summarize_called = False
        self.chat_called = False

    async def summarize(self, articles: list[Article], topic: str) -> str:
        self.summarize_called = True
        return "Mock summary"

    async def chat(self, message: str, context: list[ChatMessage]) -> str:
        self.chat_called = True
        return "Mock reply"

    async def compress_context(self, messages: list[ChatMessage]) -> str:
        return "Compressed context"

    async def extract_topic(self, user_input: str, available_topics: list[str]) -> str | None:
        return available_topics[0] if available_topics else None

    async def summarize_single(self, article: Article) -> str:
        return "Single summary"


def test_base_llm_is_abstract():
    """Cannot instantiate BaseLLM directly."""
    import pytest
    with pytest.raises(TypeError):
        BaseLLM()


async def test_mock_llm_summarize():
    llm = MockLLM()
    articles = [
        Article(title="T1", url="https://example.com/1", source="S1",
                published_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
                content="Content 1"),
    ]
    result = await llm.summarize(articles, "ai")
    assert result == "Mock summary"
    assert llm.summarize_called


async def test_mock_llm_chat():
    llm = MockLLM()
    context = [ChatMessage(role="user", content="hello")]
    result = await llm.chat("follow up", context)
    assert result == "Mock reply"
    assert llm.chat_called


def test_create_llm_claude():
    llm = create_llm(provider="claude", api_key="test-key",
                     summary_model="haiku", analysis_model="sonnet")
    from llm.claude import ClaudeLLM
    assert isinstance(llm, ClaudeLLM)


def test_create_llm_openai():
    llm = create_llm(provider="openai", api_key="test-key",
                     summary_model="gpt-4o-mini", analysis_model="gpt-4o")
    from llm.openai_llm import OpenAILLM
    assert isinstance(llm, OpenAILLM)


def test_create_llm_unknown_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm(provider="unknown", api_key="k", summary_model="m", analysis_model="m")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_llm_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm.base'`

- [ ] **Step 3: Implement llm/base.py**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from storage.models import Article, ChatMessage


class BaseLLM(ABC):
    @abstractmethod
    async def summarize(self, articles: list[Article], topic: str) -> str:
        """Summarize multiple articles for a topic. Output in Chinese."""
        ...

    @abstractmethod
    async def chat(self, message: str, context: list[ChatMessage]) -> str:
        """Conversational follow-up with context. Output in Chinese."""
        ...

    @abstractmethod
    async def compress_context(self, messages: list[ChatMessage]) -> str:
        """Compress older conversation history into a summary."""
        ...

    @abstractmethod
    async def extract_topic(self, user_input: str, available_topics: list[str]) -> str | None:
        """Extract a topic tag from user's natural language input."""
        ...

    @abstractmethod
    async def summarize_single(self, article: Article) -> str:
        """Level-3 preprocessing: summarize a single article."""
        ...


def create_llm(provider: str, api_key: str, summary_model: str, analysis_model: str) -> BaseLLM:
    if provider == "claude":
        from llm.claude import ClaudeLLM
        return ClaudeLLM(api_key=api_key, summary_model=summary_model, analysis_model=analysis_model)
    elif provider == "openai":
        from llm.openai_llm import OpenAILLM
        return OpenAILLM(api_key=api_key, summary_model=summary_model, analysis_model=analysis_model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
```

- [ ] **Step 4: Implement llm/claude.py**

```python
from __future__ import annotations

import asyncio
import logging
import time

import anthropic

from llm.base import BaseLLM
from storage.models import Article, ChatMessage

logger = logging.getLogger(__name__)

SUMMARIZE_SYSTEM = """你是一个专业的新闻分析助手。请用中文输出。
将提供的文章列表整理为结构化摘要，格式如下：

📋 【{topic} 最新资讯】{date}

1. [标题] — 一句话摘要
   🔗 原文链接

...

💡 综合分析：
整体趋势和关键洞察（2-3 句话）"""

CHAT_SYSTEM = """你是一个专业的新闻分析助手。用户正在就某个话题的资讯与你对话。
请基于已有的文章内容和对话历史，用中文回答用户的追问。
如果用户提到"第N条"，请对照之前给出的摘要列表找到对应文章。"""

COMPRESS_SYSTEM = """请将以下对话历史压缩为简短摘要，保留关键信息和结论，用中文输出。"""

EXTRACT_TOPIC_SYSTEM = """从用户输入中提取话题关键词，匹配到以下可用话题之一。
只返回匹配的话题标签（小写英文），如果没有匹配返回 NONE。

可用话题：{topics}"""

SINGLE_SUMMARY_SYSTEM = """请用一段话（50-100字）总结以下文章的核心内容，用中文输出。"""


class ClaudeLLM(BaseLLM):
    def __init__(self, api_key: str, summary_model: str, analysis_model: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._summary_model = summary_model
        self._analysis_model = analysis_model

    async def summarize(self, articles: list[Article], topic: str) -> str:
        from datetime import date
        articles_text = "\n\n---\n\n".join(
            f"标题: {a.title}\n来源: {a.source}\n链接: {a.url}\n内容: {a.summary or a.content}"
            for a in articles
        )
        system = SUMMARIZE_SYSTEM.format(topic=topic, date=date.today().isoformat())
        return await self._call_with_retry(self._analysis_model, system, articles_text)

    async def chat(self, message: str, context: list[ChatMessage]) -> str:
        messages = [{"role": m.role, "content": m.content} for m in context]
        messages.append({"role": "user", "content": message})
        return await self._call_messages_with_retry(self._analysis_model, CHAT_SYSTEM, messages)

    async def compress_context(self, messages: list[ChatMessage]) -> str:
        text = "\n".join(f"{m.role}: {m.content}" for m in messages)
        return await self._call_with_retry(self._summary_model, COMPRESS_SYSTEM, text)

    async def extract_topic(self, user_input: str, available_topics: list[str]) -> str | None:
        system = EXTRACT_TOPIC_SYSTEM.format(topics=", ".join(available_topics))
        result = await self._call_with_retry(self._summary_model, system, user_input)
        result = result.strip().lower()
        return result if result != "none" and result in available_topics else None

    async def summarize_single(self, article: Article) -> str:
        text = f"标题: {article.title}\n内容: {article.content[:3000]}"
        return await self._call_with_retry(self._summary_model, SINGLE_SUMMARY_SYSTEM, text)

    async def _call_with_retry(self, model: str, system: str, user_text: str) -> str:
        """Call with 1 retry (2s delay). On analysis_model failure, degrade to summary_model."""
        try:
            return await self._call(model, system, user_text)
        except anthropic.RateLimitError:
            raise  # Don't retry rate limits, propagate immediately
        except Exception:
            logger.warning("Claude %s call failed, retrying in 2s...", model)
            await asyncio.sleep(2)
            try:
                return await self._call(model, system, user_text)
            except Exception:
                if model == self._analysis_model and model != self._summary_model:
                    logger.warning("Degrading from %s to %s", model, self._summary_model)
                    return await self._call(self._summary_model, system, user_text)
                raise

    async def _call_messages_with_retry(self, model: str, system: str, messages: list[dict]) -> str:
        """Call with 1 retry (2s delay). On analysis_model failure, degrade to summary_model."""
        try:
            return await self._call_messages(model, system, messages)
        except anthropic.RateLimitError:
            raise
        except Exception:
            logger.warning("Claude %s call failed, retrying in 2s...", model)
            await asyncio.sleep(2)
            try:
                return await self._call_messages(model, system, messages)
            except Exception:
                if model == self._analysis_model and model != self._summary_model:
                    logger.warning("Degrading from %s to %s", model, self._summary_model)
                    return await self._call_messages(self._summary_model, system, messages)
                raise

    async def _call(self, model: str, system: str, user_text: str) -> str:
        start = time.time()
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user_text}],
            )
            result = response.content[0].text
            elapsed = time.time() - start
            tokens = response.usage.input_tokens + response.usage.output_tokens
            logger.info("Claude %s call: %.1fs, %d tokens", model, elapsed, tokens)
            return result
        except Exception:
            logger.error("Claude API call failed (model=%s)", model, exc_info=True)
            raise

    async def _call_messages(self, model: str, system: str, messages: list[dict]) -> str:
        start = time.time()
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=2048,
                system=system,
                messages=messages,
            )
            result = response.content[0].text
            elapsed = time.time() - start
            tokens = response.usage.input_tokens + response.usage.output_tokens
            logger.info("Claude %s call: %.1fs, %d tokens", model, elapsed, tokens)
            return result
        except Exception:
            logger.error("Claude API call failed (model=%s)", model, exc_info=True)
            raise
```

- [ ] **Step 5: Implement llm/openai_llm.py**

```python
from __future__ import annotations

import asyncio
import logging
import time

import openai

from llm.base import BaseLLM
from storage.models import Article, ChatMessage

logger = logging.getLogger(__name__)

# Reuse the same prompts as Claude — they are model-agnostic
from llm.claude import (
    SUMMARIZE_SYSTEM,
    CHAT_SYSTEM,
    COMPRESS_SYSTEM,
    EXTRACT_TOPIC_SYSTEM,
    SINGLE_SUMMARY_SYSTEM,
)


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: str, summary_model: str, analysis_model: str):
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._summary_model = summary_model
        self._analysis_model = analysis_model

    async def summarize(self, articles: list[Article], topic: str) -> str:
        from datetime import date
        articles_text = "\n\n---\n\n".join(
            f"标题: {a.title}\n来源: {a.source}\n链接: {a.url}\n内容: {a.summary or a.content}"
            for a in articles
        )
        system = SUMMARIZE_SYSTEM.format(topic=topic, date=date.today().isoformat())
        return await self._call_with_retry(self._analysis_model, system, articles_text)

    async def chat(self, message: str, context: list[ChatMessage]) -> str:
        messages = [{"role": "system", "content": CHAT_SYSTEM}]
        messages.extend({"role": m.role, "content": m.content} for m in context)
        messages.append({"role": "user", "content": message})
        return await self._call_messages_with_retry(self._analysis_model, messages)

    async def compress_context(self, messages: list[ChatMessage]) -> str:
        text = "\n".join(f"{m.role}: {m.content}" for m in messages)
        return await self._call_with_retry(self._summary_model, COMPRESS_SYSTEM, text)

    async def extract_topic(self, user_input: str, available_topics: list[str]) -> str | None:
        system = EXTRACT_TOPIC_SYSTEM.format(topics=", ".join(available_topics))
        result = await self._call_with_retry(self._summary_model, system, user_input)
        result = result.strip().lower()
        return result if result != "none" and result in available_topics else None

    async def summarize_single(self, article: Article) -> str:
        text = f"标题: {article.title}\n内容: {article.content[:3000]}"
        return await self._call_with_retry(self._summary_model, SINGLE_SUMMARY_SYSTEM, text)

    async def _call_with_retry(self, model: str, system: str, user_text: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ]
        return await self._call_messages_with_retry(model, messages)

    async def _call_messages_with_retry(self, model: str, messages: list[dict]) -> str:
        """Call with 1 retry (2s delay). On analysis_model failure, degrade to summary_model."""
        try:
            return await self._call_messages(model, messages)
        except openai.RateLimitError:
            raise
        except Exception:
            logger.warning("OpenAI %s call failed, retrying in 2s...", model)
            await asyncio.sleep(2)
            try:
                return await self._call_messages(model, messages)
            except Exception:
                if model == self._analysis_model and model != self._summary_model:
                    logger.warning("Degrading from %s to %s", model, self._summary_model)
                    return await self._call_messages(self._summary_model, messages)
                raise

    async def _call_messages(self, model: str, messages: list[dict]) -> str:
        start = time.time()
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
            )
            result = response.choices[0].message.content
            elapsed = time.time() - start
            tokens = response.usage.total_tokens
            logger.info("OpenAI %s call: %.1fs, %d tokens", model, elapsed, tokens)
            return result
        except Exception:
            logger.error("OpenAI API call failed (model=%s)", model, exc_info=True)
            raise
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_llm_base.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add llm/ tests/test_llm_base.py
git commit -m "feat: LLM layer with Claude and OpenAI implementations"
```

---

### Task 8: Topic Matching

**Files:**
- Create: `core/topics.py`
- Create: `tests/test_topics.py`

- [ ] **Step 1: Write failing tests for topic matching**

Create `tests/test_topics.py`:

```python
from unittest.mock import AsyncMock
from core.topics import TopicMatcher
from config import RSSSource, RedditSource, SourcesConfig


def make_sources_config() -> SourcesConfig:
    return SourcesConfig(
        rss=[
            RSSSource(name="机器之心", url="https://jiqizhixin.com/rss", topics=["ai"]),
            RSSSource(name="36氪", url="https://36kr.com/feed", topics=["tech", "ai"]),
            RSSSource(name="澎湃新闻", url="https://rsshub.app/thepaper", topics=["international"]),
        ],
        reddit=[
            RedditSource(subreddit="artificial", topics=["ai"]),
        ],
    )


async def test_keyword_match_exact():
    matcher = TopicMatcher(make_sources_config(), llm=None)
    result = await matcher.match("ai")
    assert result == "ai"


async def test_keyword_match_chinese():
    matcher = TopicMatcher(make_sources_config(), llm=None)
    result = await matcher.match("AI 最新资讯")
    assert result == "ai"


async def test_keyword_match_international():
    matcher = TopicMatcher(make_sources_config(), llm=None)
    result = await matcher.match("国际局势")
    assert result == "international"


async def test_keyword_no_match_falls_back_to_llm():
    mock_llm = AsyncMock()
    mock_llm.extract_topic = AsyncMock(return_value="ai")
    matcher = TopicMatcher(make_sources_config(), llm=mock_llm)
    result = await matcher.match("人工智能最近有什么突破")
    # keyword match should find "ai" via "人工智能" mapping
    # but if it doesn't, LLM fallback kicks in
    assert result in ["ai", "tech", "international"]


async def test_no_match_returns_none():
    mock_llm = AsyncMock()
    mock_llm.extract_topic = AsyncMock(return_value=None)
    matcher = TopicMatcher(make_sources_config(), llm=mock_llm)
    result = await matcher.match("今天天气怎么样")
    assert result is None


def test_get_sources_for_topic():
    matcher = TopicMatcher(make_sources_config(), llm=None)
    sources = matcher.get_sources_for_topic("ai")
    names = [s.name for s in sources]
    assert "机器之心" in names
    assert "36氪" in names
    assert "Reddit r/artificial" in names
    assert "澎湃新闻" not in names


def test_available_topics():
    matcher = TopicMatcher(make_sources_config(), llm=None)
    topics = matcher.available_topics()
    assert "ai" in topics
    assert "tech" in topics
    assert "international" in topics
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_topics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.topics'`

- [ ] **Step 3: Implement core/topics.py**

```python
from __future__ import annotations

import logging
from sources.base import BaseSource
from sources.rss import RSSSource
from sources.reddit import RedditSource
from config import SourcesConfig

logger = logging.getLogger(__name__)

# Chinese keyword → topic tag mapping
KEYWORD_MAP: dict[str, list[str]] = {
    "ai": ["ai", "AI", "人工智能", "机器学习", "深度学习", "大模型", "LLM", "GPT", "Claude"],
    "tech": ["科技", "技术", "tech", "互联网", "数码", "编程"],
    "international": ["国际", "世界", "全球", "地缘", "外交", "international", "world"],
    "general": ["综合", "热点", "热榜", "general"],
}


class TopicMatcher:
    def __init__(self, sources_config: SourcesConfig, llm):
        self._sources_config = sources_config
        self._llm = llm
        self._all_topics = self._collect_topics()

    def _collect_topics(self) -> set[str]:
        topics: set[str] = set()
        for rss in self._sources_config.rss:
            topics.update(rss.topics)
        for reddit in self._sources_config.reddit:
            topics.update(reddit.topics)
        return topics

    def available_topics(self) -> list[str]:
        return sorted(self._all_topics)

    async def match(self, user_input: str) -> str | None:
        # Level 1: keyword matching
        user_lower = user_input.lower()
        for topic, keywords in KEYWORD_MAP.items():
            if topic not in self._all_topics:
                continue
            for kw in keywords:
                if kw.lower() in user_lower:
                    return topic

        # Level 2: LLM fallback
        if self._llm:
            try:
                result = await self._llm.extract_topic(user_input, list(self._all_topics))
                if result:
                    return result
            except Exception:
                logger.warning("LLM topic extraction failed", exc_info=True)

        return None

    def get_sources_for_topic(self, topic: str, custom_feeds: list[dict] | None = None) -> list[BaseSource]:
        sources: list[BaseSource] = []
        for rss in self._sources_config.rss:
            if topic in rss.topics:
                sources.append(RSSSource(name=rss.name, url=rss.url, topics=rss.topics))
        for reddit in self._sources_config.reddit:
            if topic in reddit.topics:
                sources.append(RedditSource(subreddit=reddit.subreddit, topics=reddit.topics))
        # Include user's custom feeds that match the topic
        if custom_feeds:
            for feed in custom_feeds:
                if topic in feed["topics"]:
                    sources.append(RSSSource(name=feed["name"], url=feed["url"], topics=feed["topics"]))
        return sources
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_topics.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add core/topics.py tests/test_topics.py
git commit -m "feat: topic matching with keyword map and LLM fallback"
```

---

### Task 9: Pipeline

**Files:**
- Create: `core/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing tests for pipeline**

Create `tests/test_pipeline.py`:

```python
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
            published_at=datetime(2026, 4, 8, i, 0, tzinfo=timezone.utc),
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.pipeline'`

- [ ] **Step 3: Implement core/pipeline.py**

```python
from __future__ import annotations

import asyncio
import logging
from core.preprocessor import Preprocessor
from llm.base import BaseLLM
from sources.base import BaseSource
from storage.database import Database
from storage.models import Article

logger = logging.getLogger(__name__)


LEVEL3_THRESHOLD = 50  # If extracted content is shorter than this, trigger Level 3 LLM summary


class Pipeline:
    def __init__(self, llm: BaseLLM, db: Database, max_articles: int = 20,
                 max_concurrency: int = 5, cache_ttl: int = 3600):
        self._llm = llm
        self._db = db
        self._max_articles = max_articles
        self._cache_ttl = cache_ttl
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._preprocessor = Preprocessor()

    async def run(self, sources: list[BaseSource], topic: str) -> tuple[str, list[Article]]:
        # Fetch from all sources concurrently
        articles = await self._fetch_all(sources)

        if not articles:
            return "数据源暂时不可用，请稍后再试。", []

        # Dedup by URL
        seen: set[str] = set()
        unique: list[Article] = []
        for a in articles:
            if a.url not in seen:
                seen.add(a.url)
                unique.append(a)

        # Sort by published_at descending, limit
        unique.sort(key=lambda a: a.published_at, reverse=True)
        unique = unique[: self._max_articles]

        # Preprocess articles (3-level)
        for article in unique:
            cached = await self._db.get_cached_article(article.url, cache_ttl=self._cache_ttl)
            if cached and cached.summary:
                article.summary = cached.summary
            else:
                # Level 1 & 2: preprocessor
                extracted = self._preprocessor.extract(article)
                article.content = extracted

                # Level 3: if extracted content is too short, use LLM
                if len(extracted) < LEVEL3_THRESHOLD and len(article.content) > LEVEL3_THRESHOLD:
                    try:
                        article.summary = await self._llm.summarize_single(article)
                    except Exception:
                        logger.warning("Level 3 LLM summary failed for %s", article.url)

                await self._db.cache_article(article)

        # Summarize with LLM
        try:
            summary = await self._llm.summarize(unique, topic)
        except Exception:
            logger.error("LLM summarize failed", exc_info=True)
            summary = self._fallback_summary(unique, topic)

        return summary, unique

    async def _fetch_all(self, sources: list[BaseSource]) -> list[Article]:
        async def fetch_one(source: BaseSource) -> list[Article]:
            async with self._semaphore:
                try:
                    return await source.fetch()
                except Exception:
                    logger.warning("Source %s failed", source.name, exc_info=True)
                    return []

        results = await asyncio.gather(*[fetch_one(s) for s in sources])
        all_articles: list[Article] = []
        for batch in results:
            all_articles.extend(batch)
        return all_articles

    def _fallback_summary(self, articles: list[Article], topic: str) -> str:
        lines = [f"📋 【{topic} 最新资讯】\n"]
        for i, a in enumerate(articles[:10], 1):
            lines.append(f"{i}. {a.title}\n   🔗 {a.url}\n")
        lines.append("\n⚠️ LLM 分析暂不可用，以上为原始文章列表。")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_pipeline.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add core/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline with concurrent fetch, dedup, preprocess, and summarize"
```

---

### Task 10: Conversation Manager

**Files:**
- Create: `core/conversation.py`
- Create: `tests/test_conversation.py`

- [ ] **Step 1: Write failing tests for conversation manager**

Create `tests/test_conversation.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_conversation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.conversation'`

- [ ] **Step 3: Implement core/conversation.py**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_conversation.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add core/conversation.py tests/test_conversation.py
git commit -m "feat: conversation manager with session state machine"
```

---

### Task 11: Telegram Bot Handlers

**Files:**
- Create: `bot/__init__.py`
- Create: `bot/client.py`
- Create: `bot/handlers.py`
- Create: `tests/test_handlers.py`

- [ ] **Step 1: Write failing tests for handlers**

Create `bot/__init__.py` (empty file).

Create `tests/test_handlers.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers import AssistBotHandlers


def make_update(text: str, chat_id: int = 123, user_id: int = 111):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


def make_context():
    ctx = MagicMock()
    ctx.args = []
    return ctx


def make_handlers():
    mock_pipeline = AsyncMock()
    mock_pipeline.run = AsyncMock(return_value=("Summary text", []))

    mock_topic_matcher = AsyncMock()
    mock_topic_matcher.match = AsyncMock(return_value="ai")
    mock_topic_matcher.available_topics = MagicMock(return_value=["ai", "tech"])
    mock_topic_matcher.get_sources_for_topic = MagicMock(return_value=[])

    mock_conversation = AsyncMock()
    mock_conversation.has_active_session = AsyncMock(return_value=False)
    mock_conversation.get_or_create_session = AsyncMock(return_value=MagicMock(id="s1"))
    mock_conversation.add_message = AsyncMock()
    mock_conversation.get_context = AsyncMock(return_value=[])

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value="Chat reply")

    mock_db = AsyncMock()
    mock_db.get_custom_feeds = AsyncMock(return_value=[])
    mock_db.add_custom_feed = AsyncMock()
    mock_db.remove_custom_feed = AsyncMock(return_value=True)

    return AssistBotHandlers(
        pipeline=mock_pipeline,
        topic_matcher=mock_topic_matcher,
        conversation=mock_conversation,
        llm=mock_llm,
        db=mock_db,
        allowed_users=[111, 222],
    )


async def test_unauthorized_user_rejected():
    handlers = make_handlers()
    update = make_update("/start", user_id=999)
    await handlers.start(update, make_context())
    update.message.reply_text.assert_called_once()
    assert "没有使用权限" in update.message.reply_text.call_args[0][0]


async def test_start_command():
    handlers = make_handlers()
    update = make_update("/start", user_id=111)
    await handlers.start(update, make_context())
    update.message.reply_html.assert_called_once()
    reply = update.message.reply_html.call_args[0][0]
    assert "AssistBot" in reply


async def test_help_command():
    handlers = make_handlers()
    update = make_update("/help", user_id=111)
    await handlers.help_cmd(update, make_context())
    update.message.reply_html.assert_called_once()


async def test_topic_command():
    handlers = make_handlers()
    update = make_update("/topic ai", user_id=111)
    ctx = make_context()
    ctx.args = ["ai"]
    await handlers.topic_cmd(update, ctx)
    # Should call pipeline and reply
    handlers._pipeline.run.assert_called_once()


async def test_sources_command():
    handlers = make_handlers()
    update = make_update("/sources", user_id=111)
    await handlers.sources_cmd(update, make_context())
    update.message.reply_html.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_handlers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot.handlers'`

- [ ] **Step 3: Implement bot/handlers.py**

```python
from __future__ import annotations

import asyncio
import json
import logging
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from core.conversation import ConversationManager
from core.pipeline import Pipeline
from core.topics import TopicMatcher
from llm.base import BaseLLM
from storage.database import Database

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096

WELCOME_MSG = """<b>👋 欢迎使用 AssistBot!</b>

我可以帮你分析和总结最新资讯。

<b>使用方式：</b>
• 发送 /topic &lt;关键词&gt; 查询资讯
• 直接发送话题关键词（如"AI 最新资讯"）
• 在查询后继续追问，深入分析

发送 /help 查看完整命令列表。"""

HELP_MSG = """<b>📖 命令列表</b>

/topic &lt;关键词&gt; — 查询某个 topic 的最新资讯
/sources — 查看已配置的数据源列表
/addrss &lt;url&gt; — 添加自定义 RSS 源
/removerss &lt;url&gt; — 移除 RSS 源
/model — 查看当前 LLM 后端（MVP 暂不支持切换）
/help — 帮助信息

也可以直接发送自然语言查询，如"AI 最新资讯"。"""


class AssistBotHandlers:
    def __init__(
        self,
        pipeline: Pipeline,
        topic_matcher: TopicMatcher,
        conversation: ConversationManager,
        llm: BaseLLM,
        db: Database,
        allowed_users: list[int],
    ):
        self._pipeline = pipeline
        self._topic_matcher = topic_matcher
        self._conversation = conversation
        self._llm = llm
        self._db = db
        self._allowed_users = allowed_users

    def _is_authorized(self, user_id: int) -> bool:
        return not self._allowed_users or user_id in self._allowed_users

    async def _check_auth(self, update: Update) -> bool:
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("抱歉，您没有使用权限。")
            return False
        return True

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_auth(update):
            return
        await update.message.reply_html(WELCOME_MSG)

    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_auth(update):
            return
        await update.message.reply_html(HELP_MSG)

    async def topic_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_auth(update):
            return
        if not context.args:
            await update.message.reply_text("请提供话题关键词，如: /topic AI")
            return
        query = " ".join(context.args)
        await self._handle_topic_query(update, query)

    async def sources_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_auth(update):
            return
        chat_id = update.effective_chat.id
        topics = self._topic_matcher.available_topics()
        custom = await self._db.get_custom_feeds(chat_id)

        lines = ["<b>📡 数据源列表</b>\n"]
        lines.append(f"<b>支持的话题：</b> {', '.join(topics)}\n")
        if custom:
            lines.append("<b>自定义 RSS：</b>")
            for feed in custom:
                lines.append(f"• {feed['name']} — {feed['url']}")
        await update.message.reply_html("\n".join(lines))

    async def addrss_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_auth(update):
            return
        if not context.args:
            await update.message.reply_text("用法: /addrss <url> [topic]\n示例: /addrss https://example.com/rss ai")
            return
        url = context.args[0]
        topic = context.args[1] if len(context.args) > 1 else "custom"
        chat_id = update.effective_chat.id
        await self._db.add_custom_feed(chat_id=chat_id, name=url, url=url, topics=[topic])
        await update.message.reply_text(f"已添加 RSS 源: {url} (话题: {topic})")

    async def removerss_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_auth(update):
            return
        if not context.args:
            await update.message.reply_text("请提供 RSS URL，如: /removerss https://example.com/rss")
            return
        url = context.args[0]
        chat_id = update.effective_chat.id
        removed = await self._db.remove_custom_feed(chat_id=chat_id, url=url)
        if removed:
            await update.message.reply_text(f"已移除 RSS 源: {url}")
        else:
            await update.message.reply_text("未找到该 RSS 源。")

    async def model_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_auth(update):
            return
        await update.message.reply_text(
            f"当前 LLM: {self._llm.__class__.__name__}\n"
            f"摘要模型 / 分析模型（详见配置文件）"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._check_auth(update):
            return
        text = update.message.text.strip()
        if not text:
            return

        chat_id = update.effective_chat.id

        # Check if user has an active session (follow-up question)
        if await self._conversation.has_active_session(chat_id):
            await self._handle_followup(update, text)
        else:
            await self._handle_topic_query(update, text)

    async def _handle_topic_query(self, update: Update, query: str) -> None:
        chat_id = update.effective_chat.id

        # Match topic
        topic = await self._topic_matcher.match(query)
        if topic is None:
            available = ", ".join(self._topic_matcher.available_topics())
            await update.message.reply_text(
                f"未能识别话题。当前支持的话题: {available}\n"
                f"可以通过 /addrss 添加新的数据源。"
            )
            return

        # Show typing indicator (keep sending during the whole operation)
        await update.message.reply_text("🔍 正在为你搜集资讯...")
        typing_task = asyncio.create_task(self._keep_typing(update))
        try:
            # Get sources (including user's custom feeds) and run pipeline
            custom_feeds = await self._db.get_custom_feeds(chat_id)
            sources = self._topic_matcher.get_sources_for_topic(topic, custom_feeds=custom_feeds)
            summary, articles = await self._pipeline.run(sources=sources, topic=topic)

            # Create session
            articles_json = json.dumps(
                [{"title": a.title, "url": a.url, "source": a.source} for a in articles]
            )
            session = await self._conversation.get_or_create_session(
                chat_id=chat_id, topic=topic, articles_json=articles_json
            )
            await self._conversation.add_message(session.id, "assistant", summary)

            # Send response (handle message length)
            await self._send_long_message(update, summary)
        finally:
            typing_task.cancel()

    async def _keep_typing(self, update: Update) -> None:
        """Continuously send typing action every 5 seconds."""
        try:
            while True:
                await update.message.chat.send_action(ChatAction.TYPING)
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

    async def _handle_followup(self, update: Update, text: str) -> None:
        chat_id = update.effective_chat.id
        await update.message.chat.send_action(ChatAction.TYPING)

        session_row = await self._db.get_active_session(chat_id)
        if not session_row:
            await self._handle_topic_query(update, text)
            return

        session_id = session_row["id"]
        await self._conversation.add_message(session_id, "user", text)
        context = await self._conversation.get_context(session_id)

        try:
            reply = await self._llm.chat(text, context)
        except Exception:
            logger.error("LLM chat failed", exc_info=True)
            reply = "处理出错，请重试。"

        await self._conversation.add_message(session_id, "assistant", reply)
        await self._send_long_message(update, reply)

    async def _send_long_message(self, update: Update, text: str) -> None:
        if len(text) <= MAX_MESSAGE_LENGTH:
            await update.message.reply_html(text)
            return

        # Split at last newline before limit
        chunks: list[str] = []
        remaining = text
        while remaining:
            if len(remaining) <= MAX_MESSAGE_LENGTH:
                chunks.append(remaining)
                break
            split_at = remaining.rfind("\n", 0, MAX_MESSAGE_LENGTH)
            if split_at == -1:
                split_at = MAX_MESSAGE_LENGTH
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")

        for chunk in chunks:
            await update.message.reply_html(chunk)
```

- [ ] **Step 4: Implement bot/client.py**

```python
from __future__ import annotations

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import AssistBotHandlers
from config import AppConfig
from core.conversation import ConversationManager
from core.pipeline import Pipeline
from core.topics import TopicMatcher
from llm.base import BaseLLM
from storage.database import Database

logger = logging.getLogger(__name__)


def create_bot(config: AppConfig, llm: BaseLLM, db: Database, post_init=None) -> Application:
    if not config.telegram.bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

    topic_matcher = TopicMatcher(config.sources, llm=llm)
    pipeline = Pipeline(
        llm=llm, db=db,
        max_articles=config.max_articles,
        max_concurrency=config.max_concurrency,
        cache_ttl=config.cache_ttl,
    )
    conversation = ConversationManager(db=db, session_timeout=config.session_timeout, llm=llm)

    handlers = AssistBotHandlers(
        pipeline=pipeline,
        topic_matcher=topic_matcher,
        conversation=conversation,
        llm=llm,
        db=db,
        allowed_users=config.telegram.allowed_users,
    )

    builder = Application.builder().token(config.telegram.bot_token)
    if post_init:
        builder = builder.post_init(post_init)
    app = builder.build()

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("topic", handlers.topic_cmd))
    app.add_handler(CommandHandler("sources", handlers.sources_cmd))
    app.add_handler(CommandHandler("addrss", handlers.addrss_cmd))
    app.add_handler(CommandHandler("removerss", handlers.removerss_cmd))
    app.add_handler(CommandHandler("model", handlers.model_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    return app
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/test_handlers.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add bot/ tests/test_handlers.py
git commit -m "feat: Telegram bot handlers with auth, topic query, and follow-up"
```

---

### Task 12: Main Entry Point + Integration

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement main.py**

```python
from __future__ import annotations

import asyncio
import logging
import sys

from config import load_config
from llm.base import create_llm
from storage.database import Database
from bot.client import create_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    logger.info("Loading config from %s", config_path)
    config = load_config(config_path)

    logger.info("Initializing database...")
    db = Database(config.db_path)
    # DB init needs to happen inside the event loop that run_polling creates,
    # so we register it as a post_init callback
    async def post_init(application):
        await db.init()

    logger.info("Initializing LLM provider: %s", config.llm.provider)
    if not config.llm.api_key:
        logger.error("LLM_API_KEY environment variable is required")
        sys.exit(1)

    llm = create_llm(
        provider=config.llm.provider,
        api_key=config.llm.api_key,
        summary_model=config.llm.summary_model,
        analysis_model=config.llm.analysis_model,
    )

    logger.info("Starting Telegram bot...")
    app = create_bot(config, llm, db, post_init=post_init)
    # run_polling() is a blocking synchronous method that manages its own event loop
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify all tests pass**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main entry point wiring config, DB, LLM, and bot"
```

---

### Task 13: All __init__.py Files + Final Verification

- [ ] **Step 1: Ensure all __init__.py files exist**

Verify these empty `__init__.py` files exist (some were created in prior tasks):
- `storage/__init__.py`
- `sources/__init__.py`
- `llm/__init__.py`
- `core/__init__.py`
- `bot/__init__.py`
- `tests/__init__.py`

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/z/Z/AssistBot && python -m pytest tests/ -v --tb=short`
Expected: All tests pass (approx 42 tests)

- [ ] **Step 3: Verify imports work end-to-end**

Run: `cd /Users/z/Z/AssistBot && python -c "from config import load_config; from storage.database import Database; from sources.rss import RSSSource; from llm.base import create_llm; from core.pipeline import Pipeline; from bot.handlers import AssistBotHandlers; print('All imports OK')"`
Expected: `All imports OK`

- [ ] **Step 4: Commit any remaining files**

```bash
git add -A
git commit -m "chore: ensure all package init files and run final verification"
```
