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

INJECT = r'''
# === FOX RESELLER MASTER INJECT ===
# TopUpFox Reseller — https://reseller.topupfoxbot.com — MASTER only
# Placed BEFORE catch-all handle_msg so button is not swallowed.
try:
    import fox_integration as _fox
except Exception as _fox_imp_err:
    _fox = None
    logging.getLogger(__name__).warning("[fox] import failed: %s", _fox_imp_err)

FOX_CFG_FILE = _dpath("fox_reseller.json")
fox_cfg = {}
if _fox and IS_MASTER:
    try:
        fox_cfg = _fox.load_fox_cfg(DATA_DIR, _load)
    except Exception as _e:
        logging.getLogger(__name__).warning("[fox] load cfg: %s", _e)
        fox_cfg = dict(getattr(_fox, "FOX_CFG_DEFAULT", {}))

def _fox_save():
    if _fox and IS_MASTER:
        _fox.save_fox_cfg(DATA_DIR, fox_cfg, _save)

def _fox_admin_only(uid):
    return IS_MASTER and uid == ADMIN_ID and _fox is not None

_orig_admin_smm_kb = admin_smm_kb
def admin_smm_kb():
    kb = _orig_admin_smm_kb()
    if IS_MASTER:
        try:
            kb.row(KeyboardButton("🦊 TopUpFox", color="active"))
        except Exception:
            pass
    return kb

def _is_fox_menu_btn(m):
    try:
        if not m or getattr(m, "from_user", None) is None:
            return False
        if m.from_user.id != ADMIN_ID:
            return False
        t = (_restore_btn_text(m) or "") + " " + (m.text or "")
        tl = t.lower()
        return ("topupfox" in tl) or ("topup fox" in tl) or ("🦊" in t and "fox" in tl)
    except Exception:
        return False

@bot.message_handler(commands=["fox", "topupfox"])
@bot.message_handler(func=_is_fox_menu_btn)
def fox_admin_menu(message):
    uid = message.from_user.id
    if not IS_MASTER:
        bot.send_message(uid, "🚫 TopUpFox មានតែក្នុង <b>Bot Master</b> ប៉ុណ្ណោះ។", parse_mode="HTML")
        return
    if _fox is None:
        bot.send_message(uid, "❌ <b>fox_integration</b> មិន load បាន។\nពិនិត្យ <code>fox_integration.py</code> + <code>reseller_client.py</code> + package <code>cryptography</code>។", parse_mode="HTML")
        return
    if uid != ADMIN_ID:
        return
    ready = _fox.fox_ready(fox_cfg)
    bal_s = "—"
    if ready:
        try:
            bal_s = f"${_fox.fox_balance(fox_cfg):.4f}"
        except Exception as e:
            bal_s = f"err: {e}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔑 Setup UID / Key / Secret", callback_data="fox:setup", color="progress"))
    kb.add(InlineKeyboardButton("💰 Balance", callback_data="fox:bal", color="active"))
    kb.add(InlineKeyboardButton("🎮 Sync Games → Services", callback_data="fox:sync", color="active"))
    kb.add(InlineKeyboardButton("📋 List Games", callback_data="fox:games", color="progress"))
    kb.add(InlineKeyboardButton("📈 Markup %", callback_data="fox:markup", color="progress"))
    bot.send_message(
        uid,
        f"🦊 <b>TopUpFox Reseller</b> <i>(Master only)</i>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"API: <code>api.topupfoxbot.com/v1</code>\n"
        f"Docs: reseller.topupfoxbot.com/api-docs\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{'✅' if ready else '❌'} Config: <b>{'ready' if ready else 'not set'}</b>\n"
        f"🆔 UID: <code>{fox_cfg.get('uid') or '—'}</code>\n"
        f"🔑 Key: <code>{(fox_cfg.get('api_key') or '—')[:8]}…</code>\n"
        f"💰 Balance: <b>{bal_s}</b>\n"
        f"📈 Markup: <b>{float(fox_cfg.get('markup_pct') or 15):.1f}%</b>\n",
        parse_mode="HTML",
        reply_markup=kb,
        disable_web_page_preview=True,
    )

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("fox:") and c.from_user.id == ADMIN_ID)
def fox_admin_cb(call):
    uid = call.from_user.id
    if not _fox_admin_only(uid):
        bot.answer_callback_query(call.id, "Master only"); return
    act = call.data.split(":", 1)[-1]
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    if act == "setup":
        waiting[uid] = "fox_uid"
        bot.send_message(uid, "🔑 ផ្ញើ <b>FOX UID</b> (លេខពី panel):\nឬ /cancel", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if act == "bal":
        if not _fox.fox_ready(fox_cfg):
            bot.send_message(uid, "❌ មិនទាន់ Setup"); return
        try:
            b = _fox.fox_balance(fox_cfg)
            bot.send_message(uid, f"💰 TopUpFox Balance: <b>${b:.4f}</b>", parse_mode="HTML")
        except Exception as e:
            bot.send_message(uid, f"❌ Balance error:\n<code>{e}</code>", parse_mode="HTML")
        return
    if act == "markup":
        waiting[uid] = "fox_markup"
        bot.send_message(uid, f"📈 Markup បច្ចុប្បន្ន <b>{float(fox_cfg.get('markup_pct') or 15):.1f}%</b>\nផ្ញើលេខថ្មី (ឧ. 15):", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if act == "games":
        if not _fox.fox_ready(fox_cfg):
            bot.send_message(uid, "❌ មិនទាន់ Setup"); return
        try:
            games = _fox.fox_list_games(fox_cfg)
            lines = [f"🎮 <b>Fox Games ({len(games)})</b>\n━━━━━━━━━━━━━━━━━━"]
            for g in games[:40]:
                code = g.get("code") or g.get("game_code") or "?"
                name = g.get("name") or g.get("title") or code
                lines.append(f"• <code>{code}</code> — {name}")
            if len(games) > 40:
                lines.append(f"… +{len(games)-40} more")
            bot.send_message(uid, "\n".join(lines), parse_mode="HTML")
        except Exception as e:
            bot.send_message(uid, f"❌ List games:\n<code>{e}</code>", parse_mode="HTML")
        return
    if act == "sync":
        if not _fox.fox_ready(fox_cfg):
            bot.send_message(uid, "❌ មិនទាន់ Setup"); return
        bot.send_message(uid, "⏳ កំពុង Sync games ពី TopUpFox…")
        try:
            games = _fox.fox_list_games(fox_cfg)
            markup = float(fox_cfg.get("markup_pct") or 15)
            added = updated = 0
            for g in games:
                gcode = str(g.get("code") or g.get("game_code") or "")
                if not gcode:
                    continue
                try:
                    detail = _fox.fox_game_detail(fox_cfg, gcode)
                except Exception:
                    detail = g
                items = detail.get("items") or detail.get("packages") or []
                if not items and isinstance(detail.get("packages"), dict):
                    items = list(detail["packages"].values())
                for it in items:
                    icode = str(it.get("code") or it.get("item_code") or "")
                    if not icode:
                        continue
                    slug = _fox.slug_for_item(gcode, icode)
                    entry = _fox.service_from_item(detail if detail else g, it, markup)
                    if slug in smm_services:
                        old = smm_services[slug]
                        entry["open"] = old.get("open", True)
                        smm_services[slug] = entry
                        updated += 1
                    else:
                        smm_services[slug] = entry
                        added += 1
            _save(SMM_SVC_FILE, smm_services)
            bot.send_message(
                uid,
                f"✅ <b>Fox Sync រួច</b>\n"
                f"➕ បន្ថែម: <b>{added}</b>\n"
                f"🔄 កែ: <b>{updated}</b>\n"
                f"📦 Services សរុប: <b>{len(smm_services)}</b>\n"
                f"📈 Markup: {markup:.1f}%",
                parse_mode="HTML",
            )
        except Exception as e:
            bot.send_message(uid, f"❌ Sync failed:\n<code>{e}</code>", parse_mode="HTML")
        return

@bot.message_handler(func=lambda m: waiting.get(m.from_user.id) in ("fox_uid", "fox_key", "fox_secret", "fox_markup") and m.from_user.id == ADMIN_ID)
def fox_setup_steps(message):
    uid = message.from_user.id
    if not _fox_admin_only(uid):
        return
    st = waiting.get(uid)
    txt = (message.text or "").strip()
    if txt in ("/cancel", "✕ Cancel", "Cancel"):
        waiting.pop(uid, None)
        bot.send_message(uid, "❌ Cancelled", reply_markup=admin_kb())
        return
    if st == "fox_uid":
        if not txt.isdigit():
            bot.send_message(uid, "⚠️ UID ត្រូវជាលេខ — ផ្ញើម្តងទៀត:"); return
        fox_cfg["uid"] = txt
        _fox_save()
        waiting[uid] = "fox_key"
        bot.send_message(uid, "✅ UID រក្សាទុក។\nឥឡូវផ្ញើ <b>API Key</b>:", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if st == "fox_key":
        if len(txt) < 8:
            bot.send_message(uid, "⚠️ Key ខ្លីពេក:"); return
        fox_cfg["api_key"] = txt
        _fox_save()
        waiting[uid] = "fox_secret"
        bot.send_message(uid, "✅ API Key រក្សាទុក។\nឥឡូវផ្ញើ <b>API Secret</b>:", parse_mode="HTML", reply_markup=cancel_kb())
        return
    if st == "fox_secret":
        if len(txt) < 8:
            bot.send_message(uid, "⚠️ Secret ខ្លីពេក:"); return
        fox_cfg["api_secret"] = txt
        _fox_save()
        waiting.pop(uid, None)
        ok = False
        err = ""
        try:
            b = _fox.fox_balance(fox_cfg)
            ok = True
        except Exception as e:
            err = str(e)
        if ok:
            bot.send_message(uid, f"✅ <b>TopUpFox Setup រួច!</b>\n💰 Balance: <b>${b:.4f}</b>", parse_mode="HTML", reply_markup=admin_kb())
        else:
            bot.send_message(uid, f"⚠️ រក្សាទុកហើយ ប៉ុន្តែ test balance បរាជ័យ:\n<code>{err}</code>", parse_mode="HTML", reply_markup=admin_kb())
        return
    if st == "fox_markup":
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


def main():
    src = BOT.read_text(encoding="utf-8")
    if MARKER in src:
        start = src.find(MARKER)
        cut = None
        for em in [
            "@bot.message_handler(func=lambda m: True)",
            'if __name__ == "__main__":',
        ]:
            i = src.find(em, start + len(MARKER))
            if i != -1:
                cut = i
                break
        if cut is not None:
            src = src[:start] + src[cut:]
            print("[inject_fox] removed old inject block")

    needle = "@bot.message_handler(func=lambda m: True)\ndef handle_msg(message):"
    if needle in src:
        src = src.replace(needle, INJECT + "\n\n" + needle, 1)
    elif "@bot.message_handler(func=lambda m: True)" in src:
        src = src.replace(
            "@bot.message_handler(func=lambda m: True)",
            INJECT + "\n\n@bot.message_handler(func=lambda m: True)",
            1,
        )
    else:
        raise SystemExit("cannot find catch-all handle_msg inject point")

    BOT.write_text(src, encoding="utf-8")
    print("[inject_fox] injected OK (before catch-all)")


if __name__ == "__main__":
    main()
