#!/usr/bin/env bash
set -euo pipefail

INPUT=$(cat)

TRANSCRIPT=$(echo "$INPUT" | jq -r '
  .transcript |
  if type == "string" then .
  elif type == "array" then
    map(.content | if type == "string" then . elif type == "array" then map(.text // "") | join("") else tostring end) | join("\n")
  else ""
end
' 2>/dev/null || echo "")

# jq recursively extracts all strings, decoding \u003c/\u003e Unicode escapes.
# Claude Code uses HTML-safe JSON encoding, so < > are escaped — grep on raw input won't work.
ALL_STRINGS=$(echo "$INPUT" | jq -r '.. | strings' 2>/dev/null || echo "")

if echo "$ALL_STRINGS" | grep -qF '<promise>COMPLETE</promise>' || echo "$TRANSCRIPT" | grep -qF '<promise>COMPLETE</promise>'; then
  echo '{"decision": "approve", "reason": "Ralph Loop: promise received. Done."}'
  exit 0
else
  PROMPT=$(cat "$(dirname "")/prompt.md" 2>/dev/null || echo "Continue working. Output <promise>COMPLETE</promise> when all tasks pass.")
  echo "{\"decision\": \"block\", \"reason\": \"Ralph Loop: no completion promise found.\", \"systemMessage\": $(echo "$PROMPT" | jq -Rs .)}"
  exit 2
fi