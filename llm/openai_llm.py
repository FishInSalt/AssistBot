from __future__ import annotations
import asyncio
import logging
import time
import openai
from llm.base import BaseLLM
from storage.models import Article, ChatMessage

logger = logging.getLogger(__name__)

from llm.claude import (
    SUMMARIZE_SYSTEM, CHAT_SYSTEM, COMPRESS_SYSTEM,
    EXTRACT_TOPIC_SYSTEM, SINGLE_SUMMARY_SYSTEM,
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
            for a in articles)
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
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_text}]
        return await self._call_messages_with_retry(model, messages)

    async def _call_messages_with_retry(self, model: str, messages: list[dict]) -> str:
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
                model=model, messages=messages, max_tokens=2048)
            result = response.choices[0].message.content
            elapsed = time.time() - start
            tokens = response.usage.total_tokens
            logger.info("OpenAI %s call: %.1fs, %d tokens", model, elapsed, tokens)
            return result
        except Exception:
            logger.error("OpenAI API call failed (model=%s)", model, exc_info=True)
            raise
