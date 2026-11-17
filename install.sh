#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/5] Checking python3 installation..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 was not found in PATH. Install Python 3.10+ and retry." >&2
  exit 1
fi

echo "[2/5] Creating virtual environment in $SCRIPT_DIR/.venv..."
if [ ! -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  python3 -m venv "$SCRIPT_DIR/.venv"
fi

echo "[3/5] Upgrading pip and installing dependencies..."
"$SCRIPT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$SCRIPT_DIR/.venv/bin/pip" install "mcp[cli]" playwright

echo "[4/5] Installing Playwright Chromium browser..."
"$SCRIPT_DIR/.venv/bin/python" -m playwright install chromium

echo "[5/5] Generating mcp_config_snippet.json..."
"$SCRIPT_DIR/.venv/bin/python" - <<EOF
import json
import pathlib

root = pathlib.Path("$SCRIPT_DIR")
cfg = {
    "mcpServers": {
        "dzen-mcp": {
            "command": str(root / ".venv" / "bin" / "python"),
            "args": [str(root / "server.py")],
        }
    }
}
out = root / "mcp_config_snippet.json"
text = json.dumps(cfg, indent=2, ensure_ascii=False)
out.write_text(text + "\n", encoding="utf-8")
print("\n=== Copy this into your mcp_config.json ===")
print(text)
print("==========================================")
print(f"Saved to: {out}")
EOF

echo "Done! Add the JSON above to your MCP config and click Refresh."
