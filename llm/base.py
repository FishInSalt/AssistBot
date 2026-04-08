from __future__ import annotations
from abc import ABC, abstractmethod
from storage.models import Article, ChatMessage


class RateLimitException(Exception):
    pass


class BaseLLM(ABC):
    @abstractmethod
    async def summarize(self, articles: list[Article], topic: str) -> str: ...
    @abstractmethod
    async def chat(self, message: str, context: list[ChatMessage], articles_context: str = "") -> str: ...
    @abstractmethod
    async def compress_context(self, messages: list[ChatMessage]) -> str: ...
    @abstractmethod
    async def extract_topic(self, user_input: str, available_topics: list[str]) -> str | None: ...
    @abstractmethod
    async def summarize_single(self, article: Article) -> str: ...

def create_llm(provider: str, api_key: str, summary_model: str, analysis_model: str) -> BaseLLM:
    if provider == "claude":
        from llm.claude import ClaudeLLM
        return ClaudeLLM(api_key=api_key, summary_model=summary_model, analysis_model=analysis_model)
    elif provider == "openai":
        from llm.openai_llm import OpenAILLM
        return OpenAILLM(api_key=api_key, summary_model=summary_model, analysis_model=analysis_model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
