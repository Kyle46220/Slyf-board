import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional
from app.config import settings
from app.totp import verify_totp

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://\S+")


def parse_message(text: str, attachments: list) -> Optional[dict]:
    """Extract TOTP and content from a raw Signal message. Returns None if malformed."""
    text = text.strip() if text else ""
    if not text and not attachments:
        return None

    if settings.bypass_totp:
        parts = text.split(" ", 1)
        code = parts[0] if parts else ""
        if len(code) == 6 and code.isdigit():
            extracted_code = code
            body = parts[1].strip() if len(parts) > 1 else None
        else:
            extracted_code = "BYPASS"
            if text.startswith("BYPASS "):
                body = text[7:].strip()
            elif text == "BYPASS":
                body = None
            else:
                body = text if text else None
    else:
        if not text:
            return None
        parts = text.split(" ", 1)
        code = parts[0]
        if len(code) != 6 or not code.isdigit():
            return None
        extracted_code = code
        body = parts[1].strip() if len(parts) > 1 else None

    # Determine content type
    if attachments:
        first = attachments[0].get("content_type", "")
        if first.startswith("image/"):
            content_type = "image"
        elif first.startswith("video/"):
            content_type = "video"
        else:
            content_type = "text"
    elif body and URL_RE.search(body):
        # Treat as link if it contains a URL and no attachments
        content_type = "link"
    else:
        content_type = "text"

    return {
        "totp": extracted_code,
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
                                    if not settings.bypass_totp and not verify_totp(parsed["totp"], settings.totp_secret):
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
        "-n", "0",  # Don't show old lines, only new ones
        "-o", "cat"  # Output raw log lines
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        logger.info("Started journalctl process for Signal CLI logs")

        current_envelope_lines = []

        async def flush_envelope():
            nonlocal current_envelope_lines
            if not current_envelope_lines:
                return
                
            lines = current_envelope_lines
            current_envelope_lines = []

            body = ""
            attachments_files = []
            timestamp = str(hash("".join(lines)))
            seen_previews = False
            sender = None
            is_group = False
            has_native_mention = False
            in_mentions = False
            in_body = False

            for l in lines:
                l_strip = l.strip()
                if "Message timestamp:" in l:
                    in_body = False
                    timestamp = l.split(":", 1)[1].strip()
                elif l.startswith("Body:"):
                    in_body = True
                    body = l.split(":", 1)[1].strip()
                elif l_strip in ["Previews:", "Mentions:"] or l_strip.startswith("Group info:") or l_strip.startswith("Envelope from:") or "Stored plaintext in:" in l:
                    in_body = False
                    if l_strip == "Previews:": seen_previews = True
                    elif l_strip == "Mentions:": in_mentions = True
                    elif l_strip.startswith("Group info:"): is_group = True
                    elif "Stored plaintext in:" in l:
                        file_path = l.split("Stored plaintext in:", 1)[1].strip()
                        attachments_files.append(file_path)
                elif in_body:
                    # Strip Signal metadata footers that sometimes appear in logs
                    if "(with profile key)" in l_strip or l_strip == "Data message":
                        in_body = False
                        continue
                    # Append multi-line body content
                    if body:
                        body += "\n" + l # Keep original line for spacing, but strip later
                    else:
                        body = l
                elif in_mentions and l_strip.startswith("-"):
                    if "+61485676958" in l or "f074c34d-7706-44e6-9a24-b71c2b4cf673" in l:
                        has_native_mention = True

            if body:
                body = body.strip()

            if is_group:
                # Accept if they use the hashtag or natively tag the bot
                if "@slyfebot.21" not in body.lower() and not has_native_mention:
                    return
                # Strip the mention from the body before processing
                body = re.sub(r'(?i)@slyfebot\.21\s*', '', body).strip()
                # Strip native mention replacement characters if present
                body = body.replace('\ufffc', '').strip()

            if not body and not attachments_files:
                return

            if timestamp in processed_hashes:
                return
            processed_hashes.add(timestamp)

            attachments = []
            for att_file in attachments_files:
                try:
                    src_path = Path(att_file)
                    if src_path.exists():
                        temp_file = temp_media_dir / f"{timestamp}_{src_path.name}"
                        import shutil
                        shutil.copy2(src_path, temp_file)
                        
                        ext = src_path.suffix.lower()
                        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                            content_type = "image/" + ext.strip('.')
                        elif ext in ['.mp4', '.mov', '.avi', '.webm']:
                            content_type = "video/" + ext.strip('.')
                        else:
                            content_type = "unknown"
                            
                        attachments.append({
                            "content_type": content_type,
                            "filename": str(temp_file)
                        })
                        logger.info(f"Copied attachment to temp dir: {temp_file}")
                except Exception as e:
                    logger.error(f"Failed to copy attachment: {e}")

            # TOTP Bypass logic
            if settings.bypass_totp:
                totp_match = re.search(r"^(\d{6})\s*(.*)", body)
                if totp_match:
                    totp_code = totp_match.group(1)
                    message_body = totp_match.group(2).strip()
                    full_message = f"{totp_code} {message_body}".strip() if message_body else totp_code
                else:
                    totp_code = "BYPASS"
                    message_body = body
                    # Don't prepend BYPASS to the body if the original message had no text
                    full_message = f"{totp_code} {message_body}".strip() if message_body else ""
            else:
                totp_match = re.search(r"^(\d{6})\s*(.*)", body)
                if not totp_match:
                    return
                totp_code = totp_match.group(1)
                message_body = totp_match.group(2).strip()
                full_message = f"{totp_code} {message_body}".strip()

            parsed = parse_message(full_message, attachments)
            if parsed is None:
                logger.warning(f"Failed to parse message from logs: {totp_code}")
                return

            # Verify TOTP
            if not settings.bypass_totp and not verify_totp(parsed["totp"], settings.totp_secret):
                logger.warning(f"Invalid TOTP code from logs: {parsed['totp']}")
                return

            # Process the message
            await on_message(parsed)
            logger.info(f"Message from logs processed: {totp_code}")

            # Send thank you reply
            if sender and not is_group:
                import random
                import json
                
                emojis = ["😊", "👍", "🎉", "🔥", "🚀", "✨", "🙌", "😎", "🥳", "💯", "🎈", "✌️"]
                random_emojis = "".join(random.choices(emojis, k=3))
                reply_text = f"Thank you! {random_emojis}"
                
                try:
                    reader, writer = await asyncio.open_unix_connection("/var/run/signal-cli/socket")
                    msg = {
                        "jsonrpc": "2.0",
                        "method": "send",
                        "params": {
                            "recipient": [sender],
                            "message": reply_text
                        },
                        "id": 1
                    }
                    writer.write((json.dumps(msg) + "\n").encode())
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                    logger.info(f"Sent thank you reply to {sender}")
                except Exception as e:
                    logger.error(f"Failed to send reply to {sender}: {e}")

        while True:
            try:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
                if not line:
                    break
                line_str = line.decode().strip()
                if "Envelope from:" in line_str:
                    await flush_envelope()
                current_envelope_lines.append(line_str)
            except asyncio.TimeoutError:
                await flush_envelope()

    except Exception as e:
        logger.error(f"Error in Signal CLI log parsing: {e}")
    finally:
        if 'process' in locals():
            process.terminate()
            await process.wait()
