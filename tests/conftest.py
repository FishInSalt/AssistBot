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
