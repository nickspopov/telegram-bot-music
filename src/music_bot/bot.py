import asyncio
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .config import Settings
from .downloader import ProcessingError, extract_youtube_url, process_youtube_url

LOGGER = logging.getLogger(__name__)


def _is_allowed(update: Update, settings: Settings) -> bool:
    user = update.effective_user
    return bool(user and user.id in settings.allowed_user_ids)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not _is_allowed(update, settings):
        user = update.effective_user
        LOGGER.warning("Ignoring unauthorized /start from user_id=%s", user.id if user else None)
        return
    if update.message:
        await update.message.reply_text("Send a YouTube link; I’ll return an H2-safe MP3.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    user = update.effective_user
    if not _is_allowed(update, settings):
        LOGGER.warning("Ignoring unauthorized message from user_id=%s", user.id if user else None)
        return

    message = update.message
    if message is None or message.text is None:
        return

    url = extract_youtube_url(message.text)
    if not url:
        await message.reply_text("Send a YouTube URL.")
        return

    status = await message.reply_text("Downloading and converting…")
    chat_id = message.chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_DOCUMENT)

    settings.workdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="job-", dir=str(settings.workdir)) as tmp_raw:
        tmp = Path(tmp_raw)
        try:
            artifact = await asyncio.to_thread(process_youtube_url, url, tmp, settings)
            caption = (
                f"{artifact.validation.message}: "
                f"{artifact.validation.codec}, {artifact.validation.sample_rate} Hz, "
                f"{artifact.validation.channels} ch"
            )
            with artifact.path.open("rb") as audio:
                await message.reply_audio(
                    audio=audio,
                    filename=artifact.filename,
                    title=artifact.title[:64],
                    performer=artifact.performer[:64] if artifact.performer else None,
                    duration=artifact.duration,
                    caption=caption[:1024],
                )
            await status.delete()
        except ProcessingError as exc:
            LOGGER.warning("Processing failed for user_id=%s url=%s: %s", user.id if user else None, url, exc)
            await status.edit_text(f"Failed: {exc}")
        except Exception:
            LOGGER.exception("Unexpected bot error")
            await status.edit_text("Failed: unexpected error. Check container logs.")


def build_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.bot_token).build()
    application.bot_data["settings"] = settings
    application.add_handler(CommandHandler(["start", "help"], start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


def run_bot(settings: Settings) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    LOGGER.info("Starting bot with allowed_user_ids=%s", sorted(settings.allowed_user_ids))
    app = build_application(settings)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
