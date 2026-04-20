from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers import AssistBotHandlers


def make_update(text: str, chat_id: int = 123, user_id: int = 111):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.reply_html = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


def make_context():
    ctx = MagicMock()
    ctx.args = []
    return ctx


def make_handlers():
    mock_pipeline = AsyncMock()
    mock_pipeline.run = AsyncMock(return_value=("Summary text", []))

    mock_topic_matcher = AsyncMock()
    mock_topic_matcher.match = AsyncMock(return_value="ai")
    mock_topic_matcher.available_topics = MagicMock(return_value=["ai", "tech"])
    mock_topic_matcher.get_sources_for_topic = MagicMock(return_value=[])

    mock_conversation = AsyncMock()
    mock_conversation.has_active_session = AsyncMock(return_value=False)
    mock_conversation.get_active_session_if_valid = AsyncMock(return_value=None)
    mock_conversation.get_or_create_session = AsyncMock(return_value=MagicMock(id="s1"))
    mock_conversation.add_message = AsyncMock()
    mock_conversation.get_context = AsyncMock(return_value=[])

    mock_llm = AsyncMock()
    mock_llm.chat = AsyncMock(return_value="Chat reply")

    mock_db = AsyncMock()
    mock_db.get_custom_feeds = AsyncMock(return_value=[])
    mock_db.add_custom_feed = AsyncMock()
    mock_db.remove_custom_feed = AsyncMock(return_value=True)

    return AssistBotHandlers(
        pipeline=mock_pipeline,
        topic_matcher=mock_topic_matcher,
        conversation=mock_conversation,
        llm=mock_llm,
        db=mock_db,
        allowed_users=[111, 222],
    )


async def test_unauthorized_user_rejected():
    handlers = make_handlers()
    update = make_update("/start", user_id=999)
    await handlers.start(update, make_context())
    update.message.reply_text.assert_called_once()
    assert "没有使用权限" in update.message.reply_text.call_args[0][0]


async def test_start_command():
    handlers = make_handlers()
    update = make_update("/start", user_id=111)
    await handlers.start(update, make_context())
    update.message.reply_html.assert_called_once()
    reply = update.message.reply_html.call_args[0][0]
    assert "AssistBot" in reply


async def test_help_command():
    handlers = make_handlers()
    update = make_update("/help", user_id=111)
    await handlers.help_cmd(update, make_context())
    update.message.reply_html.assert_called_once()


async def test_topic_command():
    handlers = make_handlers()
    update = make_update("/topic ai", user_id=111)
    ctx = make_context()
    ctx.args = ["ai"]
    await handlers.topic_cmd(update, ctx)
    # Should call pipeline and reply
    handlers._pipeline.run.assert_called_once()


async def test_sources_command():
    handlers = make_handlers()
    update = make_update("/sources", user_id=111)
    await handlers.sources_cmd(update, make_context())
    update.message.reply_text.assert_called_once()
