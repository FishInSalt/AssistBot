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
