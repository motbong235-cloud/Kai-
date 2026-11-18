#!/usr/bin/env python3
"""Harden cost_rate KeyError on services missing the field (e.g. Fox)."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "kaijaklike_bot.py"

def main():
    src = BOT.read_text(encoding="utf-8")
    n = 0
    for old, new in [
        ('_smm_sell_rate(s["cost_rate"], slug)', '_smm_sell_rate(s.get("cost_rate", 0), slug)'),
        ("_smm_sell_rate(s['cost_rate'], slug)", "_smm_sell_rate(s.get('cost_rate', 0), slug)"),
    ]:
        c = src.count(old)
        if c:
            src = src.replace(old, new)
            n += c
    BOT.write_text(src, encoding="utf-8")
    print(f"[fix_cost_rate] replaced {n} unsafe cost_rate access")

if __name__ == "__main__":
    main()
