#!/usr/bin/env python3
"""Fix KeyError cost_rate + normalize Fox/flat services at runtime."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "kaijaklike_bot.py"
MARKER = "# === COST_RATE HARDEN ==="

BOOTSTRAP = r'''
# === COST_RATE HARDEN ===
def _normalize_smm_service(s: dict) -> dict:
    """Ensure cost_rate / flat_price exist (Fox & legacy entries)."""
    if not isinstance(s, dict):
        return s
    if "cost_rate" not in s:
        if s.get("flat_price") is not None:
            s["cost_rate"] = 0
        elif s.get("price") is not None:
            try:
                s["flat_price"] = float(s["price"])
            except Exception:
                s["flat_price"] = 0
            s["cost_rate"] = 0
        else:
            s["cost_rate"] = 0
    if s.get("fox") and s.get("flat_price") is None and s.get("price") is not None:
        try:
            s["flat_price"] = float(s["price"])
        except Exception:
            pass
        s["cost_rate"] = 0
    return s

def _normalize_all_smm_services():
    try:
        changed = False
        for slug, s in list(smm_services.items()):
            before = (s.get("cost_rate"), s.get("flat_price"))
            _normalize_smm_service(s)
            after = (s.get("cost_rate"), s.get("flat_price"))
            if before != after:
                changed = True
        if changed:
            _save(SMM_SVC_FILE, smm_services)
            logging.getLogger(__name__).info("[smm] normalized cost_rate/flat_price on services")
    except Exception as e:
        logging.getLogger(__name__).warning("[smm] normalize: %s", e)

_normalize_all_smm_services()
'''

def main():
    src = BOT.read_text(encoding="utf-8")

    n = src.count('s["cost_rate"]') + src.count("s['cost_rate']")
    src = src.replace('s["cost_rate"]', 's.get("cost_rate", 0)')
    src = src.replace("s['cost_rate']", "s.get('cost_rate', 0)")
    print(f"[fix_cost_rate] safe-get replacements around cost_rate keys: {n}")

    old_qty2 = '''def smm_qty_kb(slug, s, uid=None):
    sr    = _smm_sell_rate(s.get("cost_rate", 0), slug)
'''
    old_qty3 = '''def smm_qty_kb(slug, s, uid=None):
    sr    = _smm_sell_rate(s["cost_rate"], slug)
'''
    new_qty_head = '''def smm_qty_kb(slug, s, uid=None):
    try:
        s = _normalize_smm_service(s)
    except Exception:
        pass
    sr    = _smm_sell_rate(s.get("cost_rate", 0), slug)
'''
    if 'def smm_qty_kb(slug, s, uid=None):\n    try:\n        s = _normalize_smm_service(s)' not in src:
        if old_qty2 in src:
            src = src.replace(old_qty2, new_qty_head, 1)
            print("[fix_cost_rate] smm_qty_kb hardened (get)")
        elif old_qty3 in src:
            src = src.replace(old_qty3, new_qty_head, 1)
            print("[fix_cost_rate] smm_qty_kb hardened (bracket)")
        else:
            import re
            m = re.search(r'def smm_qty_kb\(slug, s, uid=None\):\n', src)
            if m:
                pos = m.end()
                insert = '    try:\n        s = _normalize_smm_service(s)\n    except Exception:\n        pass\n'
                src = src[:pos] + insert + src[pos:]
                print("[fix_cost_rate] smm_qty_kb insert normalize")
            else:
                print("[fix_cost_rate] WARN smm_qty_kb not found")

    if MARKER not in src:
        needle = "smm_services = _load(SMM_SVC_FILE,   {})"
        if needle in src:
            src = src.replace(needle, needle + "\n" + BOOTSTRAP, 1)
            print("[fix_cost_rate] bootstrap normalize injected")
        else:
            alt = "smm_services = _load(SMM_SVC_FILE"
            idx = src.find(alt)
            if idx >= 0:
                end = src.find("\n", idx)
                src = src[:end+1] + BOOTSTRAP + src[end+1:]
                print("[fix_cost_rate] bootstrap normalize injected (alt)")
            else:
                print("[fix_cost_rate] WARN could not find smm_services load")

    old_cb = '''    slug = call.data[7:]
    bot.answer_callback_query(call.id)
    s = smm_services.get(slug)
    if not s: return
    sr   = _smm_sell_rate(s.get("cost_rate", 0), slug)
'''
    old_cb2 = '''    slug = call.data[7:]
    bot.answer_callback_query(call.id)
    s = smm_services.get(slug)
    if not s: return
    sr   = _smm_sell_rate(s["cost_rate"], slug)
'''
    new_cb = '''    slug = call.data[7:]
    bot.answer_callback_query(call.id)
    s = smm_services.get(slug)
    if not s: return
    try:
        s = _normalize_smm_service(s)
    except Exception:
        pass
    sr   = _smm_sell_rate(s.get("cost_rate", 0), slug)
'''
    for o in [old_cb, old_cb2]:
        if o in src:
            src = src.replace(o, new_cb, 1)
            print("[fix_cost_rate] cb_smmsvc normalize")
            break
    else:
        old_cb3 = '''    slug = _cb_resolve(call.data, "smmsvc", _CB_SVC_MAP)
    bot.answer_callback_query(call.id)
    s = smm_services.get(slug)
    if not s: return
'''
        new_cb3 = '''    slug = _cb_resolve(call.data, "smmsvc", _CB_SVC_MAP)
    bot.answer_callback_query(call.id)
    s = smm_services.get(slug)
    if not s: return
    try:
        s = _normalize_smm_service(s)
    except Exception:
        pass
'''
        if old_cb3 in src:
            # only if not already normalized nearby
            pos = src.find('def cb_smmsvc')
            chunk = src[pos:pos+800] if pos >= 0 else ''
            if '_normalize_smm_service(s)' not in chunk:
                src = src.replace(old_cb3, new_cb3, 1)
                print("[fix_cost_rate] cb_smmsvc normalize (resolve)")
            else:
                print("[fix_cost_rate] cb_smmsvc already normalized")
        else:
            print("[fix_cost_rate] cb_smmsvc pattern miss")

    BOT.write_text(src, encoding="utf-8")
    print("[fix_cost_rate] applied")


if __name__ == "__main__":
    main()
