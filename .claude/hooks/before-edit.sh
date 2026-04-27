#!/usr/bin/env bash
# Block edits to security-critical files and directories

BLOCKED_PATHS=(
  "backend/.env"
  "token-generator/.env.local"
  "/var/signal-cli/"
  "/opt/backend/.env"
)

CHECKED_FILES=()

# Check if any files being edited are in blocked paths
for blocked in "${BLOCKED_PATHS[@]}"; do
  for file in "$@"; do
    if [[ "$file" == *"$blocked"* ]]; then
      echo "❌ BLOCKED: Cannot edit $file"
      echo "Contains sensitive configuration or secrets"
      echo "Use GCP console or Netlify dashboard for environment variables"
      exit 1
    fi
  done
done

exit 0