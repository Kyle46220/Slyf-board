#!/usr/bin/env bash
# Format Python files after edits

# Check if any edited files are Python
PYTHON_FILES=()

for file in "$@"; do
  if [[ "$file" == *.py ]]; then
    PYTHON_FILES+=("$file")
  fi
done

# Format Python files if any were edited
if [ ${#PYTHON_FILES[@]} -gt 0 ]; then
  echo "🔧 Formatting Python files..."

  # Check if black is available
  if command -v black &> /dev/null; then
    black "${PYTHON_FILES[@]}"
  else
    echo "⚠️  black not found, skipping formatting"
    echo "Install: pip install black"
  fi

  # Check if isort is available
  if command -v isort &> /dev/null; then
    isort "${PYTHON_FILES[@]}"
  fi
fi

exit 0
