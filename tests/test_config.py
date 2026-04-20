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
