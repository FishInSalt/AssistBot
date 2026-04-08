from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import urlparse
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from core.conversation import ConversationManager
from core.pipeline import Pipeline
from core.topics import TopicMatcher
from llm.base import BaseLLM, RateLimitException
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
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            await update.message.reply_text("请提供有效的 HTTP/HTTPS URL。")
            return
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
            self._topic_matcher.add_custom_topics(custom_feeds)
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
        except RateLimitException:
            await update.message.reply_text("请求过于频繁，请稍后再试。")
        except Exception:
            logger.error("Topic query failed", exc_info=True)
            await update.message.reply_text("处理出错，请重试。")
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

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Unhandled exception", exc_info=context.error)
        if isinstance(update, Update) and update.message:
            try:
                await update.message.reply_text("处理出错，请重试。")
            except Exception:
                pass

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
