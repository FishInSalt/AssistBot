from __future__ import annotations

import asyncio
import logging
import sys

from config import load_config
from llm.base import create_llm
from storage.database import Database
from bot.client import create_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    logger.info("Loading config from %s", config_path)
    config = load_config(config_path)

    logger.info("Initializing database...")
    db = Database(config.db_path)
    # DB init needs to happen inside the event loop that run_polling creates,
    # so we register it as a post_init callback
    async def post_init(application):
        await db.init()

    async def post_shutdown(application):
        await db.close()

    logger.info("Initializing LLM provider: %s", config.llm.provider)
    if not config.llm.api_key:
        logger.error("LLM_API_KEY environment variable is required")
        sys.exit(1)

    llm = create_llm(
        provider=config.llm.provider,
        api_key=config.llm.api_key,
        summary_model=config.llm.summary_model,
        analysis_model=config.llm.analysis_model,
    )

    logger.info("Starting Telegram bot...")
    app = create_bot(config, llm, db, post_init=post_init, post_shutdown=post_shutdown)
    # run_polling() is a blocking synchronous method that manages its own event loop
    app.run_polling()


if __name__ == "__main__":
    main()
