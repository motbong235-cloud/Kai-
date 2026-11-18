#!/usr/bin/env python3
"""After inject_fox_master: markup % must reprice existing Fox services immediately."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "kaijaklike_bot.py"

OLD = '''    if st == "fox_markup":
        try:
            v = float(txt.replace("%", "").strip())
            if v < 0 or v > 500:
                raise ValueError("range")
        except Exception:
            bot.send_message(uid, "⚠️ ផ្ញើលេខ 0–500:"); return
        fox_cfg["markup_pct"] = v
        _fox_save()
        waiting.pop(uid, None)
        bot.send_message(uid, f"✅ Markup = <b>{v:.1f}%</b>\\nSync ម្តងទៀតដើម្បីអាប់ដេតតម្លៃ។", parse_mode="HTML", reply_markup=admin_kb())
        return
'''

OLD2 = '''    if st == "fox_markup":
        try:
            v = float(txt.replace("%", "").strip())
            if v < 0 or v > 500:
                raise ValueError("range")
        except Exception:
            bot.send_message(uid, "⚠️ ផ្ញើលេខ 0–500:"); return
        fox_cfg["markup_pct"] = v
        _fox_save()
        waiting.pop(uid, None)
        bot.send_message(uid, f"✅ Markup = <b>{v:.1f}%</b>\nSync ម្តងទៀតដើម្បីអាប់ដេតតម្លៃ។", parse_mode="HTML", reply_markup=admin_kb())
        return
'''

NEW = '''    if st == "fox_markup":
        try:
            v = float(txt.replace("%", "").strip())
            if v < 0 or v > 500:
                raise ValueError("range")
        except Exception:
            bot.send_message(uid, "⚠️ ផ្ញើលេខ 0–500:"); return
        fox_cfg["markup_pct"] = v
        _fox_save()
        updated = 0
        for slug, s in list(smm_services.items()):
            if not (s.get("fox") or s.get("provider_id") == "fox" or str(slug).startswith("fox_")):
                continue
            cost = s.get("fox_cost")
            if cost is None:
                cost = s.get("price") or s.get("flat_price") or 0
            try:
                cost = float(cost)
            except Exception:
                cost = 0.0
            new_price = _fox.sell_price(cost, v)
            s["fox_cost"] = cost
            s["price"] = new_price
            s["flat_price"] = new_price
            s["rate"] = new_price
            s["cost_rate"] = 0
            s["fox"] = True
            s["provider_id"] = "fox"
            smm_services[slug] = s
            updated += 1
        if updated:
            _save(SMM_SVC_FILE, smm_services)
        waiting.pop(uid, None)
        bot.send_message(
            uid,
            f"✅ Markup = <b>{v:.1f}%</b>\\n"
            f"💰 អាប់ដេតតម្លៃ Fox: <b>{updated}</b> packages\\n"
            f"(fox_cost + {v:.1f}%)",
            parse_mode="HTML",
            reply_markup=admin_kb(),
        )
        return
'''

def main():
    src = BOT.read_text(encoding="utf-8")
    if "អាប់ដេតតម្លៃ Fox" in src and "sell_price(cost, v)" in src:
        print("[fix_fox_markup] already present")
        return
    if OLD in src:
        src = src.replace(OLD, NEW, 1)
        print("[fix_fox_markup] replaced (escaped n)")
    elif OLD2 in src:
        src = src.replace(OLD2, NEW, 1)
        print("[fix_fox_markup] replaced (real n)")
    else:
        print("[fix_fox_markup] WARN: fox_markup block not found")
        return
    BOT.write_text(src, encoding="utf-8")
    print("[fix_fox_markup] applied")

if __name__ == "__main__":
    main()
