from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)


async def send_telegram(message: str, parse_mode: str = "Markdown") -> bool:
    """Send a message via Telegram bot. Gracefully skips if no token configured."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.info("Telegram not configured, skipping notification")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("Telegram message sent successfully")
            return True
    except Exception:
        logger.warning("Failed to send Telegram notification", exc_info=True)
        return False
