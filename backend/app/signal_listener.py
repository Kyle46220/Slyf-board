import asyncio
import json
import logging
import re
import websockets
from pathlib import Path
from typing import Optional
from app.config import settings
from app.totp import verify_totp

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"^https?://\S+$")


def parse_message(text: str, attachments: list) -> Optional[dict]:
    """Extract TOTP and content from a raw Signal message. Returns None if malformed."""
    if not text:
        return None
    parts = text.strip().split(" ", 1)
    code = parts[0]
    if len(code) != 6 or not code.isdigit():
        return None
    body = parts[1].strip() if len(parts) > 1 else None

    if attachments:
        first = attachments[0].get("content_type", "")
        if first.startswith("image/"):
            content_type = "image"
        elif first.startswith("video/"):
            content_type = "video"
        else:
            content_type = "text"
    elif body and URL_RE.match(body):
        content_type = "link"
    else:
        content_type = "text"

    return {
        "totp": code,
        "body": body,
        "content_type": content_type,
        "attachments": attachments,
    }


async def listen(on_message, signal_socket_path: str = "/var/run/signal-cli/socket"):
    """
    Connect to signal-cli JSON-RPC socket and call on_message(parsed) for each valid message.
    Reconnects with exponential backoff (max 10 retries, cap 60s).
    """
    delay = 1
    retries = 0
    max_retries = 10

    while retries < max_retries:
        try:
            async with websockets.unix_connect(signal_socket_path) as ws:
                logger.info("Connected to signal-cli socket")
                delay = 1
                retries = 0
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        envelope = msg.get("params", {}).get("envelope", {})
                        data_msg = envelope.get("dataMessage", {})
                        text = data_msg.get("message", "") or ""
                        attachments = data_msg.get("attachments", [])

                        # strip sender metadata immediately
                        envelope.pop("source", None)
                        envelope.pop("sourceNumber", None)
                        envelope.pop("sourceName", None)
                        envelope.pop("sourceDevice", None)
                        envelope.pop("sourceUuid", None)
                        data_msg.pop("timestamp", None)

                        parsed = parse_message(text, attachments)
                        if parsed is None:
                            continue
                        if not verify_totp(parsed["totp"], settings.totp_secret):
                            continue

                        await on_message(parsed)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
        except Exception as e:
            retries += 1
            logger.error(f"signal-cli connection failed (attempt {retries}/{max_retries}): {e}")
            await asyncio.sleep(min(delay, 60))
            delay *= 2

    logger.error("Max retries reached. signal-cli listener stopped.")
