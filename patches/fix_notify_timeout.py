#!/usr/bin/env python3
"""Harder Telegram notify: longer timeout + retries on read timeout."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "kaijaklike_bot.py"
MARKER = "# === NOTIFY TIMEOUT FIX ==="

def main():
    src = BOT.read_text(encoding="utf-8")

    if "_apihelper.READ_TIMEOUT   = 30" in src:
        src = src.replace("_apihelper.READ_TIMEOUT   = 30", "_apihelper.READ_TIMEOUT   = 60")
        print("[fix_notify] READ_TIMEOUT 30→60")
    elif "_apihelper.READ_TIMEOUT = 30" in src:
        src = src.replace("_apihelper.READ_TIMEOUT = 30", "_apihelper.READ_TIMEOUT = 60")
        print("[fix_notify] READ_TIMEOUT 30→60")

    if "_apihelper.CONNECT_TIMEOUT = 20" in src:
        src = src.replace("_apihelper.CONNECT_TIMEOUT = 20", "_apihelper.CONNECT_TIMEOUT = 30")
        print("[fix_notify] CONNECT_TIMEOUT 20→30")

    if MARKER in src:
        print("[fix_notify] already applied")
        BOT.write_text(src, encoding="utf-8")
        return

    old = '''def _try_send(tb, chat_id, text, markup, parse_mode, label):
    """-> (ok, error_text)"""
    try:
        tb.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=markup, disable_web_page_preview=True)
        logger.info(f"[{label}] sent -> {chat_id}")
        return True, ""
    except Exception as e:
        err = str(e)[:300]
        logger.warning(f"[{label}] send failed chat={chat_id} err={err}")
        return False, err
'''

    new = '''def _try_send(tb, chat_id, text, markup, parse_mode, label):
    """-> (ok, error_text)  — retry on Telegram network timeouts."""
    # === NOTIFY TIMEOUT FIX ===
    import time as _t
    last_err = ""
    for attempt in range(1, 4):
        try:
            tb.send_message(
                chat_id, text,
                parse_mode=parse_mode,
                reply_markup=markup,
                disable_web_page_preview=True,
                timeout=60,
            )
            logger.info(f"[{label}] sent -> {chat_id} (try {attempt})")
            return True, ""
        except TypeError:
            try:
                tb.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=markup, disable_web_page_preview=True)
                logger.info(f"[{label}] sent -> {chat_id} (try {attempt})")
                return True, ""
            except Exception as e:
                last_err = str(e)[:300]
        except Exception as e:
            last_err = str(e)[:300]
        is_timeout = any(x in last_err.lower() for x in ("timed out", "timeout", "temporarily unavailable", "connection"))
        logger.warning(f"[{label}] send failed chat={chat_id} try={attempt}/3 err={last_err}")
        if not is_timeout or attempt >= 3:
            break
        _t.sleep(1.5 * attempt)
    return False, last_err
'''

    if old not in src:
        print("[fix_notify] WARN _try_send block not found")
    else:
        src = src.replace(old, new, 1)
        print("[fix_notify] _try_send retry applied")

    src = src.replace(
        '(ពិនិត្យថា Admin បាន /start %s Bot ហើយ Chat ID ត្រឹមត្រូវ)" % (kind.title(), err, kind.title()))',
        '(បើ timeout: network Render↔Telegram — សាកម្តងទៀត។ បើ chat not found: Admin ត្រូវ /start %s Bot + Chat ID ត្រឹមត្រូវ)" % (kind.title(), err, kind.title()))',
    )

    BOT.write_text(src, encoding="utf-8")
    print("[fix_notify] applied")


if __name__ == "__main__":
    main()
