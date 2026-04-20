from __future__ import annotations
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
    async def chat(self, message: str, context: list[ChatMessage], articles_context: str = "") -> str:
        self.chat_called = True
        return "Mock reply"
    async def compress_context(self, messages: list[ChatMessage]) -> str:
        return "Compressed context"
    async def extract_topic(self, user_input: str, available_topics: list[str]) -> str | None:
        return available_topics[0] if available_topics else None
    async def summarize_single(self, article: Article) -> str:
        return "Single summary"

def test_base_llm_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        BaseLLM()

async def test_mock_llm_summarize():
    llm = MockLLM()
    articles = [Article(title="T1", url="https://example.com/1", source="S1",
                published_at=datetime(2026, 4, 8, tzinfo=timezone.utc), content="Content 1")]
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
    llm = create_llm(provider="claude", api_key="test-key", summary_model="haiku", analysis_model="sonnet")
    from llm.claude import ClaudeLLM
    assert isinstance(llm, ClaudeLLM)

def test_create_llm_openai():
    llm = create_llm(provider="openai", api_key="test-key", summary_model="gpt-4o-mini", analysis_model="gpt-4o")
    from llm.openai_llm import OpenAILLM
    assert isinstance(llm, OpenAILLM)

def test_create_llm_unknown_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm(provider="unknown", api_key="k", summary_model="m", analysis_model="m")
