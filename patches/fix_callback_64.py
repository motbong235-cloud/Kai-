#!/usr/bin/env python3
"""Truncate Telegram callback_data to 64 bytes; one icon per category button."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "kaijaklike_bot.py"
MARKER = "# === CALLBACK 64 FIX ==="

FIX = '''
# === CALLBACK 64 FIX ===
def _tg_cb(data: str, limit: int = 64) -> str:
    """Telegram callback_data max 64 BYTES — truncate safely."""
    if not data:
        return data
    while len(data.encode("utf-8")) > limit and data:
        data = data[:-1]
    return data
'''

def main():
    src = BOT.read_text(encoding="utf-8")
    if MARKER not in src:
        needle = "def smm_cat_kb():"
        if needle not in src:
            raise SystemExit("smm_cat_kb not found")
        src = src.replace(needle, FIX + "\n\ndef smm_cat_kb():", 1)

    src = src.replace('callback_data=f"smmcat:{cat}"', 'callback_data=_tg_cb(f"smmcat:{cat}")')
    src = src.replace('callback_data=f"smmsvc:{slug}"', 'callback_data=_tg_cb(f"smmsvc:{slug}")')

    old = """        if _leading_emoji(cat):
            label = cat
        else:
            icon = "📱"
            for key, ico in PLATFORM_ICONS.items():
                if key in cat.lower():
                    icon = ico
                    break
            label = f"{icon}  {cat}"
"""
    new = """        # Strip any leading emoji from cat, then add exactly ONE platform icon
        cat_plain = cat
        for _ in range(4):
            e = _leading_emoji(cat_plain)
            if not e:
                break
            cat_plain = cat_plain.replace(e, "", 1).strip()
        icon = "🎮"
        for key, ico in PLATFORM_ICONS.items():
            if key in cat_plain.lower():
                icon = ico
                break
        cl = cat_plain.lower()
        if any(x in cl for x in ("free fire", "freefire", "mlbb", "mobile legend", "pubg", "roblox", "genshin", "honor", "game")):
            icon = "🎮"
        label = f"{icon}  {cat_plain}"
"""
    if old in src:
        src = src.replace(old, new, 1)
        print("[fix_callback] one-icon category label")
    else:
        print("[fix_callback] WARN: category label block not found")

    BOT.write_text(src, encoding="utf-8")
    print("[fix_callback] applied")

if __name__ == "__main__":
    main()
