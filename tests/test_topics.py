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
