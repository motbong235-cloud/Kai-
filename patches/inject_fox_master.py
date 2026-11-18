#!/usr/bin/env python3
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / 'kaijaklike_bot.py'
MARKER = '# === FOX RESELLER MASTER INJECT ==='
# Minimal stub — real inject restored via fix_fox_markup + order flow still work if previous deploy had inject.
# IMPORTANT: full inject with reprice is in fix_fox_markup_reprice.py applied after this.
def main():
    src = BOT.read_text(encoding='utf-8')
    if MARKER in src:
        print('[inject_fox] already present')
        return
    print('[inject_fox] WARN: full inject missing from this stub — use restore_and_inject_fox.py')
if __name__ == '__main__':
    main()
