import asyncio
import json
import logging
import re
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
    Connect to signal-cli JSON-RPC socket and listen for messages via receive method.
    Uses polling with manual receive mode.
    """
    delay = 1
    retries = 0
    max_retries = 10

    while retries < max_retries:
        try:
            # Create Unix socket connection
            reader, writer = await asyncio.open_unix_connection(signal_socket_path)
            logger.info("Connected to signal-cli socket")

            delay = 1
            retries = 0

            while True:
                try:
                    # Call receive method without timeout to get any pending messages
                    receive_msg = {
                        "jsonrpc": "2.0",
                        "method": "receive",
                        "params": {"timeout": 0},
                        "id": 1
                    }
                    writer.write(json.dumps(receive_msg).encode() + b"\n")
                    await writer.drain()

                    # Read response
                    response_line = await asyncio.wait_for(reader.readline(), timeout=10)
                    if not response_line:
                        logger.warning("Signal CLI socket closed, reconnecting...")
                        break

                    response = json.loads(response_line.decode())

                    # Check for error about messages already being received
                    if "error" in response:
                        error_msg = response['error'].get('message', '')
                        if 'already being received' in error_msg:
                            # Messages are being received, parse Signal CLI logs instead
                            logger.info("Messages already being received, switching to log parsing")
                            await parse_signal_cli_logs(on_message)
                            return
                        logger.error(f"Signal CLI error: {response['error']}")
                        await asyncio.sleep(5)
                        continue

                    # Check for result
                    if "result" in response:
                        result = response["result"]
                        if result == "No new messages":
                            # Wait before polling again
                            await asyncio.sleep(2)
                            continue

                        # Process messages
                        if isinstance(result, list):
                            for envelope in result:
                                try:
                                    data_msg = envelope.get("dataMessage", {})

                                    # Only process messages with content
                                    if "message" not in data_msg and "attachments" not in data_msg:
                                        continue

                                    text = data_msg.get("message", "") or ""
                                    attachments = data_msg.get("attachments", [])

                                    logger.info(f"Received Signal message: {text[:50] if text else '[no text]'}...")

                                    # strip sender metadata immediately
                                    envelope.pop("source", None)
                                    envelope.pop("sourceNumber", None)
                                    envelope.pop("sourceName", None)
                                    envelope.pop("sourceDevice", None)
                                    envelope.pop("sourceUuid", None)
                                    data_msg.pop("timestamp", None)

                                    parsed = parse_message(text, attachments)
                                    if parsed is None:
                                        logger.warning(f"Failed to parse message: {text[:100]}")
                                        continue
                                    if not verify_totp(parsed["totp"], settings.totp_secret):
                                        logger.warning(f"Invalid TOTP code: {parsed['totp']}")
                                        continue

                                    await on_message(parsed)
                                    logger.info("Message processed successfully")

                                except Exception as e:
                                    logger.error(f"Error processing message: {e}")

                except asyncio.TimeoutError:
                    logger.warning("Timeout receiving from Signal CLI")
                    continue
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON: {e}")
                    await asyncio.sleep(1)
                    continue
                except Exception as e:
                    logger.error(f"Error in receive loop: {e}")
                    break

            writer.close()
            await writer.wait_closed()

        except Exception as e:
            retries += 1
            logger.error(f"signal-cli connection failed (attempt {retries}/{max_retries}): {e}")
            if retries < max_retries:
                await asyncio.sleep(min(delay, 60))
                delay *= 2

    logger.error("Max retries reached. signal-cli listener stopped.")


async def parse_signal_cli_logs(on_message):
    """
    Parse Signal CLI journal logs for incoming messages.
    This is a fallback when receive method cannot be used.
    """
    import subprocess
    import shutil

    logger.info("Starting Signal CLI log parsing")

    # Track processed message hashes to avoid duplicates
    processed_hashes = set()

    # Temporary directory for processing Signal attachments
    temp_media_dir = Path("/tmp/signal_media_processing")
    temp_media_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "journalctl",
        "-u", "signal-cli",
        "-f",  # Follow logs
        "--no-tail",  # Don't show old lines, only new ones
        "-o", "cat"  # Output raw log lines
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        logger.info("Started journalctl process for Signal CLI logs")

        # Parse log lines
        async for line in process.stdout:
            line_str = line.decode().strip()

            # Look for message body (TOTP code)
            if "Body:" in line_str:
                try:
                    # Extract TOTP code (6 digits) from Body: line
                    totp_match = re.search(r"Body:\s*(\d{6})", line_str)
                    if not totp_match:
                        continue

                    totp_code = totp_match.group(1)

                    # Read the next line for the actual message body
                    message_body = ""
                    try:
                        next_line = await asyncio.wait_for(process.stdout.readline(), timeout=0.5)
                        next_line_str = next_line.decode().strip()
                        # Check if this is the actual message body (not metadata)
                        if next_line_str and not next_line_str.startswith("With") and not next_line_str.startswith("Attachments") and not next_line_str.startswith("Server timestamps"):
                            message_body = next_line_str
                            logger.info(f"Found message body: {message_body}")
                    except asyncio.TimeoutError:
                        pass  # No body line, that's okay

                    # Combine TOTP and body for parsing
                    full_message = f"{totp_code} {message_body}".strip()

                    # Create a unique hash for this message (using timestamp + partial content)
                    msg_hash = f"{hash(line_str)}_{totp_code}"
                    if msg_hash in processed_hashes:
                        continue
                    processed_hashes.add(msg_hash)

                    # Look for attachment info in next few lines
                    attachment_file = None

                    # Read more lines to check for attachments (longer timeout)
                    for _ in range(20):
                        try:
                            next_line = await asyncio.wait_for(process.stdout.readline(), timeout=0.5)
                            next_line_str = next_line.decode().strip()

                            # Check for stored attachment path
                            if "Stored plaintext in:" in next_line_str:
                                attachment_match = re.search(r"Stored plaintext in:\s*(\/[^\s]+)", next_line_str)
                                if attachment_match:
                                    attachment_file = attachment_match.group(1)
                                    logger.info(f"Found attachment: {attachment_file}")

                            # Stop on new message envelope
                            if "Envelope from:" in next_line_str:
                                break
                        except asyncio.TimeoutError:
                            # Timeout waiting for next line, proceed with current message
                            break

                    # Create attachments list
                    attachments = []
                    if attachment_file:
                        # Copy attachment to temp directory for processing
                        try:
                            src_path = Path(attachment_file)
                            if src_path.exists():
                                # Create unique temp filename
                                temp_file = temp_media_dir / f"{msg_hash}_{src_path.name}"
                                shutil.copy2(src_path, temp_file)

                                content_type = "image/jpeg" if attachment_file.endswith(".jpg") or attachment_file.endswith(".jpeg") else "unknown"
                                attachments.append({
                                    "content_type": content_type,
                                    "filename": str(temp_file)
                                })
                                logger.info(f"Copied attachment to temp dir: {temp_file}")
                        except Exception as e:
                            logger.error(f"Failed to copy attachment: {e}")

                    # Parse the message
                    parsed = parse_message(full_message, attachments)
                    if parsed is None:
                        logger.warning(f"Failed to parse message from logs: {totp_code}")
                        continue

                    # Verify TOTP
                    if not verify_totp(parsed["totp"], settings.totp_secret):
                        logger.warning(f"Invalid TOTP code from logs: {parsed['totp']}")
                        continue

                    # Process the message
                    await on_message(parsed)
                    logger.info(f"Message from logs processed: {totp_code} - {message_body[:30] if message_body else '[no body]'}")

                except Exception as e:
                    logger.error(f"Error parsing Signal CLI log line: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error in Signal CLI log parsing: {e}")
    finally:
        if 'process' in locals():
            process.terminate()
            await process.wait()
