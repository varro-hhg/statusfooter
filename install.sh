#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${HOME}/.local/bin/statusfooter"
CONFIG_DIR="${HOME}/.config/statusfooter"
CACHE_DIR="${HOME}/.cache/statusfooter"
CONFIG_FILE="${CONFIG_DIR}/config.json"

mkdir -p "$(dirname "$DEST")" "$CONFIG_DIR" "$CACHE_DIR"

install -m755 "${SCRIPT_DIR}/statusfooter" "$DEST"
echo "Installed: $DEST"

if [ ! -f "$CONFIG_FILE" ]; then
  cat > "$CONFIG_FILE" <<EOF
{
  "ak": "REPLACE_ME",
  "sk": "REPLACE_ME",
  "cache_ttl": 60
}
EOF
  chmod 600 "$CONFIG_FILE"
  echo "Created: $CONFIG_FILE  (chmod 600)"
  echo "→ Edit it and replace REPLACE_ME with your Volcengine AccessKeyId / SecretAccessKey."
else
  echo "Existing config left untouched: $CONFIG_FILE"
fi

cat <<EOF

Next: add this to ~/.claude/settings.json under the top-level object:

  "statusLine": {
    "type": "command",
    "command": "${DEST}"
  }

(If \$HOME/.local/bin is on PATH, the command can just be "statusfooter".)
EOF
