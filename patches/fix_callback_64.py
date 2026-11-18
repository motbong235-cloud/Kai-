#!/usr/bin/env python3
"""Fix BUTTON_DATA_INVALID: short callback keys + one category icon."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "kaijaklike_bot.py"
MARKER = "# === CALLBACK 64 FIX ==="

FIX = r'''
# === CALLBACK 64 FIX ===
# Telegram callback_data max 64 bytes. Map short keys → real cat/slug.
_CB_CAT_MAP = {}   # key -> category string
_CB_SVC_MAP = {}   # key -> service slug

def _cb_key(prefix: str, value: str, store: dict) -> str:
    """Build short stable callback_data under 64 bytes."""
    import hashlib
    h = hashlib.md5(value.encode("utf-8")).hexdigest()[:10]
    store[h] = value
    return f"{prefix}:{h}"

def _cb_resolve(data: str, prefix: str, store: dict):
    """Resolve short key or legacy full value after prefix:."""
    if not data or not data.startswith(prefix + ":"):
        return data
    key = data[len(prefix) + 1:]
    return store.get(key, key)
'''

def main():
    src = BOT.read_text(encoding="utf-8")

    if "def _tg_cb(" in src and MARKER in src:
        start = src.find(MARKER)
        end = src.find("def smm_cat_kb():", start)
        if start >= 0 and end > start:
            src = src[:start] + src[end:]
            print("[fix_callback] removed old truncate block")

    if MARKER not in src:
        needle = "def smm_cat_kb():"
        if needle not in src:
            raise SystemExit("smm_cat_kb not found")
        src = src.replace(needle, FIX + "\n\ndef smm_cat_kb():", 1)
        print("[fix_callback] injected maps")

    src = src.replace(
        'callback_data=f"smmcat:{cat}"',
        'callback_data=_cb_key("smmcat", cat, _CB_CAT_MAP)',
    )
    src = src.replace(
        'callback_data=_tg_cb(f"smmcat:{cat}")',
        'callback_data=_cb_key("smmcat", cat, _CB_CAT_MAP)',
    )
    src = src.replace(
        'callback_data=f"smmsvc:{slug}"',
        'callback_data=_cb_key("smmsvc", slug, _CB_SVC_MAP)',
    )
    src = src.replace(
        'callback_data=_tg_cb(f"smmsvc:{slug}")',
        'callback_data=_cb_key("smmsvc", slug, _CB_SVC_MAP)',
    )

    if 'cat = _cb_resolve(call.data, "smmcat", _CB_CAT_MAP)' not in src:
        src = src.replace(
            '''@bot.callback_query_handler(func=lambda c: c.data.startswith("smmcat:"))
def cb_smmcat(call):
    uid = call.message.chat.id
    cat = call.data[7:]
''',
            '''@bot.callback_query_handler(func=lambda c: c.data.startswith("smmcat:"))
def cb_smmcat(call):
    uid = call.message.chat.id
    cat = _cb_resolve(call.data, "smmcat", _CB_CAT_MAP)
''',
            1,
        )
        print("[fix_callback] smmcat resolve")

    if 'slug = _cb_resolve(call.data, "smmsvc", _CB_SVC_MAP)' not in src:
        src = src.replace(
            '''@bot.callback_query_handler(func=lambda c: c.data.startswith("smmsvc:"))
def cb_smmsvc(call):
    uid  = call.message.chat.id
    slug = call.data[7:]
''',
            '''@bot.callback_query_handler(func=lambda c: c.data.startswith("smmsvc:"))
def cb_smmsvc(call):
    uid  = call.message.chat.id
    slug = _cb_resolve(call.data, "smmsvc", _CB_SVC_MAP)
''',
            1,
        )
        print("[fix_callback] smmsvc resolve")

    old_lead = """        if _leading_emoji(cat):
            label = cat
        else:
            icon = "📱"
            for key, ico in PLATFORM_ICONS.items():
                if key in cat.lower():
                    icon = ico
                    break
            label = f"{icon}  {cat}"
"""
    new_lead = """        cat_plain = cat
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
    if old_lead in src:
        src = src.replace(old_lead, new_lead, 1)
        print("[fix_callback] one-icon label")
    elif "cat_plain = cat" in src:
        print("[fix_callback] one-icon already present")
    else:
        print("[fix_callback] WARN label block missing")

    BOT.write_text(src, encoding="utf-8")
    print("[fix_callback] applied")


if __name__ == "__main__":
    main()
