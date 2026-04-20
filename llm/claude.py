from __future__ import annotations
import asyncio
import logging
import time
import anthropic
from llm.base import BaseLLM, RateLimitException
from llm.prompts import (
    SUMMARIZE_SYSTEM, CHAT_SYSTEM, COMPRESS_SYSTEM,
    EXTRACT_TOPIC_SYSTEM, SINGLE_SUMMARY_SYSTEM,
)
from storage.models import Article, ChatMessage

logger = logging.getLogger(__name__)

class ClaudeLLM(BaseLLM):
    def __init__(self, api_key: str, summary_model: str, analysis_model: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._summary_model = summary_model
        self._analysis_model = analysis_model

    async def summarize(self, articles: list[Article], topic: str) -> str:
        from datetime import date
        articles_text = "\n\n---\n\n".join(
            f"标题: {a.title}\n来源: {a.source}\n链接: {a.url}\n内容: {a.summary or a.content}"
            for a in articles)
        system = SUMMARIZE_SYSTEM.format(topic=topic, date=date.today().isoformat())
        return await self._call_with_retry(self._analysis_model, system, articles_text)

    async def chat(self, message: str, context: list[ChatMessage], articles_context: str = "") -> str:
        messages = [{"role": m.role, "content": m.content} for m in context]
        messages.append({"role": "user", "content": message})
        system = CHAT_SYSTEM
        if articles_context:
            system = f"{CHAT_SYSTEM}\n\n{articles_context}"
        return await self._call_messages_with_retry(self._analysis_model, system, messages)

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
        try:
            return await self._call(model, system, user_text)
        except anthropic.RateLimitError:
            raise RateLimitException("Rate limited") from None
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
        try:
            return await self._call_messages(model, system, messages)
        except anthropic.RateLimitError:
            raise RateLimitException("Rate limited") from None
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
                model=model, max_tokens=2048, system=system,
                messages=[{"role": "user", "content": user_text}])
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
                model=model, max_tokens=2048, system=system, messages=messages)
            result = response.content[0].text
            elapsed = time.time() - start
            tokens = response.usage.input_tokens + response.usage.output_tokens
            logger.info("Claude %s call: %.1fs, %d tokens", model, elapsed, tokens)
            return result
        except Exception:
            logger.error("Claude API call failed (model=%s)", model, exc_info=True)
            raise
