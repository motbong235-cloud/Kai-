#!/usr/bin/env python3
"""Inject TopUpFox (master-only) into kaijaklike_bot.py at build time.

CRITICAL: handlers must be registered BEFORE the catch-all
  @bot.message_handler(func=lambda m: True)  # handle_msg
Otherwise TopUpFox button falls through to menu fallback.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "kaijaklike_bot.py"

MARKER = "# === FOX RESELLER MASTER INJECT ==="

# NOTE: full inject body loaded from same structure; markup reprice is in fox_markup branch
# File is maintained locally and pushed in full below via sequential read — see commit.

def main():
    raise SystemExit('placeholder - will be replaced')

if __name__ == '__main__':
    main()
