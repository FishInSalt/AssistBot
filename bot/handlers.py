from __future__ import annotations

import asyncio
import json
import logging
import time as _time
import uuid
from urllib.parse import urlparse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
        self._pending_more: dict[str, tuple[float, str]] = {}  # callback_id -> (timestamp, text)

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
        custom = await self._db.get_custom_feeds(chat_id)
        topics = self._topic_matcher.available_topics(custom_feeds=custom)

        lines = ["📡 数据源列表\n"]
        lines.append(f"支持的话题: {', '.join(topics)}\n")
        if custom:
            lines.append("自定义 RSS:")
            for feed in custom:
                lines.append(f"• {feed['name']} — {feed['url']}")
        await update.message.reply_text("\n".join(lines))

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

        # Check if user has an active session
        session_row = await self._conversation.get_active_session_if_valid(chat_id)
        if session_row:
            # Try to detect if user wants a new topic
            custom_feeds = await self._db.get_custom_feeds(chat_id)
            new_topic = await self._topic_matcher.match(text, custom_feeds=custom_feeds)
            if new_topic and new_topic != session_row["topic"]:
                # User wants a different topic — start new query
                await self._handle_topic_query(update, text)
            else:
                # Same topic or no topic detected — treat as follow-up
                await self._handle_followup(update, text)
        else:
            await self._handle_topic_query(update, text)

    async def _handle_topic_query(self, update: Update, query: str) -> None:
        chat_id = update.effective_chat.id
        custom_feeds = await self._db.get_custom_feeds(chat_id)

        # Match topic (include custom feeds for topic resolution)
        topic = await self._topic_matcher.match(query, custom_feeds=custom_feeds)
        if topic is None:
            available = ", ".join(self._topic_matcher.available_topics(custom_feeds=custom_feeds))
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
        except (asyncio.CancelledError, Exception):
            pass

    async def _handle_followup(self, update: Update, text: str) -> None:
        chat_id = update.effective_chat.id
        await update.message.chat.send_action(ChatAction.TYPING)

        session_row = await self._conversation.get_active_session_if_valid(chat_id)
        if not session_row:
            await self._handle_topic_query(update, text)
            return

        session_id = session_row["id"]
        await self._conversation.add_message(session_id, "user", text)
        context = await self._conversation.get_context(session_id)

        # Include article context from the session
        articles_json = session_row.get("articles", "[]")
        articles_context = self._format_articles_context(articles_json)

        try:
            reply = await self._llm.chat(text, context, articles_context=articles_context)
        except Exception:
            logger.error("LLM chat failed", exc_info=True)
            reply = "处理出错，请重试。"

        await self._conversation.add_message(session_id, "assistant", reply)
        await self._send_long_message(update, reply)

    def _format_articles_context(self, articles_json: str) -> str:
        try:
            articles = json.loads(articles_json)
            if not articles:
                return ""
            lines = ["以下是本次查询获取的文章列表："]
            for i, a in enumerate(articles, 1):
                lines.append(f"{i}. {a.get('title', '')} — {a.get('source', '')} ({a.get('url', '')})")
            return "\n".join(lines)
        except (json.JSONDecodeError, TypeError):
            return ""

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Unhandled exception", exc_info=context.error)
        if isinstance(update, Update) and update.message:
            try:
                await update.message.reply_text("处理出错，请重试。")
            except Exception:
                pass

    def _cleanup_pending_more(self) -> None:
        now = _time.time()
        expired = [k for k, (ts, _) in self._pending_more.items() if now - ts > 600]
        for k in expired:
            del self._pending_more[k]

    async def _send_long_message(self, update: Update, text: str) -> None:
        if len(text) <= MAX_MESSAGE_LENGTH:
            await update.message.reply_text(text)
            return

        # Find a good split point for the overview portion
        split_at = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        if split_at == -1:
            split_at = MAX_MESSAGE_LENGTH
        overview = text[:split_at]
        remaining = text[split_at:].lstrip("\n")

        if remaining:
            callback_id = str(uuid.uuid4())[:8]
            self._cleanup_pending_more()
            self._pending_more[callback_id] = (_time.time(), remaining)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 查看更多", callback_data=f"more:{callback_id}")]
            ])
            await update.message.reply_text(overview, reply_markup=keyboard)
        else:
            await update.message.reply_text(overview)

    async def handle_show_more(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data
        if not data.startswith("more:"):
            return
        callback_id = data[5:]
        entry = self._pending_more.pop(callback_id, None)
        if not entry:
            await query.message.reply_text("内容已过期，请重新查询。")
            return
        _, remaining = entry

        # Send remaining content in chunks if needed
        while remaining:
            if len(remaining) <= MAX_MESSAGE_LENGTH:
                await query.message.reply_text(remaining)
                break
            split_at = remaining.rfind("\n", 0, MAX_MESSAGE_LENGTH)
            if split_at == -1:
                split_at = MAX_MESSAGE_LENGTH
            await query.message.reply_text(remaining[:split_at])
            remaining = remaining[split_at:].lstrip("\n")
