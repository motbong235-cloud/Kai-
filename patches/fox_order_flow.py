#!/usr/bin/env python3
"""Fox order flow: player_id → deduct balance → TopUpFox API order."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "kaijaklike_bot.py"
MARKER = "# === FOX ORDER FLOW ==="

INJECT_HANDLER = r'''
# === FOX ORDER FLOW ===
def _is_fox_service(s) -> bool:
    try:
        return bool(s and (s.get("fox") or s.get("provider_id") == "fox" or s.get("fox_game_code")))
    except Exception:
        return False

def _fox_place_user_order(uid, slug, s, player_id, server_id="", price=None, qty=1):
    """Deduct, call Fox API, save order. Returns (ok, msg_html, order_rec_or_none)."""
    import time as _time
    try:
        s = _normalize_smm_service(s)
    except Exception:
        pass
    if price is None:
        price = float(s.get("flat_price") or s.get("price") or 0)
    if bal(uid) < price:
        return False, (
            f"❌ Balance មិនគ្រប់!\n💳 ${bal(uid):.2f} | Need: ${price:.2f}"
        ), None
    try:
        import fox_integration as _fox
    except Exception as e:
        return False, f"❌ Fox module: <code>{e}</code>", None
    cfg = None
    try:
        cfg = fox_cfg if isinstance(fox_cfg, dict) else _fox.load_fox_cfg(DATA_DIR, _load)
    except Exception:
        try:
            cfg = _fox.load_fox_cfg(DATA_DIR, _load)
        except Exception as e:
            return False, f"❌ Fox config: <code>{e}</code>", None
    if not _fox.fox_ready(cfg):
        return False, "❌ TopUpFox មិនទាន់ Setup (Admin)", None
    gcode = s.get("fox_game_code") or ""
    icode = s.get("fox_item_code") or ""
    if not gcode or not icode:
        return False, "❌ Service ខ្វះ fox_game_code / fox_item_code", None
    ded_bal(uid, price)
    uid_str = str(uid)
    oid = _make_order_id()
    ref = f"KAI_{oid}"
    try:
        res = _fox.place_fox_order(
            cfg,
            game_code=str(gcode),
            item_code=str(icode),
            player_id=str(player_id).strip(),
            server_id=str(server_id or "").strip(),
            reference=ref,
        )
    except Exception as e:
        add_bal(uid, price)
        return False, (
            f"❌ <b>Fox Order បរាជ័យ — សងលុយវិញ</b>\n"
            f"<code>{e}</code>\n"
            f"💳 Balance: <b>${bal(uid):.2f}</b>"
        ), None
    fox_oid = ""
    status = "pending"
    if isinstance(res, dict):
        fox_oid = str(res.get("id") or res.get("order_id") or res.get("order") or "")
        status = str(res.get("status") or "pending").lower()
    order_rec = {
        "uid": uid_str,
        "slug": slug,
        "label": s.get("label", slug),
        "qty": qty,
        "price": price,
        "link": str(player_id).strip(),
        "player_id": str(player_id).strip(),
        "server_id": str(server_id or "").strip(),
        "api_order_id": fox_oid,
        "status": status if status in ("pending", "processing", "success", "completed") else "pending",
        "ts": int(_time.time()),
        "provider_id": "fox",
        "fox": True,
        "fox_game_code": gcode,
        "fox_item_code": icode,
        "fox_raw": res if isinstance(res, dict) else {"raw": str(res)},
    }
    smm_orders[oid] = order_rec
    _save(SMM_ORD_FILE, smm_orders)
    ok_msg = (
        f"✅ <b>Order ជោគជ័យ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {s.get('label', slug)}\n"
        f"🎮 Player ID: <code>{player_id}</code>\n"
        f"💰 ${price:.4f}\n"
        f"🆔 Order: <code>{oid}</code>\n"
        f"🦊 Fox: <code>{fox_oid or '—'}</code>\n"
        f"📊 Status: <b>{order_rec['status']}</b>\n"
        f"💳 Balance: <b>${bal(uid):.2f}</b>"
    )
    try:
        onotify(
            f"🦊 <b>Fox Order</b>\n"
            f"👤 {_user_display(uid_str)}\n"
            f"📦 {s.get('label', slug)}\n"
            f"🎮 <code>{player_id}</code>\n"
            f"💰 ${price:.4f}\n"
            f"🆔 <code>{oid}</code> | Fox <code>{fox_oid or '—'}</code>"
        )
    except Exception:
        pass
    try:
        _notify(_channel_order_msg(
            uid_str,
            label=s.get("label", slug),
            price=price,
            link=str(player_id),
            oid=oid,
            api_order_id=fox_oid,
            qty=qty,
            status_label=f"Fox {order_rec['status']} ⏳",
        ))
    except Exception:
        pass
    return True, ok_msg, order_rec
'''

def main():
    src = BOT.read_text(encoding="utf-8")

    if MARKER not in src:
        needle = '@bot.callback_query_handler(func=lambda c: c.data.startswith("smmqty:"))'
        if needle not in src:
            raise SystemExit("smmqty handler not found")
        src = src.replace(needle, INJECT_HANDLER + "\n\n" + needle, 1)
        print("[fox_order] helpers injected")

    old = '''    s     = smm_services.get(slug)
    if not s: return
    base_price = _smm_price_for_order(slug, qty)
'''
    new = '''    s     = smm_services.get(slug)
    if not s: return
    try:
        s = _normalize_smm_service(s)
    except Exception:
        pass
    # ── Fox TopUp: ask Player ID instead of link ──
    if _is_fox_service(s):
        base_price = _smm_price_for_order(slug, qty)
        price, disc_amt, pct = _apply_user_discount(uid, slug, base_price)
        waiting[uid] = {
            "step": "fox_player_id",
            "slug": slug,
            "qty": qty,
            "price": price,
            "base_price": base_price,
            "discount_pct": pct,
            "discount_amt": disc_amt,
        }
        prompt = (
            f"🦊 <b>TopUpFox Order</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 {s.get('label', slug)}\n"
            f"💰 តម្លៃ: <b>${price:.4f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎮 ផ្ញើ <b>Player ID</b> (UID ក្នុងហ្គេម)\n"
            f"ឧ: <code>1234567890</code>\n"
            f"/cancel ដើម្បីបោះបង់"
        )
        try:
            bot.edit_message_text(
                prompt,
                chat_id=uid, message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data="back:main", color="inactive")]]),
            )
        except Exception:
            bot.send_message(uid, prompt, parse_mode="HTML", reply_markup=cancel_kb())
        return
    base_price = _smm_price_for_order(slug, qty)
'''
    if 'step": "fox_player_id"' not in src and "step': 'fox_player_id'" not in src:
        if old not in src:
            raise SystemExit("cb_smmqty insert point not found")
        src = src.replace(old, new, 1)
        print("[fox_order] cb_smmqty fox branch")
    else:
        print("[fox_order] cb_smmqty branch already present")

    fox_step = r'''
    # ── Fox TopUp: receive Player ID ──
    if isinstance(step, dict) and step.get("step") == "fox_player_id":
        slug = step.get("slug")
        qty = int(step.get("qty") or 1)
        price = float(step.get("price") or 0)
        s = smm_services.get(slug) or {}
        player_id = (text or "").strip()
        if player_id in ("/cancel", "✕ Cancel", "Cancel"):
            waiting.pop(uid, None)
            bot.send_message(uid, "❌ Cancelled", reply_markup=main_kb(uid))
            return
        if not player_id or len(player_id) < 3:
            bot.send_message(uid, "⚠️ Player ID ខ្លីពេក — ផ្ញើម្តងទៀត:", reply_markup=cancel_kb())
            return
        server_id = ""
        if "|" in player_id:
            player_id, server_id = [x.strip() for x in player_id.split("|", 1)]
        waiting.pop(uid, None)
        ok, msg, _rec = _fox_place_user_order(uid, slug, s, player_id, server_id=server_id, price=price, qty=qty)
        bot.send_message(uid, msg, parse_mode="HTML", reply_markup=main_kb(uid))
        return

'''
    if 'step") == "fox_player_id"' not in src:
        needle = 'if isinstance(step, dict) and step.get("step") == "smm_link":'
        if needle not in src:
            raise SystemExit("smm_link step not found")
        src = src.replace(needle, fox_step + "\n    " + needle, 1)
        print("[fox_order] fox_player_id step handler")
    else:
        print("[fox_order] player_id step already present")

    BOT.write_text(src, encoding="utf-8")
    print("[fox_order] applied")


if __name__ == "__main__":
    main()
