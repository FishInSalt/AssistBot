from __future__ import annotations
import asyncio
import logging
import time
import anthropic
from llm.base import BaseLLM, RateLimitException
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
            for a in articles)
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
