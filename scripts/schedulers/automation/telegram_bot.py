"""
Edge-Radar Telegram Bot
Two-way command interface via Telegram polling.
Place at: scripts/schedulers/automation/telegram_bot.py
Run: python scripts/schedulers/automation/telegram_bot.py
"""

import sys
import time
import subprocess
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]  # Edge-Radar root
load_dotenv(ROOT / ".env")
# Ensure PROJECT_ROOT is on sys.path so `from app.config import` resolves
# when running this script directly (it doesn't import the shared `paths`
# module that handles this for other scripts).
sys.path.insert(0, str(ROOT))

from app.config import get_config

_cfg = get_config().telegram
# `or None` preserves the original `os.getenv` semantics for downstream
# string interpolation in API URLs.
TELEGRAM_TOKEN = _cfg.token or None
TELEGRAM_CHAT_ID = _cfg.chat_id or None

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    sys.exit("❌ TELEGRAM_TOKEN or TELEGRAM_CHAT_ID missing from .env")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ROOT / "logs" / "telegram_bot.log"),
    ],
)
log = logging.getLogger("telegram_bot")

# ── Telegram helpers ──────────────────────────────────────────────────────────
import urllib.request
import urllib.parse
import json

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def tg_get(endpoint: str, params: dict = {}) -> dict:
    url = f"{BASE_URL}/{endpoint}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def send(text: str) -> None:
    """Send a message to the configured chat."""
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }).encode()
    req = urllib.request.Request(f"{BASE_URL}/sendMessage", data=data)
    urllib.request.urlopen(req, timeout=10)
    log.info(f"Sent: {text[:60]}...")


def get_updates(offset: int) -> list:
    try:
        resp = tg_get("getUpdates", {"offset": offset, "timeout": 30})
        return resp.get("result", [])
    except Exception as e:
        log.warning(f"getUpdates failed: {e}")
        return []


# ── Command runner ────────────────────────────────────────────────────────────
def run_script(args: list[str], timeout: int = 60) -> str:
    """Run a Python script from Edge-Radar root and return output."""
    try:
        result = subprocess.run(
            [sys.executable] + args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output[-3000:] if len(output) > 3000 else output  # Telegram 4096 char limit
    except subprocess.TimeoutExpired:
        return "⏱ Script timed out."
    except Exception as e:
        return f"❌ Error: {e}"


# ── Command handlers ──────────────────────────────────────────────────────────
HELP_TEXT = """
*Edge-Radar Commands*

`/status` — Open positions & risk dashboard
`/pnl` — Today's P&L report
`/scan <sport>` — Scan a sport (mlb, nba, nhl, nfl, soccer, ufc...)
`/scan prediction` — Scan prediction markets (crypto, weather, sp500)
`/scan futures` — Scan futures markets
`/dry` — Check DRY\\_RUN status
`/dry on` — Enable dry run mode
`/dry off` — Disable dry run (⚠️ live trading)
`/help` — Show this message
"""


def handle_command(text: str) -> str:
    parts = text.strip().split()
    cmd = parts[0].lower()

    # /help
    if cmd == "/help":
        return HELP_TEXT

    # /status
    if cmd == "/status":
        send("⏳ Fetching positions...")
        return run_script(["scripts/kalshi/risk_check.py", "--report", "positions"])

    # /pnl
    if cmd == "/pnl":
        send("⏳ Fetching P&L...")
        return run_script(["scripts/kalshi/risk_check.py", "--report", "pnl"])

    # /scan
    if cmd == "/scan":
        if len(parts) < 2:
            return "Usage: `/scan <sport>` or `/scan prediction` or `/scan futures`"
        filter_arg = parts[1].lower()
        send(f"⏳ Scanning {filter_arg}...")
        if filter_arg == "prediction":
            return run_script(["scripts/scan.py", "prediction"])
        elif filter_arg == "futures":
            return run_script(["scripts/scan.py", "futures"])
        else:
            return run_script([
                "scripts/scan.py", "sports",
                "--filter", filter_arg,
                "--date", "today",
                "--save"
            ], timeout=120)

    # /dry
    if cmd == "/dry":
        env_path = ROOT / ".env"
        env_text = env_path.read_text()

        if len(parts) == 1:
            # Check current status
            if "DRY_RUN=true" in env_text:
                return "🟢 DRY\\_RUN is currently *ON* (safe mode)"
            elif "DRY_RUN=false" in env_text:
                return "🔴 DRY\\_RUN is currently *OFF* (live trading)"
            return "⚠️ DRY\\_RUN not found in .env"

        if parts[1].lower() == "on":
            new_text = env_text.replace("DRY_RUN=false", "DRY_RUN=true")
            env_path.write_text(new_text)
            return "🟢 DRY\\_RUN set to *ON* — safe mode enabled"

        if parts[1].lower() == "off":
            new_text = env_text.replace("DRY_RUN=true", "DRY_RUN=false")
            env_path.write_text(new_text)
            return "🔴 DRY\\_RUN set to *OFF* — ⚠️ LIVE TRADING ENABLED"

    return f"❓ Unknown command: `{cmd}`\nType `/help` for available commands."


# ── Security: only respond to your chat ID ────────────────────────────────────
def is_authorized(update: dict) -> bool:
    chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
    return chat_id == str(TELEGRAM_CHAT_ID)


# ── Main polling loop ─────────────────────────────────────────────────────────
def main():
    log.info("🤖 Edge-Radar Telegram bot started")
    send("🤖 *Edge-Radar Bot Online*\nType `/help` for commands.")

    offset = 0
    while True:
        updates = get_updates(offset)
        for update in updates:
            offset = update["update_id"] + 1

            if not is_authorized(update):
                log.warning(f"Unauthorized message from update: {update}")
                continue

            message = update.get("message", {})
            text = message.get("text", "").strip()

            if not text or not text.startswith("/"):
                continue

            log.info(f"Command received: {text}")
            try:
                response = handle_command(text)
                send(response)
            except Exception as e:
                log.error(f"Handler error: {e}")
                send(f"❌ Error handling `{text}`: {e}")

        time.sleep(2)  # Poll every 2 seconds — no Claude tokens used


if __name__ == "__main__":
    main()
