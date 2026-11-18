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
    kb.add(InlineKeyboardButton("➕ Add game (all packages)", callback_data="fox:addid", color="active"))
    kb.add(InlineKeyboardButton("🗑 Remove Fox services", callback_data="fox:clear", color="danger"))
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
    if act == "addid":
        if not _fox.fox_ready(fox_cfg):
            bot.send_message(uid, "❌ មិនទាន់ Setup"); return
        waiting[uid] = "fox_add_item_code"
        bot.send_message(
            uid,
            "➕ <b>Add game — កញ្ចប់ទាំងអស់</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "ផ្ញើ <b>game code</b> ឬ <b>item code</b>\n"
            "ឧ: <code>freefire</code> · <code>mlbb</code>\n"
            "ឬ <code>freefire_like</code> (នឹងយក game ទាំងមូល)\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Bot ស្វែង Fox រួចបន្ថែម <b>កញ្ចប់ទាំងអស់</b> នៃ game នោះ។\n"
            "/cancel ដើម្បីបោះបង់",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )
        return
    if act == "clear":
        removed = 0
        for slug in list(smm_services.keys()):
            s = smm_services.get(slug) or {}
            cat = str(s.get("category") or "")
            if s.get("fox") or s.get("provider_id") == "fox" or "Fox" in cat or "fox" in cat.lower():
                smm_services.pop(slug, None)
                removed += 1
        if removed:
            _save(SMM_SVC_FILE, smm_services)
        bot.send_message(
            uid,
            f"🗑 <b>Removed Fox services</b>\n"
            f"លុប: <b>{removed}</b>\n"
            f"Services នៅសល់: <b>{len(smm_services)}</b>",
            parse_mode="HTML",
            reply_markup=admin_kb(),
        )
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

@bot.message_handler(func=lambda m: waiting.get(m.from_user.id) in ("fox_uid", "fox_key", "fox_secret", "fox_markup", "fox_add_item_code") and m.from_user.id == ADMIN_ID)
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
    if st == "fox_add_item_code":
        code = txt.strip().lower().replace(" ", "_")
        if not code or len(code) < 2:
            bot.send_message(uid, "⚠️ ផ្ញើ game/item code ឧ. <code>freefire</code>", parse_mode="HTML"); return
        bot.send_message(uid, f"🔍 កំពុងស្វែង <code>{code}</code> — នឹងបន្ថែមកញ្ចប់ទាំងអស់…", parse_mode="HTML")
        try:
            markup = float(fox_cfg.get("markup_pct") or 15)
            games = _fox.fox_list_games(fox_cfg)
            target_game = None
            target_gcode = None
            for g in games:
                gcode = str(g.get("code") or g.get("game_code") or "").strip()
                if gcode.lower() == code:
                    try:
                        target_game = _fox.fox_game_detail(fox_cfg, gcode)
                    except Exception:
                        target_game = g
                    target_gcode = gcode
                    break
            if target_game is None:
                for g in games:
                    gcode = str(g.get("code") or g.get("game_code") or "").strip()
                    gname = str(g.get("name") or g.get("title") or "").lower()
                    if code in gcode.lower() or code in gname or gcode.lower() in code:
                        try:
                            target_game = _fox.fox_game_detail(fox_cfg, gcode)
                        except Exception:
                            target_game = g
                        target_gcode = gcode
                        break
            if target_game is None:
                for g in games:
                    gcode = str(g.get("code") or g.get("game_code") or "").strip()
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
                        icode = str(it.get("code") or it.get("item_code") or "").strip().lower()
                        if icode == code or icode.endswith("_" + code) or code in icode:
                            target_game = detail
                            target_gcode = gcode
                            break
                    if target_game is not None:
                        break
            if target_game is None:
                waiting.pop(uid, None)
                bot.send_message(
                    uid,
                    f"❌ រកមិនឃើញ game/item <code>{code}</code>\n"
                    f"សាក List Games ឬ code ពី Fox panel។",
                    parse_mode="HTML",
                    reply_markup=admin_kb(),
                )
                return
            items = target_game.get("items") or target_game.get("packages") or []
            if not items and isinstance(target_game.get("packages"), dict):
                items = list(target_game["packages"].values())
            if not items:
                waiting.pop(uid, None)
                bot.send_message(uid, f"⚠️ Game <code>{target_gcode}</code> គ្មាន packages", parse_mode="HTML", reply_markup=admin_kb())
                return
            added = updated = 0
            lines = []
            for it in items:
                icode = str(it.get("code") or it.get("item_code") or "").strip()
                if not icode:
                    continue
                slug = _fox.slug_for_item(target_gcode, icode)
                entry = _fox.service_from_item(target_game, it, markup)
                if slug in smm_services:
                    old = smm_services[slug]
                    entry["open"] = old.get("open", True)
                    smm_services[slug] = entry
                    updated += 1
                else:
                    smm_services[slug] = entry
                    added += 1
                lines.append(f"• {entry.get('label')} — ${float(entry.get('price') or 0):.4f}")
            _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            gname = target_game.get("name") or target_game.get("title") or target_gcode
            preview = "\n".join(lines[:15])
            more = f"\n… +{len(lines)-15} more" if len(lines) > 15 else ""
            bot.send_message(
                uid,
                f"✅ <b>បន្ថែមកញ្ចប់ទាំងអស់</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎮 Game: <b>{gname}</b> (<code>{target_gcode}</code>)\n"
                f"📦 Packages: <b>{len(lines)}</b>\n"
                f"➕ ថ្មី: <b>{added}</b> · 🔄 កែ: <b>{updated}</b>\n"
                f"📈 Markup: {markup:.1f}%\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{preview}{more}",
                parse_mode="HTML",
                reply_markup=admin_kb(),
            )
        except Exception as e:
            waiting.pop(uid, None)
            bot.send_message(uid, f"❌ Add game failed:\n<code>{e}</code>", parse_mode="HTML", reply_markup=admin_kb())
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
