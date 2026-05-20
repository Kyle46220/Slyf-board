# Signal CLI Log Parser Metadata Stripping Fix
## Date: 2026-05-20

---

## Issue
**Problem:** When a user sends a post from Signal with an attachment (e.g. an image) and text content, Signal CLI log metadata (such as profile keys, attachment paths, upload timestamps, size, and dimensions) is appended to the message body and displayed on the board.

**Example log output appended to post body:**
```
With profile key
Attachments:
  Attachment:
    Content-Type: image/jpeg
    Type: Pointer
    Id: MFzmRmz6V8Zj0ziISDNr.jpg
    Upload timestamp: 1779246453723 (2026-05-20T03:07:33.723Z)
    Size: 79192 bytes
    Dimensions: 1000x1000
```

---

## Root Cause
In `backend/app/signal_listener.py`, the `parse_signal_cli_logs` function monitors the output of `journalctl -u signal-cli`. When it matches the `Body:` line, it sets `in_body = True` and starts capturing all subsequent lines as multi-line post content. 

Signal CLI outputs metadata footers like `With profile key` and the `Attachments:` block at the end of the log group. Because the parser was only checking for `(with profile key)` (with parentheses) or `Data message` to stop capturing the body, any other unhandled metadata footer lines (such as `With profile key` without parentheses, `Attachments:`, `Content-Type:`, etc.) kept `in_body = True` and were concatenated into the post body.

---

## Solution Implemented
Updated the log parsing loop inside `backend/app/signal_listener.py` to stop appending body content and set `in_body = False` whenever any of the metadata or attachment key lines are encountered.

### Code Modification

```python
                elif in_body:
                    # Strip Signal metadata footers that sometimes appear in logs
                    l_lower = l_strip.lower()
                    if (
                        "profile key" in l_lower or
                        l_strip == "Data message" or
                        l_strip.startswith("Attachments:") or
                        l_strip.startswith("Attachment:") or
                        l_lower.startswith("content-type:") or
                        l_lower.startswith("type:") or
                        l_lower.startswith("id:") or
                        l_lower.startswith("upload timestamp:") or
                        l_lower.startswith("size:") or
                        l_lower.startswith("dimensions:")
                    ):
                        in_body = False
                        continue
                    # Append multi-line body content
                    if body:
                        body += "\n" + l # Keep original line for spacing, but strip later
                    else:
                        body = l
```

This successfully captures the text message content without appending any trailing Signal CLI metadata or attachment pointers.

---

## Verification
- Unit and router tests passed.
- Production deployment has been updated and restarted.
