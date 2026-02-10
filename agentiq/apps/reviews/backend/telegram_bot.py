"""Telegram bot for sending notifications."""
import os
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Initialize bot (lazy loading)
_bot = None


def get_bot() -> Bot:
    """Get Telegram bot instance."""
    global _bot
    if _bot is None:
        if not TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")
        _bot = Bot(token=TELEGRAM_BOT_TOKEN)
    return _bot


def send_telegram_notification(telegram_id: int, message: str) -> bool:
    """
    Send a Telegram notification to user.

    Args:
        telegram_id: User's Telegram ID
        message: Message text

    Returns:
        True if sent successfully, False otherwise
    """
    # Skip Telegram notifications in local testing mode
    if TELEGRAM_BOT_TOKEN == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz":
        print(f"[LOCAL TEST] Skipping Telegram notification to {telegram_id}: {message}")
        return True

    try:
        import asyncio
        bot = get_bot()

        # Run async send_message in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        )
        loop.close()
        return True
    except TelegramError as e:
        print(f"Failed to send Telegram notification to {telegram_id}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error sending notification: {e}")
        return False
