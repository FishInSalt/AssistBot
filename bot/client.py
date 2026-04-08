from __future__ import annotations

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import AssistBotHandlers
from config import AppConfig
from core.conversation import ConversationManager
from core.pipeline import Pipeline
from core.topics import TopicMatcher
from llm.base import BaseLLM
from storage.database import Database

logger = logging.getLogger(__name__)


def create_bot(config: AppConfig, llm: BaseLLM, db: Database, post_init=None, post_shutdown=None) -> Application:
    if not config.telegram.bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

    topic_matcher = TopicMatcher(config.sources, llm=llm)
    pipeline = Pipeline(
        llm=llm, db=db,
        max_articles=config.max_articles,
        max_concurrency=config.max_concurrency,
        cache_ttl=config.cache_ttl,
    )
    conversation = ConversationManager(db=db, session_timeout=config.session_timeout, llm=llm)

    handlers = AssistBotHandlers(
        pipeline=pipeline,
        topic_matcher=topic_matcher,
        conversation=conversation,
        llm=llm,
        db=db,
        allowed_users=config.telegram.allowed_users,
    )

    builder = Application.builder().token(config.telegram.bot_token)
    if post_init:
        builder = builder.post_init(post_init)
    if post_shutdown:
        builder = builder.post_shutdown(post_shutdown)
    app = builder.build()

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("topic", handlers.topic_cmd))
    app.add_handler(CommandHandler("sources", handlers.sources_cmd))
    app.add_handler(CommandHandler("addrss", handlers.addrss_cmd))
    app.add_handler(CommandHandler("removerss", handlers.removerss_cmd))
    app.add_handler(CommandHandler("model", handlers.model_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    app.add_error_handler(handlers.error_handler)

    return app
