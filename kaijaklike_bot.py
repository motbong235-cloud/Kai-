"""
╔══════════════════════════════════════════════════════════════╗
║     Kaijaklike Bot — カイロゼン SMM  [v11]                ║
║     SMM Panel · ដាក់លុយ CamRapidPay KHQR + ABA PayWay       ║
║     Panel Admin · បន្ថែម/កាត់ Balance                       ║
║     Compatible: Python 3.10+ · Termux / Render / VPS       ║
║     v10: /newbot — បង្កើត Bot ថ្មីដោយផ្ទាល់ខាងក្នុង Telegram  ║
║          /mybots — គ្រប់គ្រង Bot រងទាំងអស់ (start/stop/del)  ║
╚══════════════════════════════════════════════════════════════╝
ដំឡើង:
  pip install pyTelegramBotAPI requests flask qrcode pillow --break-system-packages
"""

import json, logging, time, re, threading, io, os, sys, subprocess, datetime, base64
import zipfile
from decimal import Decimal as _Decimal, ROUND_HALF_UP as _ROUND_HALF_UP
import requests as http_req
from dotenv import load_dotenv
load_dotenv()
import telebot
from telebot import apihelper as _apihelper
# ── Retry លំនាំដើមរបស់ telebot គ្មាន retry លើ connection error ទេ (ខុសពី
# `http` session ខាងក្រោមដែលមាន Retry+backoff រួចហើយ) — នេះជាមូលហេតុចម្បង
# នៃ "Connection aborted / RemoteDisconnected" ពេល Render ខាត់ connection
# ចោលភ្លាមៗពេលកំពុង bot.send_message/send_photo ។ បើក RETRY_ON_ERROR ដើម្បីឲ្យ
# telebot ខ្លួនឯង retry ស្វ័យប្រវត្តិមុននឹង raise exception ចេញទៅ handler ។
_apihelper.RETRY_ON_ERROR = True
_apihelper.CONNECT_TIMEOUT = 15
_apihelper.READ_TIMEOUT   = 20
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton as _KB_orig,
    InlineKeyboardMarkup, InlineKeyboardButton as _IKB_orig,
    MessageEntity as _MessageEntity
)
import re as _re

# ── Colored / Premium-emoji buttons (Telegram Bot API 9.4+) ───────────────
# Injects 'style' + 'icon_custom_emoji_id' into JSON so any pyTelegramBotAPI
# version works, regardless of whether the installed lib already knows them.
#
# ⚠️ សំខាន់ (រកឃើញនិងកែនៅ 2026-08-06): Telegram Bot API 9.4 កំណត់ត្រឹមតែ
#    field ឈ្មោះ "style" ប៉ុណ្ណោះ (មិនមែន "color" ទេ) ហើយតម្លៃត្រូវជា
#    "danger" (ក្រហម) | "primary" (ខៀវ) | "success" (បៃតង) ប៉ុណ្ណោះ។
#    កូដចាស់ប្រើ field ឈ្មោះ "color" ខុស + តម្លៃប្រឌិតឡើងផ្ទាល់ខ្លួន
#    ("active"/"inactive"/"progress") ដែល Telegram មិនស្គាល់ទាល់តែសោះ —
#    មានន័យថា ពណ៌ button មិនដែលដំណើរការជាក់ស្តែងទេ តាំងពីដើមមក។
#    _COLOR_MAP ខាងក្រោមបកប្រែឈ្មោះ semantic ចាស់ (ប្រើពាសពេញកូដរាប់រយកន្លែង)
#    ទៅជាតម្លៃ enum ត្រឹមត្រូវ ដោយមិនចាំបាច់កែ call site ណាមួយឡើយ។
_COLOR_MAP = {
    "active":   "success",   # បៃតង — action ធម្មតា/ជ្រើសរើសបាន
    "progress": "primary",   # ខៀវ — highlighted / ជំហានបន្ទាប់ / custom
    "danger":   "danger",    # ក្រហម — លុប/បដិសេធ (បើប្រើផ្ទាល់)
    "inactive": None,        # គ្មាន style ពិសេស — មើលទៅដូច button ធម្មតា
    "default":  None,
}
def _to_style(color):
    if not color:
        return None
    return _COLOR_MAP.get(color, color if color in ("danger", "primary", "success") else None)
# គំនិត: លែងត្រូវចងចាំ "semantic key" ដូចមុនទៀតហើយ (account/topup/...) —
# ឥឡូវ key គឺជា emoji unicode character ពិតដែលប្រើក្នុង bot (👤 💸 🛒 ...).
# តម្លៃ = custom_emoji_id (premium) បើកំណត់រួច, None = មិនទាន់មាន → fallback
# ទៅ unicode emoji ធម្មតា។ EMOJI_MAP គ្របដណ្តប់គ្រប់ jang emoji ដែលប្រើក្នុង
# ⇒ reply-keyboard buttons, inline buttons, និង អត្ថបទសារ (message text) ទាំងអស់។
# របៀបកំណត់: /setemojis (reply ទៅសារណាមួយមាន premium emoji, លំដាប់ណាក៏បាន —
# bot ស្គាល់ automatically តាម emoji ធម្មតាដែលនៅក្រោម premium icon នីមួយៗ)
# ចំណាំ: កុំកសាង list នេះឡើងវិញដោយ iterate លើ string តែមួយបន្ត — flag emoji
# (🇰🇭 ។ល។) និង variation-selector emoji (✏️ ។ល។) មាន 2 code points/តួ ដូច្នេះ
# ត្រូវសរសេរជា element ដាច់ពីគ្នាក្នុង list ដូចខាងក្រោម ដើម្បីកុំឲ្យខូច។
_EMOJI_CHAR_LIST = [
    '🇰🇭', '🇬🇧', '🇺🇸', '❌', '✅', '💰', '→', '👤', '📊', '💳',
    '✏️', '📋', '💸', '⚠️', '🚫', '💡', '📝', '🗑️', '👥', '❤️',
    '👁️', '🔗', '🛒', '🔍', '💬', '🔢', '🎟️', '📂', '📦', '💔',
    '🔄', '🔑', '💵', '🌐', '🙏', '📢', '🤖', '😊', '⚙️', '🔙',
    '💙', '➕', '✍️', '🔔', '🎵', '📱', '🟢', '🔴', '🛑', '✕',
    '👈', '🏠', '🎉', '📌', '💹', '🧪', '🐦', '👋', '👇', '❓',
    '🖼️', '📘', '📸', '⚡', '📭', '📞', '🔖', '👜', '🙍', '🛠️',
    '★', '🎁', '🧵', '👀', '😍', '🛡️', '📏', '📎', '🔓', '⬅️',
    '✨', '➡️', '🔌', '🔵', '🟡', '📤', '🔕', '📁', '🚀', '←',
    '⏱', '🆔', '▶️', '🏦',
    # ⚠️ បន្ថែម 2026-08-17 — Emoji ថ្មីៗពី feature ថ្មីៗ (Daily Report, Preview,
    # Top Services, Backup, Profit Report, Manual Deposit) ដែលមុននេះមិនស្ថិត
    # ក្នុងបញ្ជីនេះទេ ធ្វើឲ្យមិនអាចប្តូរជា Premium Emoji បាន — រកឃើញដោយស្កេន
    # ប៊ូតុងទាំងអស់ក្នុងកូដ ធៀបនឹងបញ្ជីនេះ។
    '⏰', '🎨', '🏆', '💾', '📈', '📷', '🧾',
    # ⚠️ បន្ថែម 2026-08-31 — ស្កេនប៊ូតុងទាំងអស់ម្តងទៀត រកឃើញ emoji ថ្មីៗពី
    # feature ថ្មីៗ (បិទ/បើកវិធីទូទាត់, QR Cooldown, ប្តូរ Step ទូទាត់,
    # Manual QR) ដែលមិនធ្លាប់នៅក្នុងបញ្ជីនេះ — ធ្វើឲ្យ Admin មិនអាចកំណត់
    # ជា Premium Emoji បាន (គ្មានកន្លែង setup ក្នុង /setemojis grid)។
    '🔀', '⏳', '🔁', '🖼',
]
EMOJI_MAP = {ch: None for ch in _EMOJI_CHAR_LIST}
# ធ្វើ regex pattern មួយសម្រាប់ចាប់ emoji នៅដើម string (រួមទាំង variation
# selector ﻿(\uFE0F) និង flag ២-តួ) ដើម្បីប្រើក្នុងការ auto-detect ខាងក្រោម។
_EMOJI_CHARS_SORTED = sorted(EMOJI_MAP.keys(), key=len, reverse=True)
_LEADING_EMOJI_RE = _re.compile(
    "^(" + "|".join(_re.escape(c) for c in _EMOJI_CHARS_SORTED) + ")"
)

def _leading_emoji(s):
    """បើ string ចាប់ផ្ដើមដោយ emoji ណាមួយក្នុង EMOJI_MAP សូមត្រឡប់តួនោះមកវិញ។"""
    if not s or not isinstance(s, str):
        return None
    m = _LEADING_EMOJI_RE.match(s)
    return m.group(1) if m else None

def _strip_leading_emoji_text(text, ch):
    """ដកចេញ emoji ធម្មតា (ch) ពីដើម text បើ icon_custom_emoji_id ត្រូវបានប្រើ
    ជំនួសរួចហើយ — បើមិនដូច្នេះទេ Telegram នឹងបង្ហាញទាំង icon premium (មុន
    button) ព្រមទាំង emoji ធម្មតា (ក្នុង label) ក្នុងពេលតែមួយ ដែលមើលទៅដូចស្ទួន។"""
    if not text or not isinstance(text, str) or not ch:
        return text
    if text.startswith(ch):
        return text[len(ch):].lstrip()
    return text

class InlineKeyboardButton(_IKB_orig):
    def __init__(self, *args, color: str = None, emoji_id: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._color = color
        label = kwargs.get("text") if "text" in kwargs else (args[0] if args else None)
        self._emoji_char = _leading_emoji(label)
        if emoji_id is None and self._emoji_char:
            emoji_id = EMOJI_MAP.get(self._emoji_char)
        self._emoji_id = emoji_id

    def to_dict(self):
        d = super().to_dict()
        style = _to_style(self._color)
        if style:
            d["style"] = style
        if self._emoji_id:
            d["icon_custom_emoji_id"] = str(self._emoji_id)
            if "text" in d:
                d["text"] = _strip_leading_emoji_text(d["text"], self._emoji_char)
        return d

# ⚠️ កំណត់ត្រា (កែនៅ 2026-08-06 លើកទី ២): ការយល់ដឹងមុននេះខុស — Telegram
#    Bot API 9.4 ពិតជា support "icon_custom_emoji_id" + "style" លើ
#    KeyboardButton (reply keyboard) ដែរ ដូចគ្នានឹង InlineKeyboardButton
#    (មើល core.telegram.org/bots/api → KeyboardButton object). មូលហេតុពិត
#    ដែល emoji premium មិនបង្ហាញ គឺ to_dict() ចាស់ **មិនដែលដាក់ field នេះ
#    ចូល JSON ទាល់តែសោះ**។
#    ⚠️ លក្ខខណ្ឌចាំបាច់ពី Telegram: bot owner ត្រូវមាន Telegram Premium
#    សកម្ម (ឬ bot ទិញ additional username លើ Fragment) មិនដូច្នេះទេ
#    Telegram នឹងមិនបង្ហាញ icon នេះឡើយ ទោះកូដត្រឹមត្រូវក៏ដោយ។
#
#    ឥឡូវនេះកូដខាងក្រោមកាត់ emoji unicode ចេញពី text ដូច InlineKeyboardButton
#    ដែរ (ដើម្បីកុំឲ្យស្ទួន icon+emoji) ប៉ុន្ដែ ដើម្បីកុំឲ្យ button ធ្លាក់ចូល
#    fallback ("មិនស្គាល់ button") នៅពេល Telegram ត្រឡប់ text ដែលកាត់រួច
#    មកវិញ, យើងកត់ត្រា mapping "text ដែលកាត់ → text ដើម (មាន emoji)" ក្នុង
#    _STRIPPED_TEXT_MAP ។ MAIN MESSAGE HANDLER ត្រូវ restore text ដើមវិញ
#    មុននឹង match លក្ខខណ្ឌ text == / text in (...) ណាមួយ (មើល "# ── Restore
#    stripped-emoji text ──" ក្នុង handle_msg)។
_STRIPPED_TEXT_MAP = {}

class KeyboardButton(_KB_orig):
    """Reply-keyboard button ដែលអាចដាក់ premium emoji icon បាន (user-side only)."""
    def __init__(self, *args, color: str = None, emoji_id: str = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._color = color
        label = kwargs.get("text") if "text" in kwargs else (args[0] if args else None)
        self._emoji_char = _leading_emoji(label)
        if emoji_id is None and self._emoji_char:
            emoji_id = EMOJI_MAP.get(self._emoji_char)
        self._emoji_id = emoji_id

    def to_dict(self):
        d = super().to_dict()
        style = _to_style(self._color)
        if style:
            d["style"] = style
        if self._emoji_id and "text" in d:
            original_text = d["text"]
            d["icon_custom_emoji_id"] = str(self._emoji_id)
            stripped = _strip_leading_emoji_text(original_text, self._emoji_char)
            if stripped != original_text:
                # កត់ត្រា mapping ដើម្បីឲ្យ handler ចាស់ៗនៅតែដំណើរការធម្មតា
                _STRIPPED_TEXT_MAP[stripped] = original_text
                d["text"] = stripped
        return d

# ─────────────────────────────────────────────────────────────────────────
from flask import Flask, request as flask_request, jsonify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── Auto-install deps ───
def _ensure_deps():
    pkgs = {"PIL": "pillow", "qrcode": "qrcode", "numpy": "numpy"}
    for mod, pkg in pkgs.items():
        try: __import__(mod)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg,
                            "--break-system-packages", "-q"], check=False)
_ensure_deps()

import qrcode
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  ╔═══════════════════════════════════════════════════════╗
#  ║   🛠️  SETUP — បំពេញព័ត៌មាននៅទីនេះ មុនដំណើរការ bot   ║
#  ╚═══════════════════════════════════════════════════════╝
#
#  ដើម្បីដំណើរការ bot ច្រើនច្បាប់ក្នុងពេលតែមួយ៖
#    1) ចម្លងឯកសារនេះទាំងមូល ដាក់ក្នុង folder ថ្មីដាច់ដោយឡែក
#       (ឧ. bot_shop2/kaijaklike_bot.py)
#    2) ប្តូរតម្លៃខាងក្រោម (BOT_TOKEN, ADMIN_ID, CAMRAPID_API_KEY,
#       CONTROL_PORT) ឱ្យខុសគ្នាពី bot ដទៃ
#    3) ដំណើរការដោយ `python3 kaijaklike_bot.py` ដាច់ដោយឡែក
#       ក្នុង terminal/session ផ្សេង (ឬ tmux/screen ផ្សេងគ្នា)
#    ⚠️ សារសំខាន់: CONTROL_PORT ត្រូវតែខុសគ្នារាល់ bot មួយៗ
#       ដែលដំណើរការក្នុងម៉ាស៊ីនតែមួយ បើមិនដូច្នេះ bot ទីពីរនឹង
#       crash ដោយសារ port ប៉ះគ្នា (bot ទីមួយប្រើ 5056 default)
#
#  អាចបំពេញផ្ទាល់ខាងក្រោម ឬកំណត់ជា environment variable
#  (env var នឹងមានអទិភាពជាង តម្លៃ default ខាងក្រោម)
# ═══════════════════════════════════════════════════════════
BOT_TOKEN          = os.getenv("BOT_TOKEN", "")   # 👈 Bot Token ពី @BotFather — កំណត់ជា Environment Variable ប៉ុណ្ណោះ (កុំសរសេរផ្ទាល់ក្នុងកូដ)
ADMIN_ID           = int(os.getenv("ADMIN_ID", "0"))                                    # 👈 Telegram ID អ្នកគ្រប់គ្រង bot នេះ
INSTANCE_NAME      = os.getenv("INSTANCE_NAME", "")          # មិនទទេ = នេះជា bot រងដែលត្រូវបាន /newbot បង្កើត
IS_MASTER          = (INSTANCE_NAME == "")                    # bot ដើម (ដែលអ្នករត់ដោយផ្ទាល់) = master, អាចបង្កើត /newbot
BOT_DISPLAY_NAME   = os.getenv("BOT_DISPLAY_NAME", "")             # ឈ្មោះ bot ដែលបង្ហាញដល់អ្នកប្រើ (ប្តូរបានពី /newbot)
BOT_WELCOME_MSG    = os.getenv("BOT_WELCOME_MSG", "")              # welcome message custom (ទទេ = ប្រើ default)

# ── Anti-Spam — កំណត់ Cooldown រវាង QR generation ម្តងៗក្នុង User តែម្នាក់ (ការពារ Spam
#    ចុច "💸 បញ្ចូលលុយ" ជាប់ៗគ្នា ដែលនាំឲ្យហៅ CamRapidPay/ABA API ច្រើនដងឥតប្រយោជន៍ + Flood )
#    កំណត់តម្លៃដើមពី Environment Variable, ប៉ុន្តែ Admin អាចផ្លាស់ប្តូរផ្ទាល់ក្នុង Bot បាន
#    (👉 ⚙️ Settings → ⏳ QR Cooldown) — តម្លៃថ្មីរក្សាទុកអចិន្ត្រៃយ៍ក្នុង dep_qr_cooldown.json ។
DEP_QR_COOLDOWN_SEC = int(os.getenv("DEP_QR_COOLDOWN_SEC", "15"))
_dep_qr_cooldown    = {}   # uid_str -> unix timestamp នៃ QR generation ចុងក្រោយ

# ── CamRapidPay — Create KHQR + Check transaction ──
CAMRAPID_API_KEY   = os.getenv("CAMRAPID_API_KEY", "")   # 👈 CamRapidPay API Key — កំណត់ជា Environment Variable ប៉ុណ្ណោះ
CAMRAPID_CREATE    = "https://pay.camrapidpay.com/api/v1/khqr/create-payments"
CAMRAPID_CHECK     = "https://pay.camrapidpay.com/check-transaction-api"
WEBHOOK_URL        = os.getenv("WEBHOOK_URL", "")          # ដាក់ URL webhook (optional)

# ── ABA PayWay (តាម KHMER SYSTEM — khmer-system.com) — ជម្រើសទូទាត់ស្វ័យប្រវត្តិទី ២ ──
# (v12: បន្ថែម ABA PayWay ស្របជាមួយ CamRapidPay ដែលមានស្រាប់ — មិនលុប/មិនប៉ះពាល់ CamRapidPay ទេ។
#  បើកំណត់ទាំង CAMRAPID_API_KEY និង ABA_API_KEY ព្រមគ្នា bot នឹងឲ្យ user ជ្រើសរើសវិធីទូទាត់ពេល
#  ចុច "💸 បញ្ចូលលុយ"។ បើកំណត់តែ ABA bot ប្រើ ABA ដោយស្វ័យប្រវត្តិ។)
ABA_API_KEY        = os.getenv("ABA_API_KEY", "")          # 👈 Profile Key របស់ KHMER SYSTEM (khmer-system.com/operator/profile)
ABA_MERCHANT_ID    = os.getenv("ABA_MERCHANT_ID", "")      # 👈 Merchant ID របស់ KHMER SYSTEM (ឧ. r72mCt)
ABA_BASE_URL       = os.getenv("ABA_BASE_URL", "https://khmer-system.com")
ABA_CREATE_URL     = os.getenv("ABA_CREATE_URL", f"{ABA_BASE_URL}/aba-api/generate-qr")
ABA_CHECK_URL      = os.getenv("ABA_CHECK_URL", f"{ABA_BASE_URL}/aba-api/check-payment")

# ── Bakong Open API — Generate Deep Link (បើក App ធនាគារស្វ័យប្រវត្តិ៖ ABA / ACLEDA / Bakong / Wing ...) ──
BAKONG_API_TOKEN    = os.getenv("BAKONG_API_TOKEN", "")   # 👈 Bakong Developer Token ពី https://api-bakong.nbc.gov.kh/register/ — កំណត់ជា Environment Variable
BAKONG_DEEPLINK_API = "https://api-bakong.nbc.gov.kh/v1/generate_deeplink_by_qr"

DEPOSIT_EXPIRE_SEC = 300   # 5 minutes (CamRapidPay expire 5 min)
POLL_INTERVAL      = 8
SMM_ORDER_POLL_INTERVAL = 180   # 3 minutes — Poll ស្ថានភាព Order ពី SMM API

# Flask Control Server
# សុវត្ថិភាព: បើមិនកំណត់ CONTROL_KEY ជា env var ទេ បង្កើត key ចៃដន្យ (មិនប្រើ default
# ដែលគេទាយបាន "change_this_secret" ទៀត) ដើម្បីការពារ /shutdown /restart /broadcast_web
import secrets as _secrets
_CONTROL_KEY_ENV = os.getenv("CONTROL_KEY", "")
if not _CONTROL_KEY_ENV:
    CONTROL_KEY = _secrets.token_urlsafe(24)
    logger.warning(
        "⚠️ CONTROL_KEY មិនបានកំណត់ក្នុង Environment Variable! "
        "បង្កើត key ចៃដន្យបណ្តោះអាសន្នជំនួស (នឹងផ្លាស់ប្តូររាល់ restart): %s "
        "→ សូមកំណត់ CONTROL_KEY ជា env var នៅ Render ដើម្បីឲ្យ key ថេរ។", CONTROL_KEY)
else:
    CONTROL_KEY = _CONTROL_KEY_ENV
CONTROL_PORT       = int(os.getenv("CONTROL_PORT", "5056"))   # 👈 ប្តូរ port នេះបើដំណើរការ bot ច្រើនច្បាប់ក្នុងម៉ាស៊ីនតែមួយ (5056, 5057, 5058...)

# ── Startup guard — ការពារកុំឲ្យ deploy ដោយគ្មាន credential សំខាន់ៗ ──────────
if __name__ == "__main__" and not INSTANCE_NAME:
    _missing = []
    if not BOT_TOKEN:  _missing.append("BOT_TOKEN")
    if not ADMIN_ID:   _missing.append("ADMIN_ID")
    if _missing:
        sys.exit(
            "❌ ខ្វះ Environment Variable ចាំបាច់: " + ", ".join(_missing) +
            "\nសូមកំណត់ក្នុង Render → Environment (កុំដាក់ផ្ទាល់ក្នុងកូដ)។"
        )

# ═══════════════════════════════════════════════════════════
#  FILES  (all persisted on Render Disk so redeploy/restart never wipes data)
# ═══════════════════════════════════════════════════════════
DATA_DIR        = os.environ.get("DATA_DIR", "/var/data")
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = "."   # fallback ក្នុងករណី disk មិនមាន (local/Termux test)

# MASTER_DATA_DIR = folder data "ដើម" (bot ដើម) — clone process នីមួយៗទទួល env
# MASTER_DATA_DIR ពី _spawn_clone() ដូច្នេះទោះបី DATA_DIR ត្រូវបានប្តូរទៅ folder
# ដាច់ដោយឡែករបស់ clone ក៏ដោយ ចំណុចនេះនៅតែចង្អុលទៅ data ដើមដដែល (សម្រាប់ file
# ដែលចង់ឲ្យ share រួម ដូចជា smm_emoji.json)
MASTER_DATA_DIR = os.environ.get("MASTER_DATA_DIR", DATA_DIR)

def _dpath(name):
    return os.path.join(DATA_DIR, name)

def _mdpath(name):
    return os.path.join(MASTER_DATA_DIR, name)

WALLETS_FILE    = _dpath("smm_wallets.json")
USERS_FILE      = _dpath("smm_users.json")
LANG_FILE       = _dpath("smm_lang.json")
PROMO_FILE      = _dpath("smm_promos.json")
SETTINGS_FILE   = _dpath("smm_settings.json")
NOTIFY_FILE     = _dpath("smm_notify.json")

SMM_API_FILE    = _dpath("smm_api.json")
SMM_SVC_FILE    = _dpath("smm_services.json")
SMM_ORD_FILE    = _dpath("smm_orders.json")
SMM_PROFIT_FILE = _dpath("smm_profit.json")
SMM_POLL_FILE   = _dpath("smm_poll.json")
SMM_DEP_FILE    = _dpath("smm_deposits.json")
DEP_BONUS_FILE  = _dpath("smm_deposit_bonus.json")
SUB_ADMIN_FILE  = _dpath("smm_sub_admins.json")
SUPPORT_CFG_FILE= _dpath("smm_support.json")
CAMRAPID_CFG_FILE= _dpath("smm_camrapid.json")
ABA_CFG_FILE    = _dpath("smm_aba.json")
BAKONG_CFG_FILE = _dpath("smm_bakong.json")
WEBHOOK_CFG_FILE = _dpath("smm_webhook.json")
PAYTOGGLE_CFG_FILE = _dpath("smm_paytoggle.json")   # បិទ/បើក វិធីទូទាត់ម្តងៗ (v13)
EMOJI_FILE      = _mdpath("smm_emoji.json")   # ចែក share រួមគ្នារវាង bot ដើម និង clone ទាំងអស់ (មិនញែកតាម DATA_DIR ទេ)

def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default

def _save(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: logger.error(f"Save {path}: {e}")

# ─── Load all state ───
# EMOJI_MAP ត្រូវបានកំណត់ default (None) ខាងលើ — ឥឡូវ merge ជាមួយតម្លៃ
# ដែលធ្លាប់រក្សាទុកនៅក្នុងឯកសារ (បើមាន) ដើម្បីឲ្យ /setemojis រក្សាទុកជាអចិន្ត្រៃយ៍
_EMOJI_DEFAULTS = dict(EMOJI_MAP)
EMOJI_MAP.update(_load(EMOJI_FILE, {}))
EMOJI_KEYS = list(_EMOJI_DEFAULTS.keys())   # បញ្ជី emoji ទាំងអស់ដែល bot ស្គាល់ (សម្រាប់ reference)

wallets      = _load(WALLETS_FILE,   {})
users_db     = _load(USERS_FILE,     {})
user_lang    = _load(LANG_FILE,      {})
promos       = _load(PROMO_FILE,     {})
settings     = _load(SETTINGS_FILE,  {})
notify_cfg   = _load(NOTIFY_FILE,    {"channel_id": "-1003930705105", "enabled": True})

smm_api      = _load(SMM_API_FILE,   {"url": "", "key": ""})
smm_services = _load(SMM_SVC_FILE,   {})
smm_orders   = _load(SMM_ORD_FILE,   {})
smm_profit   = _load(SMM_PROFIT_FILE,{"pct": 20})
DAILY_REPORT_FILE = _dpath("daily_report_cfg.json")
daily_report_cfg  = _load(DAILY_REPORT_FILE, {"enabled": True, "hour": 8})
_KH_TZ = datetime.timezone(datetime.timedelta(hours=7))
smm_poll     = _load(SMM_POLL_FILE,  {"interval": POLL_INTERVAL})
smm_deps     = _load(SMM_DEP_FILE,   {})

# ── Auto Deposit Bonus — "ដាក់ $1 ឡើងទៅ ទទួល 5% ត្រលប់មកវិញ" ──────────
# enabled: បើក/បិទ Auto Bonus, min_amount: ចំនួនអប្បបរមាដែលទទួលបាន Bonus,
# pct: ភាគរយ Bonus (គិតលើចំនួនប្រាក់ដែលដាក់)។ កែបានពី Admin Menu → 🎁 Bonus ដាក់លុយ
dep_bonus_cfg = _load(DEP_BONUS_FILE, {"enabled": True, "min_amount": 1.0, "pct": 5.0})

# ── QR Anti-Spam Cooldown — កែបានពី Admin Menu → ⏳ QR Cooldown (persist ថេរ) ──
DEP_QR_COOLDOWN_FILE = _dpath("dep_qr_cooldown.json")
dep_qr_cooldown_cfg  = _load(DEP_QR_COOLDOWN_FILE, {"seconds": DEP_QR_COOLDOWN_SEC})

# ── Auto-seed TikTok Promote Khmer packages ──
_TIKTOK_PACKAGES = [
    {
        "slug":        "manual_tiktok_promote_p1",
        "label":       "🇰🇭 ❤️ 500-1K + 👁️ 1.8K Views",
        "description": "❤️ 500-1K Likes + 👁️ 1.8K Views\n⏱ 5-15 នាទី",
        "flat_price":  0.99,
    },
    {
        "slug":        "manual_tiktok_promote_p2",
        "label":       "🇰🇭 ❤️ 1K-2K + 👁️ 3.5K Views",
        "description": "❤️ 1K-2K Likes + 👁️ 3.5K Views\n⏱ 5-15 នាទី",
        "flat_price":  1.99,
    },
    {
        "slug":        "manual_tiktok_promote_p3",
        "label":       "🇰🇭 ❤️ 2K-3K + 👁️ 10K Views",
        "description": "❤️ 2K-3K Likes + 👁️ 10K Views\n⏱ 10-20 នាទី",
        "flat_price":  3.25,
    },
    {
        "slug":        "manual_tiktok_promote_p4",
        "label":       "🇰🇭 ❤️ 3K-5K + 👁️ 20K Views",
        "description": "❤️ 3K-5K Likes + 👁️ 20K Views\n⏱ 15-30 នាទី",
        "flat_price":  5.49,
    },
    {
        "slug":        "manual_tiktok_promote_p5",
        "label":       "🇰🇭 ❤️ 500 + 👁️ 1K + 👤 100",
        "description": "❤️ 500 Likes + 👁️ 1K Views + 👤 100 Followers\n⏱ 5-15 នាទី",
        "flat_price":  1.99,
    },
    {
        "slug":        "manual_tiktok_promote_view1",
        "label":       "🇰🇭 👁️ 2K-5K Views",
        "description": "👁️ 2K-5K Views (Video ណាមួយ)\n⏱ 5-15 នាទី",
        "flat_price":  0.99,
    },
    {
        "slug":        "manual_tiktok_promote_view2",
        "label":       "🇰🇭 👁️ 5K-10K Views",
        "description": "👁️ 5K-10K Views (Video ណាមួយ)\n⏱ 5-15 នាទី",
        "flat_price":  1.99,
    },
    {
        "slug":        "manual_tiktok_promote_follow1",
        "label":       "🇰🇭 👤 100-200 Followers",
        "description": "👤 100-200 Followers\n⏱ 10-20 នាទី",
        "flat_price":  0.99,
    },
    {
        "slug":        "manual_tiktok_promote_follow2",
        "label":       "🇰🇭 👤 300-500 Followers",
        "description": "👤 300-500 Followers\n⏱ 10-20 នាទី",
        "flat_price":  1.99,
    },
]
_changed = False
for _pkg in _TIKTOK_PACKAGES:
    _slug = _pkg["slug"]
    if _slug not in smm_services:
        smm_services[_slug] = {
            "api_id":      None,
            "manual":      True,
            "cost_rate":   0,
            "min":         1,
            "max":         1,
            "label":       _pkg["label"],
            "category":    "🇰🇭 TikTok Khmer",
            "flat_price":  _pkg["flat_price"],
            "preset_qtys": [1],
            "description": _pkg["description"],
        }
        _changed = True
    else:
        # ✨ Migration (2026-08-12): រៀបចំ label/description ចាស់ឲ្យស្អាត
        # ស្របគ្នា (icon នៅមុខលេខជានិច្ច, 👁️ មាន VS16 ត្រឹមត្រូវ, K លាកតួពេញ)
        # — ធ្វើតែម្តងគត់ ដោយប្រៀបធៀបនឹង label ចាស់ជាក់លាក់ដែលធ្លាប់ seed ស្រាប់,
        # មិនប៉ះពាល់ admin ដែលធ្លាប់កែ label ដោយខ្លួនឯងរួចហើយទេ
        _old_labels = {
            "manual_tiktok_promote_p1":      "🇰🇭 500-1k ❤️ · 1.8k 👁 View",
            "manual_tiktok_promote_p2":      "🇰🇭 1k-2k ❤️ · 3.5k 👁 View",
            "manual_tiktok_promote_p3":      "🇰🇭 2k-3k ❤️ · 10k 👁 View",
            "manual_tiktok_promote_p4":      "🇰🇭 3k-5k ❤️ · 20k 👁 View",
            "manual_tiktok_promote_p5":      "🇰🇭 500 ❤️ · 1k 👁 · 100 👤 Follow",
            "manual_tiktok_promote_view1":   "🇰🇭 2k-5k 👁 View",
            "manual_tiktok_promote_view2":   "🇰🇭 5k-10k 👁 View",
            "manual_tiktok_promote_follow1": "🇰🇭 100-200 👤 Follow",
            "manual_tiktok_promote_follow2": "🇰🇭 300-500 👤 Follow",
        }
        if smm_services[_slug].get("label") == _old_labels.get(_slug):
            smm_services[_slug]["label"]       = _pkg["label"]
            smm_services[_slug]["description"] = _pkg["description"]
            _changed = True
if _changed:
    _save(SMM_SVC_FILE, smm_services)

# Remove old single-package slug if exists
if "manual_tiktok_promote_khmer" in smm_services:
    smm_services.pop("manual_tiktok_promote_khmer")
    _save(SMM_SVC_FILE, smm_services)




waiting      = {}
lang_cooldown= {}

# ═══════════════════════════════════════════════════════════
#  BOT + HTTP
# ═══════════════════════════════════════════════════════════
# ── Global exception handler — ការពារ "ស្ងាត់ស្ងៀម" ──────────────────────
# បើ handler ណាមួយ (message/callback) throw exception ណាមួយដែលមិនត្រូវបាន
# catch ដោយ try/except ក្នុង handler ខ្លួនឯង, pyTelegramBotAPI លំនាំដើម
# គ្រាន់តែ log ទៅ console ប៉ុណ្ណោះ ដោយគ្មានឆ្លើយតបអ្វីមក User ទាល់តែសោះ —
# នេះជាមូលហេតុចម្បងបំផុតដែល "ចុចប៊ូតុងហើយគ្មានអ្វីកើតឡើង" ។ Handler
# ខាងក្រោមចាប់ error ទាំងអស់ដែលរួចផុតពី try/except ក្នុងស្រុក ហើយ (1) log
# stack trace ពេញលេញ (2) ជូនដំណឹង Admin ជាសារខ្លីៗ ដើម្បីកុំឲ្យ bug
# ត្រូវលាក់កំបាំងទៀតតទៅ។
class _GlobalExceptionHandler(telebot.ExceptionHandler):
    def handle(self, exception):
        import traceback as _tb
        trace = _tb.format_exc()
        logger.error(f"❌ Unhandled exception ក្នុង bot handler:\n{trace}")
        try:
            bot.send_message(ADMIN_ID,
                f"⚠️ <b>Bot Error (internal, User មិនឃើញ)</b>\n"
                f"<code>{str(exception)[:500]}</code>\n\n"
                f"<i>មើល log ពេញលេញនៅ Render console</i>",
                parse_mode="HTML")
        except Exception:
            pass  # កុំឲ្យ error-in-error-handler បង្កជាបញ្ហាបន្ថែម
        return True  # true = បន្តដំណើរការ polling loop (មិនបញ្ឈប់ bot)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None, exception_handler=_GlobalExceptionHandler())

_BOT_USERNAME_CACHE = {"v": None}
def _bot_username():
    """យក username របស់ bot បច្ចុប្បន្ន (cache) — ត្រូវការសម្រាប់ clone bot នីមួយៗ
    ដែលមាន username ខុសៗគ្នា (មិនអាច hardcode បានទេ)"""
    if _BOT_USERNAME_CACHE["v"]:
        return _BOT_USERNAME_CACHE["v"]
    try:
        _BOT_USERNAME_CACHE["v"] = bot.get_me().username
    except Exception as e:
        logger.warning(f"[bot_username] failed: {e}")
        _BOT_USERNAME_CACHE["v"] = "KaiJakLikeBot"
    return _BOT_USERNAME_CACHE["v"]

_BOT_BRAND_CACHE = {"v": None}
def _bot_brand():
    """យកឈ្មោះ (display name) របស់ bot បច្ចុប្បន្នដើម្បីប្រើក្នុងសារទាំងឡាយ —
    ធានាថា Sub Bot នីមួយៗបង្ហាញឈ្មោះខ្លួនឯង មិនមែន 'Kaijaklike' ទេ។"""
    if _BOT_BRAND_CACHE["v"]:
        return _BOT_BRAND_CACHE["v"]
    try:
        _BOT_BRAND_CACHE["v"] = bot.get_me().first_name or "Kaijaklike"
    except Exception as e:
        logger.warning(f"[bot_brand] failed: {e}")
        _BOT_BRAND_CACHE["v"] = "Kaijaklike"
    return _BOT_BRAND_CACHE["v"]


# ── Premium emoji auto-injection — ជាមួយ AUTO-FALLBACK សុវត្ថិភាព ──────────
# គ្រោះថ្នាក់ដែលត្រូវការពារ៖ បើ custom_emoji_id ណាមួយខូច/លែងមាន ឬ admin
# (ADMIN_ID) លែងមាន Telegram Premium ទៀត Telegram server អាច **បដិសេធ
# request ទាំងមូល** (error) — ដែលនឹងធ្វើឲ្យ send_message/edit_message បរាជ័យ
# ⇒ សារ ឬ button ទាំងមូលនោះនឹង "មិនដំណើរការ" ទាំងស្រុង។
# ដំណោះស្រាយ: ព្យាយាមផ្ញើជាមួយ icon/tg-emoji ជាមុនសិន — បើ Telegram បដិសេធ
# ដោយហេតុផលទាក់ទង emoji/icon/premium ប៉ុណ្ណោះ នោះ retry ដោយ **ដកចេញ** icon
# ទាំងអស់ (fallback ទៅ unicode emoji ធម្មតាវិញ) ដើម្បីធានាថា message/button
# តែងតែផ្ញើចេញបានជោគជ័យ — មិនដែលឲ្យ premium emoji ធ្វើឲ្យ button ខូចឡើយ។
def _emojify(text):
    if not text or not isinstance(text, str) or "<tg-emoji" in text:
        return text
    for ch in _EMOJI_CHARS_SORTED:
        eid = EMOJI_MAP.get(ch)
        if eid and ch in text:
            text = text.replace(ch, f'<tg-emoji emoji-id="{eid}">{ch}</tg-emoji>')
    return text

def _strip_tg_emoji_tags(text):
    """ដកចេញ <tg-emoji ...>x</tg-emoji> ទុកតែ x (unicode emoji ធម្មតា)."""
    if not text or not isinstance(text, str):
        return text
    return _re.sub(r'<tg-emoji[^>]*>(.*?)</tg-emoji>', r'\1', text, flags=_re.DOTALL)

def _strip_markup_icons(markup):
    """ដកចេញ icon_custom_emoji_id ពី button ទាំងអស់ក្នុង keyboard (in place)."""
    if markup is None:
        return markup
    try:
        rows = getattr(markup, "keyboard", None)
        if not rows:
            return markup
        for row in rows:
            for btn in row:
                if hasattr(btn, "_emoji_id"):
                    btn._emoji_id = None
    except Exception:
        pass
    return markup

_EMOJI_ERROR_HINTS = ("EMOJI", "ICON", "PREMIUM", "STICKER")

def _looks_emoji_related(exc):
    return any(h in str(exc).upper() for h in _EMOJI_ERROR_HINTS)

def _markup_has_emoji_icon(markup):
    """ត្រឡប់ True បើ keyboard/markup មាន button ណាមួយកំណត់ icon_custom_emoji_id
    (_emoji_id)។ ប្រើដើម្បីសម្រេចថាតើគួរ fallback-retry ដែរឬទេ សូម្បីតែ error
    message មិនបាននិយាយពាក្យទាក់ទង emoji ដោយផ្ទាល់ក៏ដោយ (Telegram ពេលខ្លះ
    បដិសេធ request ទាំងមូលដោយសារ field នេះ ដោយគ្មានប្រាប់ច្បាស់ក្នុង error
    text — ករណីនេះហើយដែលបណ្តាលឲ្យ buttonខ្លះ "ស្ងាត់" ជានិច្ចមុនកែ)។"""
    try:
        rows = getattr(markup, "keyboard", None)
        if not rows:
            return False
        for row in rows:
            for btn in row:
                if getattr(btn, "_emoji_id", None):
                    return True
    except Exception:
        pass
    return False

def _wrap_safe_call(fn, text_kw=None, text_pos=None):
    """រុំ bot method មួយ ដើម្បី (1) ដាក់ tg-emoji ចូល text ស្វ័យប្រវត្តិ បើ
    parse_mode=HTML និង (2) ធានាថា បើ Telegram បដិសេធដោយសារ emoji/icon,
    retry ដោយគ្មាន icon វិញ ដើម្បីកុំឲ្យ button/message បរាជ័យ។"""
    def wrapper(*args, **kwargs):
        args = list(args)
        orig_text, emojified = None, False

        if text_kw is not None and kwargs.get("parse_mode") == "HTML":
            if text_kw in kwargs and kwargs[text_kw]:
                orig_text = kwargs[text_kw]
                new_text = _emojify(orig_text)
                if new_text != orig_text:
                    kwargs[text_kw] = new_text
                    emojified = True
            elif text_pos is not None and len(args) > text_pos and isinstance(args[text_pos], str):
                orig_text = args[text_pos]
                new_text = _emojify(orig_text)
                if new_text != orig_text:
                    args[text_pos] = new_text
                    emojified = True

        markup = kwargs.get("reply_markup")
        has_icon_markup = _markup_has_emoji_icon(markup)

        try:
            return fn(*args, **kwargs)
        except Exception as e:
            # ⚠️ កំណត់ត្រា (កែ 2026-08-13): មុននេះ retry កើតឡើងលុះត្រាតែ error
            # message *contain* ពាក្យ EMOJI/ICON/PREMIUM/STICKER ច្បាស់ៗ។ ប៉ុន្តែ
            # Telegram ជួនកាលបដិសេធ request ទាំងមូល ដោយសារ icon_custom_emoji_id
            # មិនត្រឹមត្រូវ ដោយគ្មានប្រាប់ពាក្យទាំងនោះក្នុង error text ផ្ទាល់ —
            # ធ្វើឲ្យ retry-check ចាស់ខកខាន, exception ត្រូវ raise ចោល, telebot
            # គ្រាន់តែ log ទៅ console ដោយគ្មានឆ្លើយតបអ្វីមកអ្នកប្រើទាល់តែសោះ
            # (button "ស្ងាត់" ជានិច្ច)។ ឥឡូវ retry ក៏កើតឡើងបើ markup មាន
            # icon_custom_emoji_id ណាមួយផងដែរ ទោះ error text មិននិយាយពី emoji
            # ដោយផ្ទាល់ក៏ដោយ។
            if not _looks_emoji_related(e) and not (emojified or has_icon_markup):
                raise
            logger.warning(f"⚠️ Premium emoji/icon ត្រូវបានបដិសេធដោយ Telegram — fallback ទៅ unicode ធម្មតា: {e}")
            if emojified:
                if text_kw is not None and text_kw in kwargs:
                    kwargs[text_kw] = orig_text
                elif text_pos is not None:
                    args[text_pos] = orig_text
            _strip_markup_icons(markup)
            try:
                return fn(*args, **kwargs)
            except Exception as e2:
                logger.error(f"❌ Fallback (គ្មាន icon) ក៏បរាជ័យដែរ — សារនេះនឹងមិនផ្ញើចេញ: {e2}")
                raise
    return wrapper

bot.send_message        = _wrap_safe_call(bot.send_message,        "text", 1)
bot.reply_to            = _wrap_safe_call(bot.reply_to,             "text", 1)
bot.edit_message_text   = _wrap_safe_call(bot.edit_message_text,    "text", 0)
bot.send_photo          = _wrap_safe_call(bot.send_photo,           "caption", 2)
bot.edit_message_caption= _wrap_safe_call(bot.edit_message_caption, "caption", 0)
bot.edit_message_reply_markup = _wrap_safe_call(bot.edit_message_reply_markup, None, None)

# ═══════════════════════════════════════════════════════════
#  MULTI-BOT  — admin អាចបង្កើត bot ថ្មីពី /newbot ខាងក្នុង Telegram
#  bot ថ្មីដំណើរការជា process ដាច់ដោយឡែក ដោយប្រើ script នេះឯងជា worker
# ═══════════════════════════════════════════════════════════
import subprocess as _subprocess
CLONES_DIR     = _dpath("bot_clones")    # folder ផ្ទុក data របស់ bot រងនីមួយៗ
CLONES_REGISTRY= _dpath("bot_clones.json")
CLONE_BASE_PORT= 5057                   # bot ដើមប្រើ 5056, clone ចាប់ពី 5057
clone_registry = _load(CLONES_REGISTRY, {})   # name -> {token, admin_id, camrapid_key, port, pid}

# ── Sub-admins, Support config, CamRapidPay config (editable at runtime) ──
sub_admins   = _load(SUB_ADMIN_FILE,   [])          # list of int UIDs
support_cfg  = _load(SUPPORT_CFG_FILE, {"kh": "", "en": ""})   # custom support text per lang
camrapid_cfg = _load(CAMRAPID_CFG_FILE, {"key": ""})            # live-editable API key
aba_cfg      = _load(ABA_CFG_FILE, {"key": "", "merchant_id": ""})  # live-editable ABA PayWay (KHMER SYSTEM) key/merchant
bakong_cfg   = _load(BAKONG_CFG_FILE, {"token": ""})            # live-editable Bakong Developer Token
webhook_cfg  = _load(WEBHOOK_CFG_FILE, {"url": ""})              # live-editable CamRapidPay webhook URL
paytoggle_cfg= _load(PAYTOGGLE_CFG_FILE, {"camrapid_enabled": True, "aba_enabled": True})  # បិទ/បើក វិធីទូទាត់ (v13)

def _effective_camrapid_key():
    """Return runtime key if set, else fall back to env/default"""
    return camrapid_cfg.get("key") or CAMRAPID_API_KEY

def _effective_aba_key():
    """Return runtime ABA PayWay (KHMER SYSTEM) Profile Key if set, else fall back to env/default"""
    return aba_cfg.get("key") or ABA_API_KEY

def _effective_aba_merchant():
    """Return runtime ABA PayWay (KHMER SYSTEM) Merchant ID if set, else fall back to env/default"""
    return aba_cfg.get("merchant_id") or ABA_MERCHANT_ID

PAY_METHOD_LABELS = {"camrapid": "🔄 CamRapidPay KHQR", "aba": "💳 ABA PayWay"}

def is_pay_method_enabled(method):
    """True បើ admin មិនទាន់បិទវិធីទូទាត់នេះទេ (default = True បើមិនទាន់កំណត់អ្វីសោះ) — v13.
    ចំណាំ: នេះជា Toggle ដាច់ដោយឡែកពី Key/Merchant ID — វិធីទូទាត់ណាមួយត្រូវការទាំង ២យ៉ាង
    (Key/Merchant ID កំណត់រួច + Toggle នេះជា ON) ទើបប្រើបានជាក់ស្តែង។"""
    return bool(paytoggle_cfg.get(f"{method}_enabled", True))

def set_pay_method_enabled(method, enabled):
    paytoggle_cfg[f"{method}_enabled"] = bool(enabled)
    _save(PAYTOGGLE_CFG_FILE, paytoggle_cfg)

def _paytoggle_status_lines():
    lines = []
    for method, label in PAY_METHOD_LABELS.items():
        configured = _effective_camrapid_key() if method == "camrapid" else has_aba_payway()
        on = is_pay_method_enabled(method)
        status = "🟢 បើក" if on else "🔴 បិទ"
        cfg_note = "" if configured else " ⚠️ (មិនទាន់កំណត់ Key)"
        lines.append(f"{label}: <b>{status}</b>{cfg_note}")
    return "\n".join(lines)

def _paytoggle_kb():
    kb = InlineKeyboardMarkup()
    for method, label in PAY_METHOD_LABELS.items():
        on = is_pay_method_enabled(method)
        btn_txt = f"{'🔴 បិទ' if on else '🟢 បើក'} {label}"
        kb.add(InlineKeyboardButton(btn_txt, callback_data=f"paytoggle:{method}",
                                    color=("danger" if on else "active")))
    return kb

def _effective_bakong_token():
    """Return runtime Bakong token if set, else fall back to env/default"""
    return bakong_cfg.get("token") or BAKONG_API_TOKEN

def is_admin(uid):
    """True if uid is master admin OR sub-admin"""
    return uid == ADMIN_ID or uid in sub_admins
clone_procs    = {}                            # name -> subprocess.Popen (តែក្នុង process នេះប៉ុណ្ណោះ)

def _clone_dir(name):
    d = os.path.join(CLONES_DIR, name)
    os.makedirs(d, exist_ok=True)
    return d

def _next_clone_port():
    used = {v.get("port") for v in clone_registry.values()}
    p = CLONE_BASE_PORT
    while p in used:
        p += 1
    return p

def _clone_is_running(name):
    proc = clone_procs.get(name)
    return proc is not None and proc.poll() is None

def _spawn_clone(name, cfg):
    wdir = _clone_dir(name)
    env = os.environ.copy()
    env["BOT_TOKEN"]        = cfg["token"]
    env["ADMIN_ID"]         = str(cfg["admin_id"])
    env["CAMRAPID_API_KEY"] = cfg.get("camrapid_key", "")
    env["ABA_API_KEY"]      = cfg.get("aba_key", "")
    env["ABA_MERCHANT_ID"]  = cfg.get("aba_merchant", "")
    env["PAY_METHOD"]       = cfg.get("pay_method", "auto")
    env["CONTROL_PORT"]     = str(cfg["port"])
    env["CONTROL_KEY"]      = f"ctrl_{name}"
    env["INSTANCE_NAME"]    = name
    env["BOT_DISPLAY_NAME"] = cfg.get("display_name", name)
    env["BOT_WELCOME_MSG"]  = cfg.get("welcome_msg", "")
    env["DATA_DIR"]         = wdir   # ★ ធ្វើឲ្យ clone នីមួយៗសរសេរ/អាន data (users/wallets/orders/…) ដាច់ដោយឡែកក្នុង bot_clones/<name>/ មិនប៉ះពាល់ bot ដើម ឬ clone ផ្សេងទៀត
    env["MASTER_DATA_DIR"]  = MASTER_DATA_DIR   # ★ រក្សា smm_emoji.json ជាដើម ឲ្យចង្អុលទៅ data ដើមរួមគ្នា មិនប្រែប្រួលទៅតាម DATA_DIR របស់ clone
    logf = open(os.path.join(wdir, "bot.log"), "a", encoding="utf-8")
    proc = _subprocess.Popen(
        [sys.executable, os.path.abspath(__file__)],
        cwd=wdir, env=env, stdout=logf, stderr=_subprocess.STDOUT,
    )
    clone_procs[name] = proc
    return proc

def _stop_clone(name):
    proc = clone_procs.get(name)
    if proc and proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=8)
        except _subprocess.TimeoutExpired: proc.kill()
    clone_procs.pop(name, None)

def _clone_watchdog():
    while True:
        time.sleep(20)
        for name, cfg in list(clone_registry.items()):
            if not _clone_is_running(name):
                logger.warning(f"Clone '{name}' not running — starting/restarting...")
                try:
                    _spawn_clone(name, cfg)
                    bot.send_message(ADMIN_ID, f"⚠️ Bot '{name}' ត្រូវបាន (re)start ស្វ័យប្រវត្តិ។")
                except Exception as e:
                    logger.error(f"Clone watchdog failed for {name}: {e}")


def _make_session():
    s = http_req.Session()
    r = Retry(total=3, backoff_factor=2, status_forcelist=[500,502,503,504])
    a = HTTPAdapter(max_retries=r)
    s.mount("http://", a); s.mount("https://", a)
    return s
http = _make_session()

# ═══════════════════════════════════════════════════════════
#  LANGUAGE
# ═══════════════════════════════════════════════════════════
STRINGS = {
    "kh": {
        "welcome": (
            "សួស្តី បង/ប្អូន! 👋\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "ស្វាគមន៍មក <b>Kaijaklike</b> 🇰🇭\n"
            "ខ្ញុំជួយបង្កើន Views · Likes · Followers\n"
            "សម្រាប់ TikTok និង Social Media ផ្សេងៗ!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💳 លុយបច្ចុប្បន្ន: <b>${:.2f}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👇 ចុចជ្រើសពី Menu ខាងក្រោមបាន!"
        ),
        "select_lang":   "🌐 ជ្រើសភាសាដែលអ្នកចូលចិត្ត:",
        "lang_set":      "✅ ផ្លាស់ប្តូរភាសារួចហើយ!",
        "menu":          "🏠 ត្រឡប់ Menu",
        "banned":        "🚫 គណនីរបស់អ្នកត្រូវបាន ban! សូមទំនាក់ Admin ប្រសិនបើមានបញ្ហា។",
        "cancel_ok":     "🏠 ត្រឡប់ Menu ហើយ! 😊",
        "no_service":    "❌ មិនទាន់មាន Service ទេ នឹងដាក់ឆាប់ៗ!",
        "choose_platform": "ជ្រើស Platform ដែលចង់ boost:",
        "choose_qty":    "ជ្រើស Package:",
        "send_link":     "ផ្ញើ Link វីដេអូរបស់អ្នកមក:",
        "low_balance":   "❌ លុយមិនគ្រប់! សូម Top Up ជាមុន 💸",
        "order_done":    "✅ Order បានទទួលហើយ! នឹងដំណើរការឆាប់ៗ 🙏\nអរគុណដែលប្រើសេវា Kaijaklike! 💙",
        "deposit_ok":    "✅ ដាក់លុយបានជោគជ័យ! 🎉\nអរគុណច្រើនដែលបន្ថែម Balance! 💙 Kaijaklike",
        "qr_expired":    "⏰ QR ផុតហើយ! សូម Top Up ម្តងទៀតនៅ",
        "qr_error":      "⚠️ មានបញ្ហា Generate QR! សូមទំនាក់ Admin 🙏",
        "track_prompt":  "🔍 វាយ Order ID របស់អ្នក (ឧ: KZ12345):",
        "order_notfound":"❌ រកមិនឃើញ Order នេះទេ! ត្រូវប្រាកដ ID ត្រឹមត្រូវ",
        "no_orders":     "❌ មិនទាន់មាន Order ណាមួយទេ!",
        "how_to_use": (
            "💡 <b>របៀបប្រើ Kaijaklike</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ ដាក់លុយ → ចុច <b>💸 បញ្ចូលលុយ</b> → Scan QR\n"
            "2️⃣ Order → ចុច <b>🛒 បញ្ជាទិញ</b> → ជ្រើស Package → ផ្ញើ Link\n"
            "3️⃣ តាមដាន → ចុច <b>📋 ប្រវត្តិ</b> → មើលស្ថានភាព Order\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "❓ មានសំណួរ ទំនាក់ Admin បានគ្រប់ពេល! 😊"
        ),
        "support_msg": (
            "💬 <b>ទំនាក់ Admin Kaijaklike</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📞 Admin: @smos_sne1\n"
            "⏱ ទំនាក់បានគ្រប់ពេល!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💡 មានបញ្ហា Order ឬ Payment\n"
            "ផ្ញើ Order ID មកផ្ទាល់ Admin 🙏"
        ),
        "fallback": "😊 ប្រើប៊ូតុង Menu ខាងក្រោមបាន!",
    },
    "en": {
        "welcome": (
            "Hey! 👋 Welcome to <b>Kaijaklike</b> 🇰🇭\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "We help grow your TikTok & Social Media\n"
            "Views · Likes · Followers — fast & real!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💳 Your Balance: <b>${:.2f}</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👇 Pick from the menu below!"
        ),
        "select_lang":   "🌐 Choose your language:",
        "lang_set":      "✅ Language updated!",
        "menu":          "🏠 Back to Menu",
        "banned":        "🚫 Your account has been banned. Contact Admin if you think this is a mistake.",
        "cancel_ok":     "🏠 Back to Menu!",
        "no_service":    "❌ No services yet — check back soon!",
        "choose_platform": "Pick a platform to boost:",
        "choose_qty":    "Choose a package:",
        "send_link":     "Send your video link:",
        "low_balance":   "❌ Not enough balance! Please Top Up first 💸",
        "order_done":    "✅ Order received! We'll process it shortly 🙏\nThank you for using Kaijaklike! 💙",
        "deposit_ok":    "✅ Deposit successful! 🎉\nThank you for topping up! 💙 Kaijaklike",
        "qr_expired":    "⏰ QR expired! Please Top Up again",
        "qr_error":      "⚠️ QR error! Please contact Admin 🙏",
        "track_prompt":  "🔍 Send your Order ID (e.g. KZ12345):",
        "order_notfound":"❌ Order not found! Make sure the ID is correct.",
        "no_orders":     "❌ No orders yet!",
        "how_to_use": (
            "💡 <b>How to use Kaijaklike</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ Top Up → Tap <b>💸 Top Up</b> → Scan QR\n"
            "2️⃣ Order → Tap <b>🛒 Order</b> → Pick package → Send link\n"
            "3️⃣ Track → Tap <b>📋 History</b> → Check status\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "❓ Questions? Contact Admin anytime! 😊"
        ),
        "support_msg": (
            "💬 <b>Contact Kaijaklike Admin</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📞 Admin: @smos_sne1\n"
            "⏱ Available anytime!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💡 For order or payment issues,\n"
            "send your Order ID directly to Admin 🙏"
        ),
        "fallback": "😊 Use the menu buttons below!",
    },
}

def get_lang(uid): return user_lang.get(str(uid), "kh")

def t(uid, key, *args):
    lang = get_lang(uid)
    s = STRINGS.get(lang, STRINGS["kh"]).get(key) or STRINGS["kh"].get(key, key)
    if "Kaijaklike" in s:
        s = s.replace("Kaijaklike", _bot_brand())
    if args:
        try: return s.format(*args)
        except: return s
    return s

def lang_select_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇰🇭 ខ្មែរ", callback_data="setlang:kh", color="active"),
         InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en", color="active")]
    ])

# ═══════════════════════════════════════════════════════════
#  WALLET HELPERS
# ═══════════════════════════════════════════════════════════
def bal(uid): return float(wallets.get(str(uid), 0))
def add_bal(uid, amt):
    wallets[str(uid)] = round(bal(uid) + amt, 2)
    _save(WALLETS_FILE, wallets)
def ded_bal(uid, amt):
    wallets[str(uid)] = max(0, round(bal(uid) - amt, 2))
    _save(WALLETS_FILE, wallets)
def set_bal(uid, amt):
    wallets[str(uid)] = round(float(amt), 2)
    _save(WALLETS_FILE, wallets)

# ═══════════════════════════════════════════════════════════
#  PROMO CODE
# ═══════════════════════════════════════════════════════════
def apply_promo(uid, code, amount):
    code = code.strip().upper()
    p = promos.get(code)
    if not p: return amount, 0, "❌ Promo Code ខុស!"
    if p.get("uses", 0) > 0 and p.get("used", 0) >= p["uses"]:
        return amount, 0, "❌ Promo Code ផុតសិទ្ធហើយ!"
    user_used = p.get("user_used", {})
    if str(uid) in user_used:
        return amount, 0, "❌ អ្នកបានប្រើ Promo Code នេះហើយ!"
    # ការពារ Double-dip៖ កុំឲ្យ Generate ច្រើន QR ជាមួយ Code ដដែល ខណៈពេលមួយ Pending ចាំបង់ប្រាក់ស្រាប់
    # (ព្រោះ confirm_promo() ត្រូវបានពន្យារពេលរហូតដល់ Payment ពិតជាបានបញ្ជាក់ មិនមែនពេល Generate QR ទៀតទេ)
    for d in smm_deps.values():
        if d.get("uid") == str(uid) and d.get("status") == "pending" and d.get("promo") == code:
            return amount, 0, "❌ អ្នកមាន QR Pending ដែលប្រើ Promo Code នេះរួចហើយ! សូមបង់ប្រាក់ ឬចាំវាផុតកំណត់សិន។"
    if p.get("pct", False):
        discount = round(amount * float(p["discount"]) / 100, 2)
    else:
        discount = min(float(p["discount"]), amount)
    final = max(0, round(amount - discount, 2))
    return final, discount, None

def confirm_promo(code, uid):
    code = code.strip().upper()
    p = promos.get(code)
    if not p: return
    p["used"] = p.get("used", 0) + 1
    uu = p.get("user_used", {})
    uu[str(uid)] = 1
    p["user_used"] = uu
    _save(PROMO_FILE, promos)

# ═══════════════════════════════════════════════════════════
#  SMM HELPERS
# ═══════════════════════════════════════════════════════════
def _smm_get_categories():
    cats = []
    for s in smm_services.values():
        c = s.get("category", "Other")
        if c not in cats: cats.append(c)
    return cats

def _smm_get_svcs_in_cat(cat):
    return [(slug, s) for slug, s in smm_services.items() if s.get("category") == cat]

# ── Link validation (កុំឲ្យ user ដាក់ Link ខុស Platform) ───────────────
_URL_RE = _re.compile(r"^https?://[^\s/$.?#].[^\s]*$", _re.IGNORECASE)

# ✏️ Platform ស្ដង់ដារ — key ត្រូវបានរក្សាទុកផ្ទាល់ក្នុង Service ("platform" field)
# ដើម្បីសម្គាល់ Link ដោយច្បាស់លាស់តាមកម្មវិធីនីមួយៗ (មិនទាមទារ guess ពី category ទៀត)
_PLATFORM_CHOICES = [
    ("tiktok",    "🎵 TikTok",     ("tiktok.com",)),
    ("facebook",  "📘 Facebook",   ("facebook.com", "fb.com", "fb.watch")),
    ("instagram", "📸 Instagram",  ("instagram.com", "instagr.am")),
    ("youtube",   "▶️ YouTube",    ("youtube.com", "youtu.be")),
    ("telegram",  "📱 Telegram",   ("t.me", "telegram.me", "telegram.org")),
    ("twitter",   "🐦 Twitter/X",  ("twitter.com", "x.com")),
    ("threads",   "🧵 Threads",    ("threads.net",)),
    ("other",     "🔓 ផ្សេង (មិនកំណត់ Domain)", None),
]
_PLATFORM_DOMAINS_BY_KEY = {k: d for k, _label, d in _PLATFORM_CHOICES}
_PLATFORM_LABEL_BY_KEY   = {k: lbl for k, lbl, _d in _PLATFORM_CHOICES}
# Category preset (buttons ចាស់) → platform key ស្វ័យប្រវត្តិ (មិនចាំបាច់សួរម្ដងទៀត)
_CAT_TO_PLATFORM_KEY = {
    "TikTok": "tiktok", "🇰🇭 TikTok Khmer": "tiktok",
    "Facebook": "facebook", "Instagram": "instagram", "YouTube": "youtube",
    "Telegram": "telegram", "Twitter": "twitter",
}
# keyword ស្វែងរកនៅក្នុង slug/category/label (fallback សម្រាប់ Service ចាស់ៗ
# ដែលមិនទាន់មាន "platform" field ជាក់លាក់)
_PLATFORM_DOMAINS = [
    (("tiktok",),                 _PLATFORM_DOMAINS_BY_KEY["tiktok"]),
    (("facebook", "fb "),          _PLATFORM_DOMAINS_BY_KEY["facebook"]),
    (("instagram", " ig ", "insta"), _PLATFORM_DOMAINS_BY_KEY["instagram"]),
    (("youtube", " yt "),          _PLATFORM_DOMAINS_BY_KEY["youtube"]),
    (("telegram", " tg "),         _PLATFORM_DOMAINS_BY_KEY["telegram"]),
    (("twitter", " x "),           _PLATFORM_DOMAINS_BY_KEY["twitter"]),
    (("threads",),                 _PLATFORM_DOMAINS_BY_KEY["threads"]),
]

def _platform_pick_kb(prefix):
    """ស្ថាបនា Inline Keyboard ជ្រើសរើស Platform (2 columns) សម្រាប់ prefix ដែលបញ្ជាក់"""
    kb = InlineKeyboardMarkup()
    row = []
    for key, label, _d in _PLATFORM_CHOICES:
        row.append(InlineKeyboardButton(label, callback_data=f"{prefix}:{key}",
                                         color=("inactive" if key == "other" else "active")))
        if len(row) == 2:
            kb.row(*row); row = []
    if row: kb.row(*row)
    return kb

def _detect_platform_domains(slug, s):
    """រកឈ្មោះ Platform ដែលរំពឹងទុក៖ ប្រើ "platform" field ជាក់លាក់ជាមុនសិន
    (កំណត់ដោយ Admin ពេលបង្កើត Service), បើគ្មាន ត្រឡប់ទៅ guess ពី category/label ចាស់វិញ។"""
    platform = s.get("platform")
    if platform:
        return _PLATFORM_DOMAINS_BY_KEY.get(platform)
    cat = s.get("category", "")
    if cat in _CAT_TO_PLATFORM_KEY:
        return _PLATFORM_DOMAINS_BY_KEY.get(_CAT_TO_PLATFORM_KEY[cat])
    hay = f" {slug} {cat} {s.get('label','')} ".lower()
    for keywords, domains in _PLATFORM_DOMAINS:
        for kw in keywords:
            if kw.strip() in hay:
                return domains
    return None

# domain → platform key, សម្រាប់ Auto-detect Platform ផ្ទាល់ពី Link ដែល User ផ្ញើមក
_DOMAIN_TO_PLATFORM_KEY = {}
for _k, _lbl, _doms in _PLATFORM_CHOICES:
    if _doms:
        for _d in _doms:
            _DOMAIN_TO_PLATFORM_KEY[_d] = _k

def _detect_link_platform(link):
    """ស្គាល់ Platform ពី Domain នៃ Link ខ្លួនឯង។ ត្រឡប់ (key, label) ឬ (None, None) បើមិនស្គាល់។"""
    try:
        netloc = link.split("://", 1)[-1].split("/", 1)[0].lower()
    except Exception:
        return None, None
    for dom, key in _DOMAIN_TO_PLATFORM_KEY.items():
        if netloc == dom or netloc.endswith("." + dom):
            return key, _PLATFORM_LABEL_BY_KEY.get(key, key)
    return None, None

def _validate_order_link(link, slug, s):
    """ត្រឡប់ (True, None) បើ Link ត្រឹមត្រូវ, ឬ (False, error_msg) បើខុស។"""
    link = (link or "").strip()
    if not link or " " in link or not _URL_RE.match(link):
        return False, (
            "❌ <b>Link មិនត្រឹមត្រូវ!</b>\n"
            "សូមផ្ញើ Link ដែលចាប់ផ្ដើមដោយ <code>http://</code> ឬ <code>https://</code> "
            "ដោយគ្មានចន្លោះ (space) ។"
        )
    domains = _detect_platform_domains(slug, s)
    if domains:
        netloc = link.split("://", 1)[-1].split("/", 1)[0].lower()
        if not any(netloc == d or netloc.endswith("." + d) for d in domains):
            expected = " / ".join(domains)
            _detected_key, detected_label = _detect_link_platform(link)
            got_line = (f"Link ដែលអ្នកផ្ញើគឺជា Link <b>{detected_label}</b> 👀\n"
                        if detected_label else
                        f"Link ដែលអ្នកផ្ញើមកពី Domain <code>{netloc}</code> ដែល Bot មិនស្គាល់ ⚠️\n")
            return False, (
                f"❌ <b>Link មិនត្រូវនឹង Service នេះទេ!</b>\n"
                f"{got_line}"
                f"Service នេះទាមទារ Link ពី <b>{expected}</b>\n"
                f"សូមពិនិត្យ Link ឡើងវិញ ហើយផ្ញើម្ដងទៀត។"
            )
    return True, None

def _auto_dep_bonus(amount):
    """ត្រឡប់ Bonus ស្វ័យប្រវត្តិ (USD) សម្រាប់ចំនួនប្រាក់ដែលដាក់ — 0 បើមិនចូលលក្ខខណ្ឌ។"""
    try:
        if not dep_bonus_cfg.get("enabled", True):
            return 0.0
        amount = float(amount)
        min_amt = float(dep_bonus_cfg.get("min_amount", 1.0))
        if amount < min_amt:
            return 0.0
        pct = float(dep_bonus_cfg.get("pct", 5.0))
        if pct <= 0:
            return 0.0
        return round(amount * pct / 100, 2)
    except Exception:
        return 0.0

def _dep_bonus_status_text():
    c = dep_bonus_cfg
    if not c.get("enabled", True):
        return "🎁 <b>Bonus ដាក់លុយ៖</b> <i>បិទ</i>"
    return (f"🎁 <b>Bonus ដាក់លុយ៖</b> <b>{float(c.get('pct',5.0)):.0f}%</b> "
            f"(ដាក់ចាប់ពី <b>${float(c.get('min_amount',1.0)):.2f}</b> ឡើងទៅ)")

def _dep_qr_cooldown_status_text():
    sec = int(dep_qr_cooldown_cfg.get("seconds", DEP_QR_COOLDOWN_SEC))
    if sec <= 0:
        return "⏳ <b>QR Cooldown៖</b> <i>បិទ (គ្មានកំណត់)</i>"
    return (f"⏳ <b>QR Cooldown៖</b> <b>{sec} វិនាទី</b>\n"
            f"👉 User ម្នាក់ៗត្រូវរង់ចាំ {sec} វិនាទី មុននឹងបង្កើត QR ថ្មីម្តងទៀត "
            f"(ការពារ Spam ចុច 💸 បញ្ចូលលុយ ជាប់ៗគ្នា)។ Admin មិនកំណត់ទេ។")

def _smm_profit_pct(): return float(smm_profit.get("pct", 20))

def _smm_sell_rate(cost, slug=None):
    s = smm_services.get(slug, {})
    if s.get("flat_price"): return float(s["flat_price"]) * 1000  # convert to per-1K for display
    if s.get("custom_price"): return float(s["custom_price"])
    return round(float(cost) * (1 + _smm_profit_pct() / 100), 4)

def _round_price_01(x):
    """បង្គត់តម្លៃទៅខ្ទង់ទសភាគទី 1 (0.1$) ដោយប្រើ round-half-up ធម្មតា — ខ្ទង់
    ទសភាគទី 2 ≥ 5 ត្រូវបង្គត់ឡើង, < 5 បង្គត់ចុះ។ ឧ. $1.23 → $1.2, $1.25 → $1.3,
    $1.27 → $1.3 ។ ប្រើ Decimal ដើម្បីជៀសវាង floating-point rounding ខុសឆ្គង
    (round() ធម្មតារបស់ Python ប្រើ banker's rounding ដែលអាចបង្គត់ខុសពីអ្វី
    ដែលមនុស្សរំពឹងទុក)។
    ⚠️ Guard (កែ 2026-08-17): បើតម្លៃដើមធំជាង 0 ប៉ុន្តែតូចជាង $0.05, ការបង្គត់
    ធម្មតានឹងបង្គត់ចុះទៅ <b>$0.00</b> — ធ្វើឲ្យសេវាមួយចំនួន (qty តូច × rate
    ទាប) បង្ហាញតម្លៃ $0.0000 ខណៈវាមិនមែនឥតគិតថ្លៃទេ។ ក្នុងករណីនេះ បង្គត់ឡើង
    ទៅ $0.10 ជំនួសវិញ ដើម្បីកុំឲ្យលក់ក្នុងតម្លៃ $0 ។"""
    r = float(_Decimal(str(x)).quantize(_Decimal("0.1"), rounding=_ROUND_HALF_UP))
    if r == 0.0 and float(x) > 0:
        return 0.1
    return r

def _smm_price_for_order(slug, qty):
    """Get actual price for an order (handles flat_price services)"""
    s = smm_services.get(slug, {})
    if s.get("flat_price"):
        return float(s["flat_price"])  # flat: តម្លៃកំណត់ដោយ Admin ដោយផ្ទាល់ (ឧ. $0.99) —
                                        # មិនបង្គត់ទេ ព្រោះជាតម្លៃចិត្តសាស្ត្រដែល Admin
                                        # ចង់ឲ្យជាក់លាក់ តម្លៃប្រភេទនេះមិនមែនគណនាចេញទេ
    sr = _smm_sell_rate(s.get("cost_rate", 0), slug)
    return _round_price_01(round(sr * qty / 1000, 4))

def _smm_cost_for_order(slug, qty):
    """គណនាតម្លៃដើម (Provider cost) របស់ Order មួយ — ប្រើ cost_rate បច្ចុប្បន្ន
    របស់ Service នោះ។ សម្រាប់ Flat/Manual item (flat_price) cost_rate តែងតែ 0
    ដូច្នេះ profit = 100% នៃតម្លៃលក់ (ដូចគ្នានឹងវិធីគណនា sell-rate ផ្សេងទៀត
    ក្នុងកូដ — ព្រោះមិនមានតាមដាន cost ដោយឡែកសម្រាប់ទំនិញទាំងនេះ)។"""
    s = smm_services.get(slug, {})
    if s.get("flat_price"):
        return 0.0
    cost_rate = float(s.get("cost_rate", 0) or 0)
    return round(cost_rate * qty / 1000, 4)

def _profit_sum(period_days=None):
    """សរុប (revenue, cost, profit, count, margin%) របស់ SMM Orders ក្នុងចន្លោះ
    period_days ថ្ងៃចុងក្រោយ (None = គ្រប់ពេល)។ Order ស្ថានភាព rejected/canceled
    ត្រូវលើកលែង ព្រោះលុយត្រូវបានសងវិញទាំងអស់ — មិនមែនចំណេញពិតប្រាកដទេ។ Order
    partial គិត Revenue ដកចេញនូវចំនួនលុយដែលបានសងវិញ (refunded) ដើម្បីឲ្យត្រឹមត្រូវ។"""
    cutoff = int(time.time()) - period_days * 86400 if period_days else 0
    revenue = cost = 0.0
    count = 0
    for o in smm_orders.values():
        if o.get("status") in ("rejected", "canceled"):
            continue
        if o.get("ts", 0) < cutoff:
            continue
        price = float(o.get("price", 0) or 0) - float(o.get("refunded", 0) or 0)
        revenue += price
        cost += _smm_cost_for_order(o.get("slug", ""), o.get("qty", 0))
        count += 1
    profit = revenue - cost
    margin = (profit / revenue * 100) if revenue else 0.0
    return revenue, cost, profit, count, margin

def _profit_report_text():
    """សាងសង់របាយការណ៍ចំណេញពេញលេញ — ថ្ងៃនេះ / សប្តាហ៍នេះ / ខែនេះ / សរុប។"""
    lines = ["💹 <b>របាយការណ៍ចំណេញ (Profit Report)</b>", "━━━━━━━━━━━━━━━━━━"]
    for label, days in [("📅 ថ្ងៃនេះ (24ម៉ោង)", 1),
                         ("🗓️ សប្តាហ៍នេះ (7ថ្ងៃ)", 7),
                         ("📆 ខែនេះ (30ថ្ងៃ)", 30)]:
        rev, cost, profit, cnt, margin = _profit_sum(days)
        lines.append(
            f"\n{label}\n"
            f"  🛒 Orders: <b>{cnt}</b>  |  💵 លក់: <b>${rev:.2f}</b>\n"
            f"  📦 ដើម: <b>${cost:.2f}</b>  |  💹 ចំណេញ: <b>${profit:.2f}</b> ({margin:.1f}%)")
    rev, cost, profit, cnt, margin = _profit_sum(None)
    lines.append(
        f"\n📊 <b>សរុបគ្រប់ពេល</b>\n"
        f"  🛒 Orders: <b>{cnt}</b>  |  💵 លក់: <b>${rev:.2f}</b>\n"
        f"  📦 ដើម: <b>${cost:.2f}</b>  |  💹 ចំណេញ: <b>${profit:.2f}</b> ({margin:.1f}%)")
    lines.append("\n<i>* លុប Order rejected/canceled ចេញ (បានសងលុយវិញទាំងអស់) · Order partial ដកចំនួនសងវិញ · Cost គិតតាមអត្រាបច្ចុប្បន្នរបស់ Service</i>")
    return "\n".join(lines)

@bot.message_handler(commands=["profit"])
def cmd_profit(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, _profit_report_text(), parse_mode="HTML")

def _top_report_text(period_days=30, top_n=5):
    """សាងសង់របាយការណ៍ Top Services (លក់ដាច់បំផុត) និង Top Clients (ចំណាយច្រើន
    បំផុត) ក្នុងចន្លោះ period_days ថ្ងៃចុងក្រោយ។ លើកលែង Order rejected/canceled
    ដូចគ្នានឹង Profit Report ដែរ។"""
    cutoff = int(time.time()) - period_days * 86400 if period_days else 0
    svc_stats, client_stats = {}, {}
    for o in smm_orders.values():
        if o.get("status") in ("rejected", "canceled"):
            continue
        if o.get("ts", 0) < cutoff:
            continue
        price = float(o.get("price", 0) or 0) - float(o.get("refunded", 0) or 0)
        slug  = o.get("slug", "")
        label = o.get("label", slug)
        cs = svc_stats.setdefault(slug, [0, 0.0, label])
        cs[0] += 1; cs[1] += price
        uid = o.get("uid", "")
        cu = client_stats.setdefault(uid, [0, 0.0])
        cu[0] += 1; cu[1] += price
    top_svcs    = sorted(svc_stats.items(),    key=lambda kv: kv[1][1], reverse=True)[:top_n]
    top_clients = sorted(client_stats.items(), key=lambda kv: kv[1][1], reverse=True)[:top_n]

    lines = [f"🏆 <b>Top {top_n} — {period_days} ថ្ងៃចុងក្រោយ</b>", "━━━━━━━━━━━━━━━━━━"]
    lines.append("\n📦 <b>Services លក់ដាច់បំផុត:</b>")
    if top_svcs:
        medal = ["🥇", "🥈", "🥉"]
        for i, (slug, (cnt, rev, label)) in enumerate(top_svcs):
            m = medal[i] if i < 3 else f"{i+1}."
            lines.append(f"  {m} {label} — {cnt} orders · ${rev:.2f}")
    else:
        lines.append("  <i>គ្មានទិន្នន័យ</i>")

    lines.append("\n👤 <b>Client ចំណាយច្រើនបំផុត:</b>")
    if top_clients:
        medal = ["🥇", "🥈", "🥉"]
        for i, (uid, (cnt, rev)) in enumerate(top_clients):
            u = users_db.get(str(uid), {})
            name = u.get("name") or u.get("username") or "?"
            m = medal[i] if i < 3 else f"{i+1}."
            lines.append(f"  {m} {name} (<code>{uid}</code>) — {cnt} orders · ${rev:.2f}")
    else:
        lines.append("  <i>គ្មានទិន្នន័យ</i>")
    lines.append("\n<i>* លុប Order rejected/canceled ចេញ</i>")
    return "\n".join(lines)

def daily_report_kb():
    on   = daily_report_cfg.get("enabled", True)
    hour = daily_report_cfg.get("hour", 8)
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("🟢 បើក" + (" ✅" if on else ""),  callback_data="dreport:on",  color=("success" if on else "active")),
        InlineKeyboardButton("🔴 បិទ" + (" ✅" if not on else ""), callback_data="dreport:off", color=("danger" if not on else "active")),
    )
    kb.row(InlineKeyboardButton(f"⏰ ម៉ោង: {hour:02d}:00 (ខ្មែរ) — ចុចប្តូរ", callback_data="dreport:hour", color="active"))
    kb.row(InlineKeyboardButton("📤 សាកល្បងផ្ញើឥឡូវ", callback_data="dreport:test", color="active"))
    return kb

@bot.callback_query_handler(func=lambda c: c.data.startswith("dreport:"))
def cb_dreport(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id); return
    action = call.data.split(":", 1)[1]
    if action == "on":
        daily_report_cfg["enabled"] = True; _save(DAILY_REPORT_FILE, daily_report_cfg)
        bot.answer_callback_query(call.id, "✅ បើករួច")
    elif action == "off":
        daily_report_cfg["enabled"] = False; _save(DAILY_REPORT_FILE, daily_report_cfg)
        bot.answer_callback_query(call.id, "🔴 បិទរួច")
    elif action == "hour":
        bot.answer_callback_query(call.id)
        waiting[uid] = "await_dreport_hour"
        bot.send_message(uid, "⏰ ផ្ញើម៉ោង (0-23) ដែលចង់ឲ្យផ្ញើ Daily Report (ម៉ោងកម្ពុជា):",
                          reply_markup=cancel_kb())
        return
    elif action == "test":
        bot.answer_callback_query(call.id, "📤 កំពុងផ្ញើ...")
        txt = (f"⏰ <b>Daily Report (សាកល្បង)</b>\n━━━━━━━━━━━━━━━━━━\n\n"
               + _profit_report_text() + "\n\n" + _top_report_text(7))
        bot.send_message(uid, txt, parse_mode="HTML")
        return
    try:
        bot.edit_message_text(
            f"⏰ <b>Daily Report Auto</b>\nស្ថានភាព: {'🟢 បើក' if daily_report_cfg.get('enabled', True) else '🔴 បិទ'}\n"
            f"ម៉ោងផ្ញើ: {daily_report_cfg.get('hour', 8):02d}:00 (ម៉ោងកម្ពុជា)\n\n"
            f"Bot នឹងផ្ញើ 📈 ចំណេញ + 🏆 Top Services/Clients មកអ្នកដោយស្វ័យប្រវត្តិរាល់ថ្ងៃ។",
            chat_id=uid, message_id=call.message.message_id,
            parse_mode="HTML", reply_markup=daily_report_kb())
    except Exception as _e:
        logger.debug(f"[silent] {_e}")


    """/dailyreport on|off|<hour 0-23> — គ្រប់គ្រង Auto Daily Report"""
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        state = "🟢 បើក" if daily_report_cfg.get("enabled", True) else "🔴 បិទ"
        bot.reply_to(message,
            f"⏰ <b>Daily Report Auto-Send</b>\n"
            f"ស្ថានភាព: {state}\n"
            f"ម៉ោងផ្ញើ: {daily_report_cfg.get('hour', 8):02d}:00 (ម៉ោងកម្ពុជា)\n\n"
            f"ប្រើ: <code>/dailyreport on</code> ឬ <code>off</code> ឬ <code>/dailyreport 9</code> (ប្តូរម៉ោង)",
            parse_mode="HTML")
        return
    arg = parts[1].lower()
    if arg == "on":
        daily_report_cfg["enabled"] = True
        _save(DAILY_REPORT_FILE, daily_report_cfg)
        bot.reply_to(message, "✅ បើក Daily Report ស្វ័យប្រវត្តិហើយ។")
    elif arg == "off":
        daily_report_cfg["enabled"] = False
        _save(DAILY_REPORT_FILE, daily_report_cfg)
        bot.reply_to(message, "🔴 បិទ Daily Report ស្វ័យប្រវត្តិហើយ។")
    elif arg.isdigit() and 0 <= int(arg) <= 23:
        daily_report_cfg["hour"] = int(arg)
        _save(DAILY_REPORT_FILE, daily_report_cfg)
        bot.reply_to(message, f"⏰ កំណត់ម៉ោងផ្ញើ Daily Report ទៅ {int(arg):02d}:00 (ម៉ោងកម្ពុជា) ជោគជ័យ។")
    else:
        bot.reply_to(message, "❌ ប្រើ: /dailyreport on | off | <ម៉ោង 0-23>")


def cmd_top(message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    days = 30
    if len(parts) > 1 and parts[1].isdigit():
        days = int(parts[1])
    bot.reply_to(message, _top_report_text(days), parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
#  BACKUP / RESTORE DATA — សម្រាប់ផ្ទេរទៅ Server ថ្មី ដោយមិនបាត់ data
#  (users, wallets, orders, services, emoji, config ។ល។ — គ្រប់ file
#  JSON ក្នុង DATA_DIR)
# ═══════════════════════════════════════════════════════════
@bot.message_handler(commands=["backup"])
def cmd_backup(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_chat_action(ADMIN_ID, "upload_document")
    try:
        files = [f for f in os.listdir(DATA_DIR) if f.endswith(".json")]
        if not files:
            bot.reply_to(message, "❌ រកមិនឃើញ file .json ណាមួយក្នុង DATA_DIR ទេ។")
            return
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(os.path.join(DATA_DIR, f), arcname=f)
        buf.seek(0)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        buf.name = f"kaijaklike_backup_{ts}.zip"
        bot.send_document(ADMIN_ID, buf,
            caption=f"💾 <b>Backup ទិន្នន័យ</b> — {len(files)} files\n"
                    f"🗓️ {ts}\n\n"
                    f"👉 រក្សាទុក file នេះឲ្យបានល្អ។ ដើម្បីយកទៅប្រើលើ Server ថ្មី "
                    f"ផ្ញើ file នេះមកវិញ ព្រម <code>/restore</code>",
            parse_mode="HTML")
    except Exception as e:
        logger.error(f"[backup] {e}")
        bot.reply_to(message, f"❌ Backup បរាជ័យ: {e}")

@bot.message_handler(commands=["restore"])
def cmd_restore(message):
    if message.from_user.id != ADMIN_ID:
        return
    waiting[ADMIN_ID] = "await_restore_zip"
    bot.reply_to(message,
        "📥 <b>Restore ទិន្នន័យ</b>\n"
        "សូម Forward ឬផ្ញើ file <code>.zip</code> backup មកទីនេះ (ចេញពី /backup)។\n\n"
        "⚠️ <b>ប្រុងប្រយ័ត្ន:</b> នេះនឹង <u>សរសេរជាន់ពី</u> data បច្ចុប្បន្នទាំងអស់ "
        "(users, wallets, orders...) ។ ធ្វើ /backup ទុកជាមុនសិន បើអ្នកមិនប្រាកដ។",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.message_handler(content_types=["document"])
def handle_document(message):
    uid = message.chat.id
    if uid != ADMIN_ID:
        return
    step = waiting.get(uid)
    if step != "await_restore_zip":
        return
    doc = message.document
    if not (doc.file_name or "").lower().endswith(".zip"):
        bot.send_message(uid, "❌ ត្រូវជា file .zip ប៉ុណ្ណោះ។ ផ្ញើម្តងទៀត ឬ ✕ Cancel។",
                          reply_markup=cancel_kb())
        return
    try:
        file_info = bot.get_file(doc.file_id)
        raw = bot.download_file(file_info.file_path)
        buf = io.BytesIO(raw)
        with zipfile.ZipFile(buf, "r") as zf:
            names = [n for n in zf.namelist() if n.endswith(".json") and "/" not in n and ".." not in n]
            if not names:
                bot.send_message(uid, "❌ រកមិនឃើញ file .json ក្នុង zip នេះទេ។ ផ្ញើម្តងទៀត ឬ ✕ Cancel។",
                                  reply_markup=cancel_kb())
                return
            # ចម្លងទុកមុនសិន (safety backup) មុននឹងសរសេរជាន់
            safety_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_dir = _dpath(f"_pre_restore_backup_{safety_ts}")
            os.makedirs(safety_dir, exist_ok=True)
            for f in os.listdir(DATA_DIR):
                if f.endswith(".json"):
                    try:
                        import shutil as _shutil
                        _shutil.copy(os.path.join(DATA_DIR, f), os.path.join(safety_dir, f))
                    except Exception: pass
            for n in names:
                zf.extract(n, DATA_DIR)
        waiting.pop(uid, None)
        bot.send_message(uid,
            f"✅ <b>Restore ជោគជ័យ!</b> ({len(names)} files)\n"
            f"🛡️ Data ចាស់បានចម្លងទុកនៅ <code>{os.path.basename(safety_dir)}</code> ជាមុនសិន (ការពារបញ្ហា)\n\n"
            f"🔄 <b>កំពុង Restart Bot ស្វ័យប្រវត្តិ...</b> (ត្រូវការ ដើម្បីអោយ Data ថ្មីចូល RAM — "
            f"គ្រាន់តែសរសេរជាន់ file មិនគ្រប់គ្រាន់ទេ)។ រង់ចាំ ~5 វិនាទី រួចសាកល្បង /start វិញ។",
            parse_mode="HTML")
        def _auto_restart():
            time.sleep(1.5)
            try: bot.stop_polling()
            except Exception: pass
            time.sleep(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        threading.Thread(target=_auto_restart, daemon=True).start()
        return
    except zipfile.BadZipFile:
        bot.send_message(uid, "❌ File នេះមិនមែនជា zip ត្រឹមត្រូវទេ។ ផ្ញើម្តងទៀត ឬ ✕ Cancel។",
                          reply_markup=cancel_kb())
    except Exception as e:
        logger.error(f"[restore] {e}")
        bot.send_message(uid, f"❌ Restore បរាជ័យ: {e}", reply_markup=admin_kb())

def _smm_api_post(params, timeout=25):
    url = smm_api.get("url", "")
    if not url: return None
    try:
        r = http.post(url, data=params, timeout=timeout)
        return r.json()
    except Exception as e:
        logger.error(f"SMM API: {e}"); return None

def _smm_api_status(api_order_id):
    """ពិនិត្យស្ថានភាព Order ដែលបានដាក់តាម SMM API (action=status)"""
    key = smm_api.get("key", ""); url = smm_api.get("url", "")
    if not key or not url or not api_order_id: return None
    try:
        r = http.post(url, data={"key": key, "action": "status", "order": api_order_id}, timeout=25)
        return r.json()
    except Exception as e:
        logger.error(f"SMM API status: {e}"); return None

def _smm_sync_order(oid):
    """🔄 ត្រួតពិនិត្យ + Sync ស្ថានភាព Order មួយពី Supplier API ភ្លាមៗ (Live) —
    ប្រើទាំងដោយ Background Watcher (Poll ទៀងទាត់) និងដោយ User ខ្លួនឯងពេលចុច
    🔍 Track Order (ដើម្បីទទួលបានស្ថានភាព Live មិនចាំបាច់រង់ចាំ Poll Cycle បន្ទាប់)។
    ត្រឡប់ status ថ្មីបំផុតរបស់ Order (str)។ គ្មានផលប៉ះពាល់ទេបើ Order មិនមែន
    'pending' ឬគ្មាន api_order_id (Manual order) — ត្រឡប់ status បច្ចុប្បន្នវិញ។"""
    o = smm_orders.get(oid)
    if not o: return None
    if o.get("status") != "pending": return o.get("status")
    api_oid = o.get("api_order_id")
    if not api_oid: return o.get("status")
    res = _smm_api_status(api_oid)
    if not res or not isinstance(res, dict): return o.get("status")
    st = str(res.get("status", "")).strip().lower()
    if st == "completed":
        smm_orders[oid]["status"]  = "completed"
        smm_orders[oid]["remains"] = res.get("remains", 0)
        _save(SMM_ORD_FILE, smm_orders)
        try:
            bot.send_message(int(o["uid"]),
                f"✅ <b>Order បានជោគជ័យគ្រប់ចំនួន 100%!</b> 🎉\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"📊 {o.get('label','?')}\n"
                f"🔢 ចំនួន: <b>{o.get('qty',0):,}</b>\n"
                f"🔗 <code>{o.get('link','')}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🙏 អរគុណដែលប្រើ {_bot_brand()}!",
                parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        try:
            bot.send_message(ADMIN_ID,
                f"✅ <b>Order បានគ្រប់ចំនួន 100%!</b>\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 {_user_display(o.get('uid',''))}\n"
                f"📦 {o.get('label','?')}\n"
                f"🔢 {o.get('qty',0):,} | 💰 ${float(o.get('price',0)):.4f}\n"
                f"🔗 <code>{o.get('link','')}</code>",
                parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        return "completed"
    elif st in ("canceled", "cancelled"):
        smm_orders[oid]["status"] = "canceled"
        price = float(o.get("price") or 0)
        smm_orders[oid]["refunded"] = price
        _save(SMM_ORD_FILE, smm_orders)
        # Refund ស្វ័យប្រវត្តិ — ដាច់ដោយឡែកពី Notify, ដើម្បីកុំឲ្យ User ខាតលុយបើផ្ញើសារទៅគាត់មិនចេញ
        add_bal(int(o["uid"]), price)
        try:
            bot.send_message(int(o["uid"]),
                f"⚠️ <b>Order ត្រូវបានលុបចោល (Canceled)</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"📊 {o.get('label','?')}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 លុយត្រូវបានសងវិញ: <b>${price:.4f}</b>\n"
                f"💳 Balance: <b>${bal(int(o['uid'])):.2f}</b>\n"
                f"🙏 សូមអភ័យទោសចំពោះការរអាក់រអួល!",
                parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        try:
            bot.send_message(ADMIN_ID,
                f"⚠️ <b>Order ត្រូវបានលុបចោល (Auto-Refunded)</b>\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 {_user_display(o.get('uid',''))}\n"
                f"📊 {o.get('label','?')} | {o.get('qty',0):,} | ${price:.4f}\n"
                f"🔗 <code>{o.get('link','')}</code>\n"
                f"💰 លុយបានសងវិញស្វ័យប្រវត្តិទៅ User",
                parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        return "canceled"
    elif st == "partial":
        # Supplier បានប្រគល់ខ្លះ ប៉ុន្តែមិនគ្រប់ចំនួន → សងលុយវិញសម្រាប់ចំនួនដែលមិនបានប្រគល់ (remains)
        remains  = float(res.get("remains", 0) or 0)
        qty_orig = float(o.get("qty", 0) or 0)
        price    = float(o.get("price") or 0)
        refund   = round(price * remains / qty_orig, 4) if qty_orig > 0 and remains > 0 else 0.0
        delivered = int(qty_orig - remains) if qty_orig else 0
        smm_orders[oid]["status"]   = "partial"
        smm_orders[oid]["remains"]  = remains
        smm_orders[oid]["refunded"] = refund
        _save(SMM_ORD_FILE, smm_orders)
        if refund > 0:
            add_bal(int(o["uid"]), refund)
        try:
            bot.send_message(int(o["uid"]),
                f"⚠️ <b>Order ប្រគល់មិនគ្រប់ចំនួន (Partial)</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"📊 {o.get('label','?')}\n"
                f"✅ បានប្រគល់: <b>{delivered:,}</b> / {int(qty_orig):,}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                + (f"💰 លុយត្រូវបានសងវិញ: <b>${refund:.4f}</b>\n"
                   f"💳 Balance: <b>${bal(int(o['uid'])):.2f}</b>\n" if refund > 0 else "")
                + f"🙏 សូមអភ័យទោសចំពោះការរអាក់រអួល!",
                parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        try:
            bot.send_message(ADMIN_ID,
                f"⚠️ <b>Order ប្រគល់មិនគ្រប់ (Partial, Auto-Refunded)</b>\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 {_user_display(o.get('uid',''))}\n"
                f"📊 {o.get('label','?')} | ប្រគល់ {delivered:,}/{int(qty_orig):,}\n"
                f"🔗 <code>{o.get('link','')}</code>\n"
                f"💰 សងវិញ: ${refund:.4f}",
                parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        return "partial"
    return o.get("status")

def _smm_order_watcher():
    """ 🕑 Background thread — Poll ស្ថានភាព Order ដែលដាក់ស្វ័យប្រវត្តិតាម API ជាទៀងទាត់
    ដោយហៅ _smm_sync_order() សម្រាប់ Order pending នីមួយៗ។
    Order ដែលជា Manual (គ្មាន api_order_id) មិនត្រូវបាន Poll ទេ — Admin ត្រូវ Mark Done ដោយផ្ទាល់។"""
    while True:
        try:
            time.sleep(SMM_ORDER_POLL_INTERVAL)
            for oid, o in list(smm_orders.items()):
                if o.get("status") != "pending": continue
                if not o.get("api_order_id"): continue
                _smm_sync_order(oid)
        except Exception as e:
            logger.error(f"[order_watcher] {e}")

def _smm_fetch_service(api_id):
    key = smm_api.get("key", "")
    url = smm_api.get("url", "")
    if not key or not url:
        logger.error("SMM API: url or key not set")
        return None
    try:
        r = http.post(url, data={"key": key, "action": "services"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("error"):
            logger.error(f"SMM API error: {data['error']}")
            return None
        for s in data:
            if str(s.get("service")) == str(api_id):
                # API panels use "rate" as cost per 1000, some use "min" fallback
                rate = s.get("rate") or s.get("price") or s.get("cost") or "0"
                return {
                    "cost_rate": str(rate),
                    "min":       max(1, int(float(s.get("min") or 10))),
                    "max":       int(float(s.get("max") or 100000)),
                    "raw_name":  s.get("name") or s.get("Name") or str(api_id),
                }
        logger.error(f"SMM API: service {api_id} not found in list")
    except Exception as e:
        logger.error(f"Fetch service {api_id}: {e}")
    return None

def _smm_clean_name(raw):
    raw = re.sub(r'\s*\[.*?\]\s*', ' ', raw)
    raw = re.sub(r'\s*\(.*?\)\s*', ' ', raw)
    return re.sub(r'\s+', ' ', raw).strip()[:60]

def _smm_service_list_text():
    if not smm_services: return "❌ គ្មាន Service ទេ"
    lines = ["<b>📋 SMM Services</b>\n━━━━━━━━━━━━━━━━━━"]
    for cat in _smm_get_categories():
        lines.append(f"\n📂 <b>{cat}</b>")
        for slug, s in _smm_get_svcs_in_cat(cat):
            sr = _smm_sell_rate(s["cost_rate"], slug)
            lines.append(f"  • {s.get('label',slug)} — ${sr:.2f}/1K")
    return "\n".join(lines)

# ── Hardcoded notify channel — always works ──
NOTIFY_CHANNEL_ID_DEFAULT = -1003930705105

def _notify(msg):
    """Send message to notify channel — always use hardcoded ID"""
    cid = NOTIFY_CHANNEL_ID_DEFAULT
    # Override with file/env if admin changed it
    try:
        cfg = _load(NOTIFY_FILE, {})
        saved_cid = cfg.get("channel_id", "")
        if saved_cid:
            cid = int(saved_cid)
    except Exception as _e:
        logger.debug(f"[silent] {_e}")
    try:
        bot.send_message(cid, msg, parse_mode="HTML")
        logger.info(f"[notify] sent to {cid}")
    except Exception as e:
        logger.warning(f"[notify] failed cid={cid} err={e}")

def _send_deposit_notify(uid, amount, bonus, new_bal):
    msg = (
        f"💰 <b>ដាក់លុយ ថ្មី!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 User ID: <code>{uid}</code>\n"
        f"💵 បានទទួល: <b>${amount:.2f}</b>\n"
    )
    if bonus > 0:
        msg += f"🎟️ Bonus: <b>+${bonus:.2f}</b>\n"
    msg += (
        f"💳 Balance ថ្មី: <b>${new_bal:.2f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    _notify(msg)

def _get_notify_cfg():
    cfg = _load(NOTIFY_FILE, {})
    if not cfg.get("channel_id"):
        cfg = {"channel_id": str(NOTIFY_CHANNEL_ID_DEFAULT), "enabled": True}
    cfg["enabled"] = True
    return cfg

def _make_order_id():
    return f"KZ{int(time.time())%100000:05d}"

def _user_display(uid_str):
    """បង្កើតឈ្មោះ + username បង្ហាញឲ្យ Admin មើលងាយ (ជំនួសមើលតែលេខ UID
    ដែលមិនអាចដឹងថាជានរណា)។ ត្រឡប់ ឧ. "Sokha (@sokha123)" ឬ fallback ត្រឹមតែ
    UID បើគ្មានទិន្នន័យ User។"""
    u = users_db.get(str(uid_str), {})
    name = (u.get("name") or "").strip()
    uname = u.get("username") or ""
    parts = []
    if name:
        parts.append(name)
    if uname:
        parts.append(f"@{uname}")
    if parts:
        return " ".join(parts) + f" (<code>{uid_str}</code>)"
    return f"<code>{uid_str}</code>"

# ═══════════════════════════════════════════════════════════
#  KHQR CARD GENERATOR  (Bakong-style branded card)
# ═══════════════════════════════════════════════════════════
_CARD_NAVY      = (5, 59, 47)       # deep emerald (header / headline text)
_CARD_NAVY2     = (3, 33, 30)       # deeper teal (header gradient bottom)
_CARD_RED       = (217, 45, 32)
_CARD_WHITE     = (255, 255, 255)
_CARD_SUBTITLE  = (170, 221, 199)   # mint (header subtitle)
_CARD_GRAY      = (100, 116, 109)
_CARD_MUTED     = (145, 152, 148)
_CARD_BORDER    = (224, 231, 227)
_CARD_GOLD      = (201, 162, 39)
_CARD_VIOLET    = (6, 95, 70)       # emerald accent (panel border / pill outline)
_CARD_PANEL     = (247, 250, 249)
_CARD_CHIP_BG   = (234, 250, 244)   # pale mint chip background

_FONT_REG = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/system/fonts/Roboto-Regular.ttf",
    "/data/data/com.termux/files/usr/share/fonts/DejaVuSans.ttf",
]
_FONT_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/system/fonts/Roboto-Bold.ttf",
    "/data/data/com.termux/files/usr/share/fonts/DejaVuSans-Bold.ttf",
]

def _card_font(size, bold=False):
    for path in (_FONT_BOLD if bold else _FONT_REG):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default(size=size)

def _tw(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)[2]

def _cx_text(draw, cx, y, text, font, fill):
    draw.text((cx - _tw(draw, text, font) / 2, y), text, font=font, fill=fill)

def _vgrad(draw, box, top_color, bottom_color):
    x0, y0, x1, y1 = box
    h = max(1, y1 - y0)
    for i in range(h):
        t = i / h
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.line([(x0, y0 + i), (x1, y0 + i)], fill=(r, g, b))

def _qr_matrix(data):
    try:
        import qrcode as _qrcode
        qr = _qrcode.QRCode(border=0, error_correction=_qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(data); qr.make(fit=True)
        m = qr.get_matrix()
        return np.array([[0 if c else 255 for c in row] for row in m], dtype=np.uint8)
    except Exception as e:
        raise RuntimeError(f"qrcode lib error: {e}")

def _qr_img(data, box_px):
    matrix = _qr_matrix(data)
    n = matrix.shape[0]
    mod = max(1, box_px // n)
    img = Image.new("RGB", (mod * n, mod * n), _CARD_PANEL)
    draw = ImageDraw.Draw(img)
    for ry in range(n):
        for rx in range(n):
            if matrix[ry, rx] == 0:
                x0, y0 = rx * mod, ry * mod
                draw.rectangle([x0, y0, x0 + mod - 1, y0 + mod - 1], fill=_CARD_NAVY)
    return img.resize((box_px, box_px), Image.LANCZOS)

def _pill_box(draw, cx, y, text, font, pad_x, pad_y, fill, outline=None, outline_w=2,
              text_fill=_CARD_NAVY):
    """Draw a centered, auto-width rounded pill with text. Returns pill height."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw_, th_ = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pill_h = th_ + 2 * pad_y
    pill_w = tw_ + 2 * pad_x
    box = [cx - pill_w / 2, y, cx + pill_w / 2, y + pill_h]
    draw.rounded_rectangle(box, radius=pill_h / 2, fill=fill,
                            outline=outline, width=outline_w if outline else 0)
    draw.text((cx - tw_ / 2 - bbox[0], y + pad_y - bbox[1]), text, font=font, fill=text_fill)
    return pill_h

def _build_qr_image(qr_string, amount=None, ref=None, label=None, subtitle=None,
                    expires_min=None, width=720):
    """Generate branded KHQR 'ticket' card → BytesIO (PNG). Falls back to plain QR on error."""
    if expires_min is None:
        expires_min = max(1, round(DEPOSIT_EXPIRE_SEC / 60))
    try:
        W = width
        HEADER_H = int(W * 0.30)
        SIDE_PAD = int(W * 0.13)
        QR_BOX   = W - 2 * SIDE_PAD
        QR_PAD   = int(QR_BOX * 0.09)
        OVERLAP  = int(W * 0.10)

        f_title = _card_font(int(W * 0.052), bold=True)
        f_sub   = _card_font(int(W * 0.026))
        f_name  = _card_font(int(W * 0.042), bold=True)
        f_label = _card_font(int(W * 0.024))
        f_amt   = _card_font(int(W * 0.062), bold=True)
        f_small = _card_font(int(W * 0.0205))
        f_badge = _card_font(int(W * 0.0195), bold=True)

        qr_card_top    = HEADER_H - OVERLAP
        qr_card_bottom = qr_card_top + QR_BOX
        content_top    = qr_card_bottom + int(W * 0.05)

        # Row heights (shared between H calc and the draw walk, kept in sync)
        NAME_ROW  = int(W * 0.065)
        SUB_ROW   = int(W * 0.045)
        GAP1      = int(W * 0.020)
        AMT_H     = int(f_amt.size * 1.55)
        GAP2      = int(W * 0.030)
        PERF_ROW  = int(W * 0.045)
        CHIP_H    = int(f_small.size * 1.9)
        CHIP_GAP  = int(W * 0.022)
        EXP_ROW   = int(W * 0.032)
        FOOT_ROW1 = int(W * 0.030)
        FOOT_ROW2 = int(W * 0.030)
        BOTTOM_PAD = int(W * 0.05)

        H = (content_top + NAME_ROW + SUB_ROW + GAP1 + AMT_H + GAP2 + PERF_ROW
             + CHIP_H + CHIP_GAP + EXP_ROW + FOOT_ROW1 + FOOT_ROW2 + BOTTOM_PAD)

        img  = Image.new("RGB", (W, H), _CARD_WHITE)
        draw = ImageDraw.Draw(img)
        cx   = W // 2
        pad  = int(W * 0.06)

        # 1. Gradient header (deep emerald → teal)
        _vgrad(draw, [0, 0, W, HEADER_H], _CARD_NAVY, _CARD_NAVY2)

        # Decorative rings — kept fully inside the header so no stray arcs bleed
        # into the body below (the previous ring's radius overshot HEADER_H)
        for rr, rw in ((int(W*0.16), 1), (int(W*0.10), 1)):
            ring_cx, ring_cy = W - int(W * 0.04), int(W * 0.045)
            draw.ellipse([ring_cx - rr, ring_cy - rr, ring_cx + rr, ring_cy + rr],
                         outline=(24, 84, 68), width=rw)

        draw.text((pad, int(W * 0.045)), "KHQR", font=f_title, fill=_CARD_WHITE)
        draw.text((pad, int(W * 0.045) + f_title.size + int(W * 0.010)),
                  "Cambodian QR Payment · Bakong", font=f_sub, fill=_CARD_SUBTITLE)
        rule_y = int(W * 0.045) + f_title.size + int(W * 0.010) + f_sub.size + int(W * 0.018)
        draw.line([(pad, rule_y), (pad + int(W * 0.14), rule_y)], fill=_CARD_GOLD, width=2)

        # Gold "verified" badge
        badge_txt = "✓ VERIFIED"
        bw = _tw(draw, badge_txt, f_badge)
        bpad_x, bpad_y = int(W * 0.020), int(W * 0.011)
        bx1 = W - pad
        bx0 = bx1 - bw - bpad_x * 2
        by0 = int(W * 0.045)
        by1 = by0 + f_badge.size + bpad_y * 2
        shadow_d = max(2, int(W * 0.006))
        draw.rounded_rectangle([bx0+shadow_d, by0+shadow_d, bx1+shadow_d, by1+shadow_d],
                                radius=(by1 - by0) // 2, fill=(2, 20, 16))
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=(by1 - by0) // 2, fill=_CARD_GOLD)
        draw.text((bx0 + bpad_x, by0 + bpad_y - int(W * 0.003)), badge_txt, font=f_badge, fill=_CARD_NAVY)

        # 2. Floating QR panel — thin gold border + emerald corner dots (instead of brackets)
        r = int(W * 0.045)
        panel_box = [SIDE_PAD, qr_card_top, SIDE_PAD + QR_BOX, qr_card_bottom]
        shadow_off = int(W * 0.012)
        draw.rounded_rectangle(
            [panel_box[0] + shadow_off, panel_box[1] + shadow_off,
             panel_box[2] + shadow_off, panel_box[3] + shadow_off],
            radius=r, fill=(222, 230, 226))
        draw.rounded_rectangle(panel_box, radius=r, fill=_CARD_WHITE,
                                outline=_CARD_GOLD, width=3)

        qr_px  = QR_BOX - 2 * QR_PAD
        qr_pil = _qr_img(qr_string, qr_px)
        img.paste(qr_pil, (SIDE_PAD + QR_PAD, qr_card_top + QR_PAD))

        # Small emerald corner dots — pushed fully past the rounded-corner arc
        # (r) so they render as clean circles instead of being clipped by it
        dot_r = max(3, int(W * 0.007))
        do = r + int(W * 0.012)
        x0, y0, x1, y1 = panel_box
        for dx, dy in [(x0+do, y0+do), (x1-do, y0+do), (x0+do, y1-do), (x1-do, y1-do)]:
            draw.ellipse([dx-dot_r, dy-dot_r, dx+dot_r, dy+dot_r], fill=_CARD_VIOLET)

        # 3. Store name + subtitle
        y = content_top
        _cx_text(draw, cx, y, label or _bot_brand(), f_name, _CARD_NAVY)
        y += NAME_ROW
        _cx_text(draw, cx, y, subtitle or "SMM Panel Deposit", f_label, _CARD_GRAY)
        y += SUB_ROW + GAP1

        # 4. Amount — gold-bordered floating pill (not a full-width banner)
        if amount is not None:
            amt_str = f"${float(amount):.2f}"
            pad_x = int(W * 0.045)
            pad_y = (AMT_H - f_amt.size) // 2
            _pill_box(draw, cx, y, amt_str, f_amt, pad_x, pad_y,
                      fill=_CARD_CHIP_BG, outline=_CARD_GOLD, outline_w=3,
                      text_fill=_CARD_NAVY)
        y += AMT_H + GAP2

        # 5. Ticket perforation — dashed tear line with two gold end-dots
        perf_y = y + PERF_ROW // 2
        dash_w, dash_gap = int(W * 0.018), int(W * 0.012)
        dx = pad + int(W * 0.03)
        while dx < W - pad - int(W * 0.03):
            draw.line([(dx, perf_y), (min(dx + dash_w, W - pad - int(W*0.03)), perf_y)],
                      fill=_CARD_BORDER, width=2)
            dx += dash_w + dash_gap
        end_r = max(3, int(W * 0.008))
        draw.ellipse([pad-end_r, perf_y-end_r, pad+end_r, perf_y+end_r], fill=_CARD_GOLD)
        draw.ellipse([W-pad-end_r, perf_y-end_r, W-pad+end_r, perf_y+end_r], fill=_CARD_GOLD)
        y += PERF_ROW

        # 6. Ref chip
        if ref:
            _pill_box(draw, cx, y, f"Ref: {ref}", f_small,
                      int(W * 0.03), int(f_small.size * 0.45),
                      fill=_CARD_CHIP_BG, text_fill=_CARD_GRAY)
        y += CHIP_H + CHIP_GAP

        # 7. Expiry (red, plain — draws the eye without another box)
        if expires_min:
            _cx_text(draw, cx, y, f"Expires in {expires_min} minutes", f_small, _CARD_RED)
        y += EXP_ROW

        # 8. Footer
        _cx_text(draw, cx, y, "Scan with any Bakong-member app", f_small, _CARD_MUTED)
        y += FOOT_ROW1
        _cx_text(draw, cx, y, "ABA · ACLEDA · Wing", f_small, _CARD_MUTED)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0); buf.name = "khqr_card.png"
        return buf

    except Exception as e:
        logger.warning(f"[build_qr_image] {e}")
        try:
            import qrcode as _qrc
            qr = _qrc.QRCode(box_size=8, border=2,
                             error_correction=_qrc.constants.ERROR_CORRECT_M)
            qr.add_data(qr_string); qr.make(fit=True)
            pil = qr.make_image(fill_color=(5, 59, 47), back_color="white").convert("RGB")
            buf = io.BytesIO(); pil.save(buf, format="PNG")
            buf.seek(0); buf.name = "khqr.png"
            return buf
        except:
            return None

# ═══════════════════════════════════════════════════════════
#  CAMRAPIDPAY — Create KHQR + Check payment
#  (v9: replace manual EMV TLV with CamRapidPay API)
# ═══════════════════════════════════════════════════════════

def _effective_webhook_url():
    """CamRapidPay ទាមទារ webhook_url ជា Required Field (បញ្ជាក់ដោយ API ផ្ទាល់៖
    'Missing required fields: ... webhook_url ...') ដូច្នេះត្រូវផ្ញើជានិច្ច។
    អាទិភាព៖ 1) webhook_cfg (Set ដោយផ្ទាល់ក្នុង Bot តាម Admin Menu)  2) WEBHOOK_URL env var
    3) Auto-build ពី RENDER_EXTERNAL_URL ទៅកាន់ Route /webhook/camrapid ដែល Bot ស្គាល់ស្រាប់
    4) Fallback ចុងក្រោយ (គ្មាន Public URL ទាល់តែសោះ) — Placeholder ដែលមិន Leak អី"""
    if webhook_cfg.get("url"):
        return webhook_cfg["url"]
    if WEBHOOK_URL:
        return WEBHOOK_URL
    render_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if render_url:
        return render_url.rstrip("/") + "/webhook/camrapid"
    return "https://example.com/webhook/camrapid"

def _camrapid_create(uid, amount, reference):
    """Create KHQR payment via CamRapidPay API — returns response dict or None"""
    payload = {
        "api_key":     _effective_camrapid_key(),
        "amount":      round(float(amount), 2),
        "reference":   reference,
        "webhook_url": _effective_webhook_url(),
    }

    logger.info(f"[camrapid_create] uid={uid} ref={reference} amount={payload['amount']} "
                f"webhook={payload['webhook_url']}")
    try:
        r = http.post(CAMRAPID_CREATE,
                      json=payload,
                      headers={"Content-Type": "application/json",
                               "Accept": "application/json"},
                      timeout=15)
        logger.info(f"[camrapid_create] HTTP {r.status_code}")
        data = r.json()
        logger.info(f"[camrapid_create] resp={data}")
        if data.get("success"):
            return data   # keys: qr_code, payment_url, bill_number, amount, expires_in
        logger.error(f"[camrapid_create] failed: {data}")
        return None
    except Exception as e:
        logger.error(f"[camrapid_create] exception: {e}")
        return None

def _camrapid_check(reference) -> bool:
    """Check payment status via CamRapidPay API — returns True if paid"""
    try:
        r = http.get(
            CAMRAPID_CHECK,
            params={"api_key": _effective_camrapid_key(), "reference": reference},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        data = r.json()
        logger.info(f"[camrapid_check] ref={reference} resp={data}")
        return data.get("success") and data.get("status") in ("Success", "success", "PAID", "paid")
    except Exception as e:
        logger.error(f"[camrapid_check] {e}")
        return False

# ═══════════════════════════════════════════════════════════
#  ABA PAYWAY (តាម KHMER SYSTEM — khmer-system.com) — ជម្រើសទូទាត់ស្វ័យប្រវត្តិទី ២
#  (v12: ស្របជាមួយ CamRapidPay ដែលមានស្រាប់ខាងលើ — ២ Gateway ដំណើរការឯករាជ្យពីគ្នា)
# ═══════════════════════════════════════════════════════════
_last_aba_error = ""

def has_aba_payway():
    """True បើ Bot នេះមាន ABA PayWay auto-payment តាម KHMER SYSTEM (Key + Merchant ID ព្រមទាំង ២)"""
    return bool(_effective_aba_key() and _effective_aba_merchant())

def _aba_create(uid, amount, username, _attempt=1):
    """Create ABA PayWay payment (KHMER SYSTEM) — returns response dict ពេលជោគជ័យ
    (keys ប្រហែល: payment_id, qr_image/card_image, pay_url, qr_string...), ឬ None ពេលបរាជ័យ
    (មើល _last_aba_error សម្រាប់មូលហេតុ)"""
    global _last_aba_error
    api_key      = _effective_aba_key()
    merchant_id  = _effective_aba_merchant()
    if not api_key or not merchant_id:
        _last_aba_error = "ABA_API_KEY / ABA_MERCHANT_ID មិនបានកំណត់ (env var ឬ Settings → ABA PayWay Key)"
        logger.error(f"[aba_create] {_last_aba_error}")
        return None
    try:
        r = http.post(
            ABA_CREATE_URL,
            json={
                "api_key":     api_key,
                "merchant_id": merchant_id,
                "username":    username,
                "amount":      round(float(amount), 2),
            },
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=20,
        )
        logger.info(f"[aba_create] uid={uid} HTTP {r.status_code}")
        try:
            data = r.json()
        except Exception:
            body = r.text.strip()
            _last_aba_error = f"HTTP {r.status_code} (non-JSON): {body[:300]}"
            logger.error(f"[aba_create] {_last_aba_error}")
            if r.status_code >= 500 and _attempt < 2:
                time.sleep(1.5)
                return _aba_create(uid, amount, username, _attempt=2)
            return None
        logger.info(f"[aba_create] resp={data}")
        if data.get("ok"):
            return data
        _last_aba_error = f"HTTP {r.status_code} [{data.get('code', '?')}]: {data.get('message') or data}"
        logger.error(f"[aba_create] failed: {_last_aba_error}")
        if r.status_code >= 500 and _attempt < 2:
            time.sleep(1.5)
            return _aba_create(uid, amount, username, _attempt=2)
        return None
    except Exception as e:
        _last_aba_error = f"{type(e).__name__}: {e}"
        logger.error(f"[aba_create] exception: {e}")
        if _attempt < 2:
            time.sleep(1.5)
            return _aba_create(uid, amount, username, _attempt=2)
        return None

def _aba_check(payment_id) -> bool:
    """Check ABA PayWay (KHMER SYSTEM) payment status — returns True if PAID"""
    try:
        r = http.post(
            ABA_CHECK_URL,
            json={"api_key": _effective_aba_key(), "merchant_id": _effective_aba_merchant(),
                  "payment_id": payment_id},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=10,
        )
        data = r.json()
        logger.info(f"[aba_check] payment_id={payment_id} resp={data}")
        return bool(data.get("ok")) and str(data.get("status", "")).upper() == "PAID"
    except Exception as e:
        logger.error(f"[aba_check] {e}")
        return False

def _build_aba_app_deeplink(data):
    """បើ response ពី khmer-system.com មាន field deeplink ត្រង់ៗ ត្រឡប់វាភ្លាម។ បើគ្មាន
    ប៉ុន្តែមាន raw KHQR string ត្រូវបង្កើត deep link ដោយខ្លួនឯង តាម scheme ផ្លូវការរបស់
    ABA Mobile (abamobilebank://ababank.com?type=payway&qrcode=...) ។ ត្រឡប់ None បើគ្មាន field
    ណាមួយសមរម្យទេ។"""
    if not isinstance(data, dict):
        return None
    for key in ("abapay_deeplink", "aba_deeplink", "deeplink", "deep_link"):
        val = data.get(key)
        if val and str(val).strip():
            return str(val).strip()
    qr_raw = None
    for key in ("qr_string", "qrString", "qr_code", "qrCode", "qr"):
        val = data.get(key)
        if val and str(val).strip():
            qr_raw = str(val).strip()
            break
    if qr_raw:
        from urllib.parse import quote
        return f"abamobilebank://ababank.com?type=payway&qrcode={quote(qr_raw, safe='')}"
    logger.warning(f"[aba_deeplink] គ្មាន deeplink/qr_string field ក្នុង response — keys: {list(data.keys())}")
    return None

def _bakong_deeplink(qr_str, uid=None):
    """
    ហៅ Bakong Open API (NBC) ដើម្បីបំលែង KHQR string → Deep Link មួយ
    ដែលបើក App ធនាគារបានស្វ័យប្រវត្តិ (ABA, ACLEDA, Bakong, Wing, Chip Mong ...) —
    អ្នកប្រើគ្រាន់តែចុច button ម្តង App ធនាគាររបស់ខ្លួននឹងបើក ព្រមទាំង pre-fill ការទូទាត់។
    ត្រូវការ BAKONG_API_TOKEN (Bakong Developer Token) កំណត់ជា Environment Variable។
    """
    tok = _effective_bakong_token()
    if not tok or not qr_str:
        return None
    try:
        r = http.post(
            BAKONG_DEEPLINK_API,
            json={
                "qr": qr_str,
                "sourceInfo": {
                    "appIconUrl": "https://raw.githubusercontent.com/sovannarinsorn-droid/assets/main/kairozen_logo.png",
                    "appName": BOT_DISPLAY_NAME or "KaiJakLike",
                    "appDeepLinkCallback": f"https://t.me/{_bot_username()}",
                },
            },
            headers={
                "Authorization": f"Bearer {tok}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            },
            timeout=10,
        )
        data = r.json()
        logger.info(f"[bakong_deeplink] uid={uid} HTTP={r.status_code} resp={data}")
        if data.get("responseCode") == 0:
            d = data.get("data") or {}
            return d.get("shortLink") or d.get("deeplink") or d.get("dl")
        logger.warning(f"[bakong_deeplink] failed: {data}")
        return None
    except Exception as e:
        logger.warning(f"[bakong_deeplink] exception: {e}")
        return None

def _watch_deposit(uid, uid_str, dep_id, amount, reference, checker=None):
    """Poll payment gateway until paid or expired (5 min). `checker` ជា function ទទួល
    reference/payment_id → True/False ថាបានទូទាត់ហើយឬនៅ — default ជា CamRapidPay (backward
    compatible), ប្ដូរជា _aba_check ពេលហៅសម្រាប់ ABA PayWay deposit (v12)."""
    checker = checker or _camrapid_check
    deadline = time.time() + DEPOSIT_EXPIRE_SEC + 30
    while time.time() < deadline:
        dep = smm_deps.get(dep_id)
        if not dep or dep.get("status") != "pending": return
        if checker(reference):
            bonus       = float(dep.get("bonus") or 0)
            promo_bonus = float(dep.get("promo_bonus") or 0)
            auto_bonus  = float(dep.get("auto_bonus") or 0)
            total = round(amount + bonus, 2)
            add_bal(uid, total)
            smm_deps[dep_id]["status"] = "confirmed"
            _save(SMM_DEP_FILE, smm_deps)
            if dep.get("promo") and promo_bonus > 0:
                confirm_promo(dep["promo"], uid)
            new_b = bal(uid)
            msg = (f"✅ <b>ដាក់លុយបានជោគជ័យហើយ!</b> 🎉\n"
                   f"━━━━━━━━━━━━━━━━━━\n"
                   f"💰 បានទទួល: <b>${amount:.2f}</b>")
            if promo_bonus > 0:
                msg += f"\n🎟️ Promo Bonus: <b>+${promo_bonus:.2f}</b>"
            if auto_bonus > 0:
                msg += f"\n🎁 Auto Bonus: <b>+${auto_bonus:.2f}</b>"
            msg += f"\n💳 Balance: <b>${new_b:.2f}</b>\n━━━━━━━━━━━━━━━━━━\n💙 អរគុណដែលប្រើ {_bot_brand()}!"
            try: bot.send_message(uid, msg, parse_mode="HTML", reply_markup=main_kb(uid))
            except Exception as _e: logger.debug(f"[silent] {_e}")
            try:
                bot.send_message(ADMIN_ID,
                    f"💰 <b>ដាក់លុយ ✅</b>\n👤 <code>{uid_str}</code>\n"
                    f"📌 Ref: <code>{reference}</code>\n"
                    f"💰 ${amount:.2f}" + (f" + Bonus ${bonus:.2f}" if bonus > 0 else "") +
                    (f" (Promo ${promo_bonus:.2f} / Auto ${auto_bonus:.2f})" if (promo_bonus > 0 and auto_bonus > 0) else ""),
                    parse_mode="HTML")
            except Exception as _e: logger.debug(f"[silent] {_e}")
            # Notify channel — call _notify directly to avoid any config issues
            try:
                dep_msg = (
                    f"💰 <b>ដាក់លុយ ថ្មី!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 User ID: <code>{uid}</code>\n"
                    f"💵 បានទទួល: <b>${amount:.2f}</b>\n"
                )
                if bonus > 0:
                    dep_msg += f"🎟️ Bonus: <b>+${bonus:.2f}</b>\n"
                dep_msg += f"💳 Balance ថ្មី: <b>${new_b:.2f}</b>\n━━━━━━━━━━━━━━━━━━"
                bot.send_message(NOTIFY_CHANNEL_ID_DEFAULT, dep_msg, parse_mode="HTML")
                logger.info(f"[deposit_notify] sent uid={uid} amount={amount}")
            except Exception as e:
                logger.warning(f"[deposit_notify] failed: {e}")
            return
        time.sleep(POLL_INTERVAL)
    dep = smm_deps.get(dep_id)
    if dep and dep.get("status") == "pending":
        dep["status"] = "expired"; _save(SMM_DEP_FILE, smm_deps)
        try: bot.send_message(uid, "⏰ <b>QR ផុតកំណត់!</b> សូម top up ម្តងទៀត", parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")

def _dep_created_ts(dep_id, dep):
    """ត្រឡប់ created timestamp របស់ deposit មួយ — ប្រើ field 'created_ts' បើមាន
    (deposit ថ្មីៗ), បើអត់ (deposit ចាស់មុន update នេះ) fallback ទៅ parse ពី
    dep_id ខ្លួនឯង (format: dep_{uid}_{unix_ts})។"""
    ts = dep.get("created_ts")
    if ts:
        return float(ts)
    try:
        return float(dep_id.rsplit("_", 1)[-1])
    except Exception:
        return 0.0

def _active_pending_deposit(uid):
    """បើ User មាន QR deposit ដែលកំពុង 'pending' ហើយមិនទាន់ផុតកំណត់ (5 នាទី)
    សូមត្រឡប់ (dep, remain_sec) មកវិញ — បើគ្មាន ត្រឡប់ (None, 0)។ ប្រើដើម្បីទប់
    User មិនឲ្យបង្កើត QR ថ្មីម្តងទៀត ព្រោះ QR ចាស់ (5 នាទី) នៅតែសកម្ម — ត្រូវឲ្យ
    QR នោះផុតកំណត់ (ឬបានទូទាត់ជោគជ័យ) សិន ទើបបង្កើតបានថ្មីទៀត។"""
    uid_str = str(uid)
    now = time.time()
    for dep_id, dep in smm_deps.items():
        if dep.get("uid") != uid_str or dep.get("status") != "pending":
            continue
        elapsed = now - _dep_created_ts(dep_id, dep)
        remain  = DEPOSIT_EXPIRE_SEC - elapsed
        if remain > 0:
            return dep, int(remain) + 1
    return None, 0

def _send_deposit_qr(uid, amount, promo_code=None, label="💸 ដាក់លុយ", bonus=0.0, promo_code_name=None,
                      promo_bonus=0.0, auto_bonus=0.0, method="camrapid"):
    """Create payment QR → send branded QR card to user.
    method="camrapid" (default — ដដែលពីមុន, backward-compatible) ឬ method="aba"
    (ABA PayWay តាម KHMER SYSTEM — v12, មិនប៉ះពាល់ code path CamRapidPay ខាងក្រោមទេ)"""
    # ── ទប់ស្កាត់ User មិនឲ្យបង្កើត QR ថ្មី ដរាបណា QR ចាស់ (5 នាទី) មិនទាន់ផុត
    #    កំណត់ — ការពារកុំឲ្យមាន QR pending ច្រើនក្នុងពេលតែមួយសម្រាប់ User តែម្នាក់
    #    (Admin មិនកំណត់ ដើម្បីងាយ Test) ──
    if str(uid) != str(ADMIN_ID):
        _dep, _remain = _active_pending_deposit(uid)
        if _dep:
            _mins, _secs = divmod(_remain, 60)
            _remain_txt = f"{_mins} នាទី {_secs} វិនាទី" if _mins else f"{_secs} វិនាទី"
            bot.send_message(uid,
                f"⏳ <b>អ្នកមាន QR ដែលកំពុងរង់ចាំទូទាត់ស្រាប់ហើយ!</b>\n"
                f"សូមប្រើ QR នោះ ឬស្កេនវាដើម្បីទូទាត់ជាមុនសិន។\n"
                f"បើមិនចង់ប្រើទៀត សូមរង់ចាំ <b>{_remain_txt}</b> ដល់ QR ចាស់ផុតកំណត់ "
                f"ទើបអាចបង្កើតថ្មីម្តងទៀតបាន។",
                parse_mode="HTML")
            return

    # ── Anti-Spam Cooldown — ការពារ User ចុចបង្កើត QR ជាប់ៗគ្នា (spam) ដែលនាំឲ្យ
    #    ហៅ CamRapidPay/ABA API ច្រើនដងឥតប្រយោជន៍ ។ Admin (ADMIN_ID) មិនកំណត់ ដើម្បីងាយ Test ។
    _cd_key = str(uid)
    if _cd_key != str(ADMIN_ID):
        _cd_sec  = int(dep_qr_cooldown_cfg.get("seconds", DEP_QR_COOLDOWN_SEC))
        _now_ts  = time.time()
        _last_ts = _dep_qr_cooldown.get(_cd_key, 0)
        _elapsed = _now_ts - _last_ts
        if _cd_sec > 0 and _elapsed < _cd_sec:
            _remain = int(_cd_sec - _elapsed) + 1
            bot.send_message(uid,
                f"⏳ <b>សូមរង់ចាំ {_remain} វិនាទី</b> មុននឹងបង្កើត QR ថ្មីម្តងទៀត។\n"
                f"បើ QR មុនទើបតែផ្ញើ សូមប្រើវានោះ ឬស្កេនវាដើម្បីទូទាត់។",
                parse_mode="HTML")
            return
        _dep_qr_cooldown[_cd_key] = _now_ts

    if method == "aba":
        _send_deposit_qr_aba(uid, amount, promo_code_name=promo_code_name, bonus=bonus,
                              promo_bonus=promo_bonus, auto_bonus=auto_bonus)
        return

    uid_str       = str(uid)
    promo_applied = promo_code_name
    reference     = f"KZ{uid}_{int(time.time())}"[:50]

    # ── ជូនដំណឹង User ថាកំពុងបង្កើត QR (CamRapidPay API អាចចំណាយពេលបន្តិច) ──
    _gen_msg = None
    try:
        _gen_msg = bot.send_message(uid, "⏳ <b>កំពុងបង្កើត QR...</b>\nសូមរង់ចាំបន្តិច",
                                    parse_mode="HTML")
    except Exception as _e: logger.debug(f"[silent] {_e}")

    # Call CamRapidPay API to create KHQR
    resp = _camrapid_create(uid, amount, reference)
    if not resp:
        if _gen_msg:
            try: bot.delete_message(uid, _gen_msg.message_id)
            except Exception as _e: logger.debug(f"[silent] {_e}")
        bot.send_message(uid, "⚠️ <b>មានបញ្ហា Generate QR!</b>\nសូមព្យាយាមម្តងទៀត ឬ ទំនាក់ Admin",
                         parse_mode="HTML")
        return

    qr_str      = resp.get("qr_code", "")
    payment_url = resp.get("payment_url", "")

    dep_id = f"dep_{uid}_{int(time.time())}"
    smm_deps[dep_id] = {
        "uid":         uid_str,
        "amount":      amount,
        "status":      "pending",
        "bonus":       bonus,
        "promo_bonus": promo_bonus,
        "auto_bonus":  auto_bonus,
        "promo":       promo_applied or "",
        "reference":   reference,
        "payment_url": payment_url,
        "created_ts":  time.time(),
    }
    _save(SMM_DEP_FILE, smm_deps)

    # ចំណាំ: Promo Code មិន confirm_promo() (consume) នៅទីនេះទេ — រង់ចាំរហូតដល់ Payment
    # ពិតជាបានបញ្ជាក់ (_watch_deposit / Admin manual confirm) ដើម្បីកុំឲ្យ User ខាត Promo Code
    # ដោយឥតបានការ បើ QR ផុតកំណត់ ឬ User មិនបានបង់ប្រាក់ជាដុំ។

    # Caption text (shown below card photo)
    ref_short = reference[-12:] if len(reference) > 12 else reference
    bonus_bits = []
    if promo_bonus > 0:
        bonus_bits.append(f"🎟️ Promo Bonus: <b>+${promo_bonus:.2f}</b> ({promo_applied})")
    if auto_bonus > 0:
        bonus_bits.append(f"🎁 Auto Bonus ({dep_bonus_cfg.get('pct',5):.0f}%): <b>+${auto_bonus:.2f}</b>")
    bonus_line = ("\n" + "\n".join(bonus_bits)) if bonus_bits else ""
    cap = (f"💸 <b>SMM Panel — បញ្ចូលលុយ</b>{bonus_line}\n"
           f"💰 Amount: <b>${amount:.2f}</b>\n"
           f"🔖 Ref: <code>{ref_short}</code>\n"
           f"⏱ Expires in: <b>5 minutes</b>\n"
           f"✅ <i>ប្រព័ន្ធ auto-detect — Balance update ភ្លាមៗ!</i>")

    # Generate branded KHQR card
    img_buf = None
    if qr_str:
        img_buf = _build_qr_image(
            qr_str,
            amount=amount,
            ref=ref_short,
            label="SMM TOPUP",
            subtitle="SMM Panel Deposit · ដាក់លុយ",
        )

    # ── ផ្ញើ QR ភ្លាមៗសិន (កុំឲ្យ deposit យឺត ដោយរង់ចាំ Bakong deeplink API) ──
    if _gen_msg:
        try: bot.delete_message(uid, _gen_msg.message_id)
        except Exception as _e: logger.debug(f"[silent] {_e}")
    if img_buf:
        try:
            sent_msg = bot.send_photo(uid, img_buf, caption=cap, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"[deposit_qr] send_photo failed: {e}")
            sent_msg = bot.send_message(uid, cap, parse_mode="HTML")
    else:
        sent_msg = bot.send_message(uid, cap, parse_mode="HTML")

    # ── Deep Link button ចូល App ធនាគារស្វ័យប្រវត្តិ — ធ្វើនៅ background thread
    #    ដើម្បីកុំឲ្យរង់ចាំ Bakong API (រហូតដល់ 10s) ធ្វើឲ្យ QR ចេញយឺត/មិនចេញ ──
    def _attach_bank_button():
        try:
            dlink = _bakong_deeplink(qr_str, uid) if qr_str else None
            if not dlink:
                return
            kb_pay = InlineKeyboardMarkup()
            kb_pay.add(InlineKeyboardButton("🏦 ស្កេន QR ឬ ចុចបើក App ធនាគារ", url=dlink, color="active"))
            new_cap = cap + ("\n📱 <i>ចុច button ខាងក្រោម ដើម្បីបើក App ធនាគារ auto-scan។ "
                              "បើមិនចូល App ស្វ័យប្រវត្តិទេ សូមចុច ••• (ជ្រុងស្តាំលើ ក្នុង browser) → 'បើកក្នុង Safari'</i>")
            if img_buf:
                bot.edit_message_caption(new_cap, chat_id=uid, message_id=sent_msg.message_id,
                                         parse_mode="HTML", reply_markup=kb_pay)
            else:
                bot.edit_message_text(new_cap, chat_id=uid, message_id=sent_msg.message_id,
                                      parse_mode="HTML", reply_markup=kb_pay)
        except Exception as e:
            logger.warning(f"[deposit_qr] attach_bank_button failed: {e}")

    threading.Thread(target=_attach_bank_button, daemon=True).start()

    threading.Thread(target=_watch_deposit,
                     args=(uid, uid_str, dep_id, amount, reference), daemon=True).start()

def _send_deposit_qr_aba(uid, amount, promo_code_name=None, bonus=0.0, promo_bonus=0.0, auto_bonus=0.0):
    """Create payment via ABA PayWay (KHMER SYSTEM) → send QR/card image ដែល khmer-system.com
    បង្កើតរួចជាស្រេច (v12) — ខុសពី CamRapidPay ត្រង់ khmer-system.com ត្រឡប់ card_image
    (base64 ឬ URL) ដោយផ្ទាល់ ជាជាងឲ្យ bot ខ្លួនឯង render ពី raw KHQR string ។"""
    uid_str       = str(uid)
    promo_applied = promo_code_name
    username      = users_db.get(uid_str, {}).get("username") or f"tg{uid}"

    # ── ជូនដំណឹង User ថាកំពុងបង្កើត QR (ABA PayWay / khmer-system.com អាចចំណាយពេលបន្តិច) ──
    _gen_msg = None
    try:
        _gen_msg = bot.send_message(uid, "⏳ <b>កំពុងបង្កើត QR...</b>\nសូមរង់ចាំបន្តិច",
                                    parse_mode="HTML")
    except Exception as _e: logger.debug(f"[silent] {_e}")

    data = _aba_create(uid, amount, username)
    if not data:
        if _gen_msg:
            try: bot.delete_message(uid, _gen_msg.message_id)
            except Exception as _e: logger.debug(f"[silent] {_e}")
        bot.send_message(uid, "⚠️ <b>មានបញ្ហា Generate QR (ABA PayWay)!</b>\nសូមព្យាយាមម្តងទៀត ឬ ទំនាក់ Admin",
                         parse_mode="HTML")
        try:
            bot.send_message(ADMIN_ID,
                f"⚠️ <b>ABA PayWay បរាជ័យ (aba_generate_qr)</b>\n👤 <code>{uid_str}</code> — ${amount:.2f}\n"
                f"🔎 <code>{_last_aba_error[:500]}</code>", parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        return

    payment_id   = data.get("payment_id", "")
    card_image   = data.get("card_image") or data.get("qr_image")
    pay_url      = data.get("pay_url")
    aba_app_link = _build_aba_app_deeplink(data)

    dep_id = f"dep_{uid}_{int(time.time())}"
    reference = payment_id or f"ABA{uid}_{int(time.time())}"[:50]
    smm_deps[dep_id] = {
        "uid":         uid_str,
        "amount":      amount,
        "status":      "pending",
        "bonus":       bonus,
        "promo_bonus": promo_bonus,
        "auto_bonus":  auto_bonus,
        "promo":       promo_applied or "",
        "reference":   reference,
        "payment_url": pay_url or "",
        "method":      "aba",
        "created_ts":  time.time(),
    }
    _save(SMM_DEP_FILE, smm_deps)

    ref_short = reference[-12:] if len(reference) > 12 else reference
    bonus_bits = []
    if promo_bonus > 0:
        bonus_bits.append(f"🎟️ Promo Bonus: <b>+${promo_bonus:.2f}</b> ({promo_applied})")
    if auto_bonus > 0:
        bonus_bits.append(f"🎁 Auto Bonus ({dep_bonus_cfg.get('pct',5):.0f}%): <b>+${auto_bonus:.2f}</b>")
    bonus_line = ("\n" + "\n".join(bonus_bits)) if bonus_bits else ""
    cap = (f"💸 <b>SMM Panel — បញ្ចូលលុយ</b>{bonus_line}\n"
           f"💳 វិធីទូទាត់: <b>ABA PayWay</b>\n"
           f"💰 Amount: <b>${amount:.2f}</b>\n"
           f"🔖 Ref: <code>{ref_short}</code>\n"
           f"⏱ Expires in: <b>5 minutes</b>\n"
           f"✅ <i>ប្រព័ន្ធ auto-detect — Balance update ភ្លាមៗ!</i>")

    # ⚠️ Telegram Bot API only accepts http(s):// or tg:// URLs on inline-button `url`
    # fields — custom app schemes like abamobilebank:// are rejected outright with
    # "Bad Request: ... Unsupported URL protocol", which crashes the whole send here.
    # So _build_aba_app_deeplink()'s custom-scheme fallback is only usable for a button
    # when khmer-system.com happens to return an http(s) wrapper link; otherwise we
    # silently drop the button (the QR image/pay_url are still enough for the user).
    aba_btn_link = aba_app_link if (aba_app_link and aba_app_link.lower().startswith(("http://", "https://", "tg://"))) else None

    kb_pay = None
    if aba_btn_link or pay_url:
        kb_pay = InlineKeyboardMarkup()
        if aba_btn_link:
            kb_pay.add(InlineKeyboardButton("🏦 បើក ABA App ស្កេនស្វ័យប្រវត្តិ", url=aba_btn_link, color="active"))
        if pay_url:
            kb_pay.add(InlineKeyboardButton("🌐 បើកទំព័រទូទាត់", url=pay_url, color="progress"))

    # khmer-system.com ត្រឡប់ card_image ជា http(s) URL ធម្មតា ឬ base64 string (មានពេលមាន
    # prefix "data:image/...;base64," មានពេលគ្មាន) — ត្រូវ decode ជា raw bytes មុននឹងផ្ញើ
    # ដើម្បីកុំឲ្យ Telegram បដិសេធជា "MESSAGE_TOO_LONG" ពេល string វែងពេក។
    photo_payload = None
    if card_image:
        img_str = str(card_image).strip()
        if img_str.lower().startswith(("http://", "https://")):
            photo_payload = img_str
        else:
            try:
                b64_part = img_str.split(",", 1)[1] if img_str.startswith("data:") else img_str
                photo_payload = io.BytesIO(base64.b64decode(b64_part, validate=False))
                photo_payload.name = "aba_payment.png"
            except Exception as e:
                logger.warning(f"[deposit_qr_aba] base64 decode failed: {e}")
                photo_payload = None

    if _gen_msg:
        try: bot.delete_message(uid, _gen_msg.message_id)
        except Exception as _e: logger.debug(f"[silent] {_e}")

    sent_ok = False
    if photo_payload:
        try:
            bot.send_photo(uid, photo_payload, caption=cap, parse_mode="HTML", reply_markup=kb_pay)
            sent_ok = True
        except Exception as e:
            logger.warning(f"[deposit_qr_aba] send_photo failed: {e}")
    if not sent_ok:
        bot.send_message(uid, cap, parse_mode="HTML", reply_markup=kb_pay)

    if not payment_id:
        bot.send_message(uid, "⚠️ <b>ABA PayWay មិនបាន Return payment_id!</b>\nសូមទំនាក់ Admin ជូនវិក័យប័ត្រផ្ទាល់",
                         parse_mode="HTML")
        return

    try:
        bot.send_message(ADMIN_ID,
            f"🆕 <b>QR ត្រូវបានបង្កើត (ABA PayWay)</b>\n👤 <code>{uid_str}</code>\n"
            f"💵 ${amount:.2f}\n🔖 <code>{payment_id}</code>", parse_mode="HTML")
    except Exception as _e: logger.debug(f"[silent] {_e}")

    threading.Thread(target=_watch_deposit,
                     args=(uid, uid_str, dep_id, amount, reference),
                     kwargs={"checker": _aba_check}, daemon=True).start()

def _get_dep_promo(uid):
    step = waiting.get(uid)
    if isinstance(step, dict):
        return step.get("promo")
    return None

_pending_dep_choice = {}   # uid -> {"amount":..., "promo_code":...} — រង់ចាំ user ជ្រើស Payment Method (v12)

def _process_deposit(uid, uid_str, amount, promo_code=None, method=None):
    """method=None → decide ស្វ័យប្រវត្តិ: បើមានទាំង CamRapidPay + ABA PayWay ព្រមគ្នា (Key
    កំណត់រួច ព្រមទាំង admin មិនទាន់បិទតាម 🔀 វិធីទូទាត់) ឲ្យ user ជ្រើសរើសមុន (picker) ；
    បើមានតែមួយ ប្រើវិធីនោះភ្លាម；  បើគ្មានវិធីណាមួយប្រើបាន ជូនដំណឹង user + admin ។ (v12/v13)"""
    camrapid_ok = bool(_effective_camrapid_key()) and is_pay_method_enabled("camrapid")
    aba_ok      = has_aba_payway() and is_pay_method_enabled("aba")
    if method is None:
        if camrapid_ok and aba_ok:
            _pending_dep_choice[uid] = {"amount": amount, "promo_code": promo_code}
            lang = get_lang(uid)
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔄 CamRapidPay KHQR", callback_data="depm:camrapid", color="active"))
            kb.add(InlineKeyboardButton("💳 ABA PayWay", callback_data="depm:aba", color="primary"))
            bot.send_message(uid,
                f"💳 <b>{'ជ្រើសរើសវិធីទូទាត់' if lang=='kh' else 'Choose payment method'}</b> — ${amount:.2f}",
                parse_mode="HTML", reply_markup=kb)
            return
        if not camrapid_ok and not aba_ok:
            lang = get_lang(uid)
            bot.send_message(uid,
                "⚠️ <b>មិនមានវិធីទូទាត់ស្វ័យប្រវត្តិណាមួយបើកនៅពេលនេះទេ។</b>\nសូមទំនាក់ Admin ដើម្បីជំនួយ"
                if lang == "kh" else
                "⚠️ <b>No automatic payment method is available right now.</b>\nPlease contact Admin for help",
                parse_mode="HTML")
            try:
                bot.send_message(ADMIN_ID,
                    f"🚨 <b>User ព្យាយាមដាក់លុយ ${amount:.2f} តែវិធីទូទាត់ទាំងអស់ត្រូវបានបិទ/មិនទាន់កំណត់!</b>\n"
                    f"👤 <code>{uid_str}</code>\nសូមចុច 🔀 វិធីទូទាត់ ដើម្បីពិនិត្យ",
                    parse_mode="HTML")
            except Exception as _e: logger.debug(f"[silent] {_e}")
            return
        method = "aba" if aba_ok else "camrapid"

    lang  = get_lang(uid)
    promo_bonus = 0.0
    promo_applied = None
    if promo_code:
        p = promos.get(promo_code.upper())
        if p and (p.get("uses", 0) == 0 or p.get("used", 0) < p.get("uses", 0)):
            if str(uid) not in p.get("user_used", {}):
                if p.get("pct", False):
                    promo_bonus = round(amount * float(p["discount"]) / 100, 2)
                else:
                    promo_bonus = round(float(p["discount"]), 2)
                promo_applied = promo_code.upper()
    # ── Auto Deposit Bonus (stacks on top of any promo bonus) ──
    auto_bonus  = _auto_dep_bonus(amount)
    total_bonus = round(promo_bonus + auto_bonus, 2)
    _send_deposit_qr(uid, amount,
                     label=f"💸 <b>{'ដាក់លុយ' if lang=='kh' else 'Top Up'}</b>",
                     bonus=total_bonus, promo_code_name=promo_applied,
                     promo_bonus=promo_bonus, auto_bonus=auto_bonus, method=method)

@bot.callback_query_handler(func=lambda c: c.data.startswith("depm:"))
def cb_dep_method(call):
    """ចម្លើយ user ជ្រើសរើស Payment Method ពី picker ក្នុង _process_deposit (v12)"""
    uid = call.message.chat.id
    uid_str = str(uid)
    method = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)
    pending = _pending_dep_choice.pop(uid, None)
    if not pending:
        bot.send_message(uid, "⚠️ Session ផុតកំណត់ — សូមចាប់ផ្ដើមដាក់លុយម្តងទៀត")
        return
    _process_deposit(uid, uid_str, pending["amount"], pending.get("promo_code"), method=method)

@bot.callback_query_handler(func=lambda c: c.data.startswith("paytoggle:"))
def cb_paytoggle(call):
    """បិទ/បើក វិធីទូទាត់ (CamRapidPay / ABA PayWay) ពី Admin Panel — v13"""
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id, "🚫"); return
    method = call.data.split(":", 1)[1]
    if method not in PAY_METHOD_LABELS:
        bot.answer_callback_query(call.id, "❌ Unknown method"); return
    set_pay_method_enabled(method, not is_pay_method_enabled(method))
    new_state = is_pay_method_enabled(method)
    bot.answer_callback_query(call.id, f"{'🟢 បើក' if new_state else '🔴 បិទ'} {PAY_METHOD_LABELS[method]}")
    try:
        bot.edit_message_text(
            f"🔀 <b>បិទ/បើក វិធីទូទាត់</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{_paytoggle_status_lines()}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👉 ចុចប៊ូតុងខាងក្រោមដើម្បីបិទ/បើក។ បើមានទាំង ២ (Key កំណត់រួច + Toggle ON) ព្រមគ្នា "
            f"User នឹងឃើញ picker ជ្រើសរើសពេលដាក់លុយ។ បើមានតែមួយ Bot ប្រើវិធីនោះដោយស្វ័យប្រវត្តិ។",
            chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=_paytoggle_kb())
    except Exception as _e: logger.debug(f"[silent] {_e}")

# ═══════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════
def main_kb(uid=None):
    lang = get_lang(uid) if uid else "kh"
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    e = EMOJI_MAP
    if lang == "en":
        kb.row(KeyboardButton("👤 My Account", emoji_id=e.get("account"), color="active"),
               KeyboardButton("💸 Top Up",      emoji_id=e.get("topup"),   color="progress"))
        kb.row(KeyboardButton("🛒 Order Service", emoji_id=e.get("order"), color="active"))
        kb.row(KeyboardButton("📋 Order History", emoji_id=e.get("history"), color="active"),
               KeyboardButton("🔍 Track Order",   emoji_id=e.get("track"),   color="active"))
        kb.row(KeyboardButton("💬 Support", emoji_id=e.get("support"), color="active"),
               KeyboardButton("💡 How to Use",  emoji_id=e.get("💡"),      color="progress"))
    else:
        kb.row(KeyboardButton("👤 គណនី",            emoji_id=e.get("account"), color="active"),
               KeyboardButton("💸 បញ្ចូលលុយ",       emoji_id=e.get("topup"),   color="progress"))
        kb.row(KeyboardButton("🛒 បញ្ជាទិញសេវា", emoji_id=e.get("order"), color="active"))
        kb.row(KeyboardButton("📋 ប្រវត្តិការបញ្ជាទិញ", emoji_id=e.get("history"), color="active"),
               KeyboardButton("🔍 តាមដានការបញ្ជាទិញ", emoji_id=e.get("track"),   color="active"))
        kb.row(KeyboardButton("💬 ជំនួយ", emoji_id=e.get("support"), color="active"),
               KeyboardButton("💡 របៀបប្រើប្រាស់", emoji_id=e.get("💡"),  color="progress"))
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 ការបញ្ជា SMM",  color="active"),
           KeyboardButton("⚙️ កំណត់ SMM API", color="progress"))
    kb.row(KeyboardButton("➕ បន្ថែម SMM",    color="active"),
           KeyboardButton("✍️ Manual SMM",   color="active"))
    kb.row(KeyboardButton("🗑️ លុប SMM",   color="danger"),
           KeyboardButton("✏️ កែ SMM",     color="progress"))
    kb.row(KeyboardButton("📦 បន្ថែម Package", color="active"),
           KeyboardButton("💰 កែតម្លៃ",       color="progress"))
    kb.row(KeyboardButton("💹 ប្រាក់ចំណេញ SMM", color="active"),
           KeyboardButton("📋 SMM Services",    color="active"))
    kb.row(KeyboardButton("📈 របាយការណ៍ចំណេញ", color="active"),
           KeyboardButton("🏆 Top Services/Clients", color="active"))
    kb.row(KeyboardButton("⏰ Daily Report Auto", color="active"))
    kb.row(KeyboardButton("💾 Backup Data", color="active"))
    kb.row(KeyboardButton("🧾 QR ដាក់លុយដោយដៃ", color="active"))
    kb.row("━━━ 💰 ហិរញ្ញវត្ថុ ━━━")
    kb.row(KeyboardButton("💰 កាបូបលុយ",   color="active"),
           KeyboardButton("💳 ប្រាក់បញ្ញើ", color="active"))
    kb.row(KeyboardButton("💸 បន្ថែមប្រាក់", color="active"),
           KeyboardButton("💔 កាត់ប្រាក់",  color="danger"))
    kb.row(KeyboardButton("🎁 Bonus ដាក់លុយ", color="progress"))
    kb.row("━━━ 👥 អ្នកប្រើ ━━━")
    kb.row(KeyboardButton("👥 អ្នកប្រើប្រាស់", color="active"),
           KeyboardButton("📊 ស្ថិតិ",       color="active"))
    kb.row(KeyboardButton("📢 ផ្សព្វផ្សាយ", color="progress"))
    kb.row(KeyboardButton("⏱ ល្បឿន Poll",   color="progress"),
           KeyboardButton("💰 ឆែកលុយ API", color="active"))
    kb.row(KeyboardButton("🖼️ Welcome Photo", color="progress"),
           KeyboardButton("🎬 វីដេអូបង្រៀន", color="progress"))
    kb.row(KeyboardButton("🔄 ធ្វើឱ្យទាន់សម័យ", color="progress"))
    kb.row(KeyboardButton("🔔 Notify Channel", color="progress"),
           KeyboardButton("🧪 តេស្ត Notify",   color="active"))
    # ── ⚙️ Settings — Bot Clone (INSTANCE_NAME set / IS_MASTER=False) មិនបង្ហាញ
    #    ប៊ូតុងទាំងនេះទេ ព្រោះជា credential/config ដែលគ្រប់គ្រងតាមម្ចាស់ (Master Bot)
    #    តាមរយៈ /newbot wizard និង /mybots → 🔁 ប្តូរ Step ទូទាត់ / 👤 ប្តូរ Admin
    #    រួចហើយ — បើទុកឲ្យកែពី clone ខ្លួនឯងផ្ទាល់ នឹងធ្វើឲ្យ config ចាស់ក្នុង
    #    clone_registry.json (Master) មិនត្រូវគ្នានឹងតម្លៃពិតរបស់ clone ទៀត
    #    (bug ប្រភពទិន្នន័យស្ទួន — clone restart វិញនឹងទាញយកតម្លៃចាស់ពី Master មកជាន់)។
    if IS_MASTER:
        kb.row("━━━ ⚙️ Settings ━━━")
        kb.row(KeyboardButton("✏️ កែ Support",      color="progress"),
               KeyboardButton("👥 Sub Admins",      color="progress"))
        kb.row(KeyboardButton("🔑 CamRapidPay Key", color="progress"),
               KeyboardButton("💳 ABA PayWay Key", color="progress"))
        kb.row(KeyboardButton("🔀 វិធីទូទាត់", color="progress"),
               KeyboardButton("🏦 Bakong Deep Link", color="progress"))
        kb.row(KeyboardButton("⏳ QR Cooldown", color="progress"))
        kb.row(KeyboardButton("📝 Welcome Msg",     color="progress"),
               KeyboardButton("😊 កំណត់ Emoji", color="progress"))
    return kb

def emoji_menu_kb():
    """Inline menu for Premium Emoji settings (replaces /setemojis, /emojilist, /emojiid)."""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✏️ កំណត់ Emoji ថ្មី", callback_data="emojimenu:set", color="progress"))
    kb.add(InlineKeyboardButton("🔄 ប្តូរ Emoji ដែលមានស្រាប់", callback_data="emojimenu:change", color="progress"))
    kb.add(InlineKeyboardButton("📊 មើលស្ថានភាព",     callback_data="emojimenu:list", color="active"))
    kb.add(InlineKeyboardButton("🎨 មើលសាកល្បង (Preview)", callback_data="emojimenu:preview", color="active"))
    kb.add(InlineKeyboardButton("🆔 យក Emoji ID",       callback_data="emojimenu:id", color="active"))
    return kb

def missing_emoji_kb(per_row=6):
    """Inline keyboard grid — one button per NOT-YET-SET emoji. Tapping one starts a
    single-target flow: bot remembers which char was picked, admin sends/forwards the
    premium version of it, bot matches it and saves the custom_emoji_id automatically —
    no manual ID lookup needed."""
    missing = [ch for ch, v in EMOJI_MAP.items() if not v]
    btns = []
    row = []
    for ch in missing:
        row.append(InlineKeyboardButton(ch, callback_data=f"emojipick:{ch}", color="progress"))
        if len(row) == per_row:
            btns.append(row); row = []
    if row: btns.append(row)
    btns.append([InlineKeyboardButton("📋 ផ្ញើច្រើនម្តង (Advanced)", callback_data="emojimenu:setmulti", color="active")])
    btns.append([InlineKeyboardButton("🔙 ត្រឡប់ Menu", callback_data="emojimenu:menu", color="inactive")])
    return InlineKeyboardMarkup(btns)

def all_emoji_kb(per_row=6):
    """Inline keyboard grid — ALL emoji (both set និង unset), ដើម្បីឲ្យ Admin អាចជ្រើស
    Emoji ដែលកំណត់រួចហើយ មកកំណត់ (ប្តូរ) ម្តងទៀត។ ✅ = មានស្រាប់, ⬜ = មិនទាន់កំណត់។
    ប្រើ callback_data ដដែលនឹង emojipick: (Handler ដដែលមិនប្រកែកថា Set រួចហើយឬអត់)។"""
    btns = []
    row = []
    for ch, v in EMOJI_MAP.items():
        mark = "✅" if v else "⬜"
        row.append(InlineKeyboardButton(f"{mark}{ch}", callback_data=f"emojipick:{ch}",
                                         color=("active" if v else "progress")))
        if len(row) == per_row:
            btns.append(row); row = []
    if row: btns.append(row)
    btns.append([InlineKeyboardButton("🔙 ត្រឡប់ Menu", callback_data="emojimenu:menu", color="inactive")])
    return InlineKeyboardMarkup(btns)

def sub_admin_kb():
    """Keyboard for sub-admins (limited permissions)"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 ការបញ្ជា SMM", color="active"),
           KeyboardButton("💰 កាបូបលុយ",    color="active"))
    kb.row(KeyboardButton("💳 ប្រាក់បញ្ញើ",   color="active"),
           KeyboardButton("👥 អ្នកប្រើប្រាស់", color="active"))
    kb.row(KeyboardButton("💸 បន្ថែមប្រាក់", color="active"),
           KeyboardButton("💔 កាត់ប្រាក់",   color="danger"))
    kb.row(KeyboardButton("📊 ស្ថិតិ",       color="active"),
           KeyboardButton("📢 ផ្សព្វផ្សាយ", color="progress"))
    return kb

def cancel_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✕ Cancel", color="danger"))
    return kb

def _warm_stripped_text_map():
    """ហៅ .to_dict() លើ reply-keyboard ចម្បងទាំងអស់ (KH + EN) មួយដងពេល bot
    ចាប់ផ្ដើម ដើម្បីបំពេញ _STRIPPED_TEXT_MAP ជាមុន — កុំឲ្យមាន window ខ្លីៗ
    ចន្លោះពេល bot restart និងពេលផ្ញើ keyboard ថ្មីទៅ user ដែលអាចធ្វើឲ្យ
    ប៊ូតុងចាស់ (ដែល client នៅចាំ) ធ្លាក់ចូល fallback "មិនស្គាល់ button"។"""
    def _dump(kb):
        for row in kb.keyboard:
            for btn in row:
                if hasattr(btn, "to_dict"):
                    btn.to_dict()
    try:
        _dump(main_kb())                      # lang="kh" default
        user_lang["__warmup__"] = "en"
        _dump(main_kb(uid="__warmup__"))
        user_lang.pop("__warmup__", None)
        _dump(admin_kb())
        _dump(sub_admin_kb())
        _dump(cancel_kb())
    except Exception as e:
        logger.warning(f"⚠️ _warm_stripped_text_map failed: {e}")

def deposit_amt_kb(uid=None, promo_code=None):
    lang = get_lang(uid) if uid else "kh"
    # Preset amounts
    amounts = [1, 2, 5, 10, 20, 50]
    btns = []
    row = []
    for i, amt in enumerate(amounts):
        row.append(InlineKeyboardButton(f"💵 ${amt}", callback_data=f"dep:amt:{amt}", color="active"))
        if len(row) == 3:
            btns.append(row); row = []
    if row: btns.append(row)
    # Custom amount
    btns.append([InlineKeyboardButton(
        "✏️ ចំនួនផ្សេង" if lang=="kh" else "✏️ Custom Amount",
        callback_data="dep:custom", color="progress")])
    if manual_qr_cfg.get("enabled") and manual_qr_cfg.get("photo_id"):
        btns.append([InlineKeyboardButton(
            "🧾 ដាក់លុយដោយដៃ (Manual)" if lang=="kh" else "🧾 Manual Deposit",
            callback_data="dep:manual", color="active")])
    return InlineKeyboardMarkup(btns)

def smm_cat_kb():
    PLATFORM_ICONS = {
        "tiktok khmer": "🇰🇭",
        "tiktok": "🎵", "telegram": "📱", "facebook": "📘",
        "instagram": "📸", "youtube": "▶️", "twitter": "🐦",
        "x": "🐦", "threads": "🧵"
    }
    cats = _smm_get_categories()
    btns = []
    for cat in cats:
        # បើ cat ចាប់ផ្តើមដោយ emoji ស្រាប់ (ឧ. "🇰🇭 TikTok Khmer") កុំបន្ថែម icon
        # ថ្មីទៀត — ការពារ icon ស្ទួន (ឧ. 🇰🇭🇰🇭) ដែលធ្លាប់កើតឡើងពីមុន
        if _leading_emoji(cat):
            btns.append([InlineKeyboardButton(cat, callback_data=f"smmcat:{cat}", color="active")])
            continue
        icon = "📱"
        for key, ico in PLATFORM_ICONS.items():
            if key in cat.lower(): icon = ico; break
        btns.append([InlineKeyboardButton(f"{icon}  {cat}", callback_data=f"smmcat:{cat}", color="active")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:main", color="inactive")])
    return InlineKeyboardMarkup(btns)

def smm_svc_kb(cat):
    SVC_ICONS = {
        "follower":"👤","like":"❤️","view":"👁️","comment":"💬",
        "share":"🔗","save":"🔖","member":"👥","subscriber":"🔔",
        "watch":"👀","reaction":"😍",
    }
    svcs = _smm_get_svcs_in_cat(cat)
    btns = []
    for slug, s in svcs:
        label = s.get("label", slug)
        # បើ label ចាប់ផ្តើមដោយ emoji ស្រាប់ (ឧ. "🇰🇭 ❤️ 500-1K...") កុំបន្ថែម
        # icon ថ្មីទៀត — ការពារ icon ស្ទួន (ឧ. 👁️👁️) ដែលធ្លាប់កើតឡើងពីមុន
        if _leading_emoji(label):
            btns.append([InlineKeyboardButton(label, callback_data=f"smmsvc:{slug}", color="active")])
            continue
        icon = "⚡"
        for key, ico in SVC_ICONS.items():
            if key in label.lower(): icon = ico; break
        btns.append([InlineKeyboardButton(f"{icon}  {label}", callback_data=f"smmsvc:{slug}", color="active")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats", color="inactive")])
    return InlineKeyboardMarkup(btns)

def smm_qty_kb(slug, s):
    sr    = _smm_sell_rate(s["cost_rate"], slug)
    mn    = s.get("min", 10)
    mx    = s.get("max", 100000)
    label = s.get("label", slug)
    first = label.split()[0] if label else slug
    # Flat price service — only 1 option
    if s.get("flat_price"):
        flat = float(s["flat_price"])
        btns = [[InlineKeyboardButton(
            f"✅ Order — ${flat:.2f}", callback_data=f"smmqty:{slug}:1", color="active")]]
        btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats", color="inactive")])
        return InlineKeyboardMarkup(btns)
    preset = s.get("preset_qtys")
    if preset and isinstance(preset, list):
        qtys = [q for q in preset if mn <= q <= mx]
    else:
        suggestions = [100, 500, 1000, 5000, 10000, 50000]
        qtys = []
        for q in [mn] + suggestions:
            if mn <= q <= mx and q not in qtys: qtys.append(q)
            if len(qtys) >= 6: break
    btns = []
    for q in qtys:
        price = _round_price_01(sr * q / 1000)  # ត្រូវតែដូចគ្នានឹងតម្លៃពិត _smm_price_for_order()
                                                  # ដែលនឹងគិតលុយ ដើម្បីកុំឲ្យតម្លៃលើប៊ូតុងខុសពី
                                                  # តម្លៃពិតដែលគិតលុយពេលបញ្ជាទិញ (bug ចាស់)
        btns.append([InlineKeyboardButton(
            f"{q:,} {first} — ${price:.2f}", callback_data=f"smmqty:{slug}:{q}", color="active")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats", color="inactive")])
    return InlineKeyboardMarkup(btns)

# ═══════════════════════════════════════════════════════════
#  USER TRACKING
# ═══════════════════════════════════════════════════════════
def _track_user(message):
    uid = message.chat.id
    uid_str = str(uid)
    u = message.from_user
    users_db[uid_str] = {
        "name":     u.first_name or "",
        "username": u.username or "",
        "last":     int(time.time()),
        "banned":   users_db.get(uid_str, {}).get("banned", False),
    }
    _save(USERS_FILE, users_db)
    wallets.setdefault(uid_str, 0.0)

def is_banned(uid):
    return bool(users_db.get(str(uid), {}).get("banned", False))

# ═══════════════════════════════════════════════════════════
#  ADMIN PROMO HELPERS
# ═══════════════════════════════════════════════════════════
def _show_promos(uid):
    if not promos:
        bot.send_message(uid, "🎟️ <b>គ្មាន Promo Code ទេ</b>", parse_mode="HTML",
                         reply_markup=admin_kb()); return
    lines = ["🎟️ <b>Promo Codes</b>\n━━━━━━━━━━━━━━━━━━"]
    for code, p in promos.items():
        dtype = f"{p['discount']:.0f}%" if p.get("pct") else f"${float(p.get('discount',0)):.2f}"
        lines.append(f"• <code>{code}</code> — {dtype} | {p.get('used',0)}/{p.get('uses',0)} used")
    bot.send_message(uid, "\n".join(lines), parse_mode="HTML")

def _utf16_slice(text, offset, length):
    """ស្រង់ substring ត្រឹមត្រូវតាម UTF-16 code units (របៀបដែល Telegram
    គិត offset/length របស់ MessageEntity — សម្រាប់ភាសាមានតួអក្សរក្រៅ BMP
    ដូច emoji, ការគណនាតាម Python string index ធម្មតាមិនត្រឹមត្រូវទេ)."""
    u = text.encode("utf-16-le")
    return u[offset * 2: (offset + length) * 2].decode("utf-16-le", errors="ignore")

def _extract_custom_emoji(src):
    """ត្រឡប់ list of (underlying_unicode_char, custom_emoji_id) ពីសារមួយ —
    underlying_unicode_char គឺជា emoji placeholder ដែលនៅពីក្រោម premium icon
    (Telegram រក្សាទុកជានិច្ច ទោះបីជាបង្ហាញ icon ផ្សេង)."""
    text = src.text or src.caption or ""
    entities = list(src.entities or []) + list(src.caption_entities or [])
    out = []
    for e in entities:
        if getattr(e, "type", None) != "custom_emoji":
            continue
        ch = _utf16_slice(text, e.offset, e.length)
        if ch:
            out.append((ch, str(e.custom_emoji_id)))
    # ── ក៏ចាប់យក Premium Emoji ដែលផ្ញើមកជា "Sticker" ដោយផ្ទាល់ (content_type=
    # "sticker") ផងដែរ — ករណីនេះកើតឡើងញឹកញាប់ ពេលអ្នកប្រើផ្ញើ custom emoji
    # តែម្នាក់ឯងពី emoji panel ដោយមិនវាយជាអក្សរ ឬ Forward វា ដោយខ្លួនវាមិនមែន
    # text entity ទេ តែជា sticker.type == "custom_emoji" វិញ។ បើមិនចាប់ករណីនេះ
    # ទេ សារនោះនឹងធ្លាក់ចូល content_type ដែលគ្មាន handler ណាដោះស្រាយសោះ —
    # បណ្តាលឲ្យ Bot ស្ងាត់ស្ងៀមទាំងស្រុង គ្មាន reply អ្វីទាំងអស់។
    sticker = getattr(src, "sticker", None)
    if sticker is not None and getattr(sticker, "type", None) == "custom_emoji" \
            and getattr(sticker, "custom_emoji_id", None):
        ch = sticker.emoji or ""
        if ch:
            out.append((ch, str(sticker.custom_emoji_id)))
    return out

def _norm_vs(s):
    """ដក Variation Selector-16 (U+FE0F) ចេញ សម្រាប់ធៀបធៀប emoji ដោយអត់ខ្ជិលរឹង —
    Telegram ពេលខ្លះត្រឡប់ underlying char ដោយគ្មាន VS16 ខណៈ EMOJI_MAP key មាន
    VS16 (ឬផ្ទុយមកវិញ), ធ្វើឲ្យការធៀប == ត្រង់ៗពីមុន ខុសទាំងដែលអ្នកប្រើជ្រើសត្រូវ
    emoji ត្រឹមត្រូវ (bug ដើម្បីនាំឲ្យបង្ហាញ 'Emoji មិនត្រូវគ្នា!' ខុសឆ្គង)។"""
    return (s or "").replace("\ufe0f", "")

def _emoji_key_lookup(ch):
    """រក key ពិតប្រាកដក្នុង EMOJI_MAP ដែលត្រូវនឹង ch ដោយអត់ខ្ជិលរឹងចំពោះ VS16។
    ត្រឡប់ None បើរកមិនឃើញសោះ។"""
    if ch in EMOJI_MAP:
        return ch
    norm = _norm_vs(ch)
    for k in EMOJI_MAP:
        if _norm_vs(k) == norm:
            return k
    return None

# ═══════════════════════════════════════════════════════════
#  PREMIUM EMOJI ID FINDER (admin-only utility)
#  Reply command នេះទៅសារដែលមាន premium emoji — bot បង្ហាញទាំង custom_emoji_id
#  និង unicode character ដើមដែលនៅពីក្រោម icon នីមួយៗ (មានប្រយោជន៍ដើម្បីដឹងថា
#  emoji character មួយណានៅក្នុង EMOJI_MAP ដែលនឹងត្រូវផ្គូផ្គង)។
# ═══════════════════════════════════════════════════════════
def _emojiid_text(src_msg):
    """Build the Custom Emoji ID report for a message. Returns None if none found."""
    found = _extract_custom_emoji(src_msg)
    if not found:
        return None
    lines = ["🆔 <b>Custom Emoji ID(s):</b>"]
    for i, (ch, eid) in enumerate(found, 1):
        known = "✅ មានក្នុង EMOJI_MAP" if ch in EMOJI_MAP else "⚠️ មិននៅក្នុង EMOJI_MAP"
        lines.append(f"{i}. {ch} → <code>{eid}</code> ({known})")
    return "\n".join(lines)

@bot.message_handler(commands=["emojiid"])
def cmd_emojiid(message):
    if message.from_user.id != ADMIN_ID:
        return
    src = message.reply_to_message
    if not src:
        bot.reply_to(message, "សូម Reply command នេះទៅសារដែលមាន premium emoji ជាមុនសិន។")
        return
    report = _emojiid_text(src)
    if not report:
        bot.reply_to(message, "❌ រកមិនឃើញ premium/custom emoji ក្នុងសារនោះទេ។")
        return
    bot.reply_to(message, report, parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
#  PREMIUM EMOJI AUTO-SET (admin-only) — លំដាប់ណាក៏បាន, ចាំបាច់មិនត្រូវ
#  ផ្ញើម្តងទាំងអស់ទេ (អាចធ្វើម្តងមួយៗ ឬច្រើនដងតគ្នា) ។ Reply command នេះទៅសារ
#  ណាមួយដែលមាន premium emoji — bot នឹងផ្គូផ្គង emoji ធម្មតាដែលនៅក្រោម icon
#  នីមួយៗ ទៅនឹង custom_emoji_id ស្វ័យប្រវត្តិ (មិនអាស្រ័យលំដាប់) រួច save ជា
#  អចិន្ត្រៃយ៍ទៅ EMOJI_MAP។ ធ្វើម្តងទៀតបានគ្រប់ពេលដើម្បីបន្ថែម/កែ emoji ថ្មី។
# ═══════════════════════════════════════════════════════════
def _apply_setemojis(src_msg):
    """Extract premium emoji from src_msg, apply to EMOJI_MAP, save. Returns report text, or None if no emoji found."""
    found = _extract_custom_emoji(src_msg)
    if not found:
        return None
    lines = ["✅ <b>បានកំណត់ Emoji ដោយស្វ័យប្រវត្តិ:</b>\n"]
    unknown = []
    for ch, eid in found:
        key = _emoji_key_lookup(ch)   # ✅ ធៀបដោយអត់ខ្ជិលរឹង VS16 (មុននេះ `ch in EMOJI_MAP`
                                       # ត្រង់ៗ ធ្វើឲ្យខកខានផ្គូផ្គង emoji ត្រឹមត្រូវ)
        if key:
            EMOJI_MAP[key] = eid
            lines.append(f"{key} → <code>{eid}</code>")
        else:
            unknown.append((ch, eid))
    _save(EMOJI_FILE, EMOJI_MAP)

    if unknown:
        lines.append(f"\n⚠️ {len(unknown)} emoji មិននៅក្នុងបញ្ជីស្គាល់ (បន្ថែមក្នុង EMOJI_MAP ដោយដៃបើត្រូវការ):")
        for ch, eid in unknown:
            lines.append(f"  {ch} → <code>{eid}</code>")

    remaining = sum(1 for v in EMOJI_MAP.values() if not v)
    lines.append(f"\n📊 សរុប: {sum(1 for v in EMOJI_MAP.values() if v)}/{len(EMOJI_MAP)} កំណត់រួច — នៅសល់ {remaining}")
    lines.append("🔄 Restart bot (/restart) ដើម្បីឲ្យប្រើប្រាស់ពេញលេញគ្រប់កន្លែង។")
    return "\n".join(lines)

@bot.message_handler(commands=["setemojis"])
def cmd_setemojis(message):
    if message.from_user.id != ADMIN_ID:
        return
    src = message.reply_to_message
    if not src:
        missing = [ch for ch, v in EMOJI_MAP.items() if not v]
        bot.reply_to(message,
            "សូម Reply command នេះទៅសារដែលមាន Premium Emoji (លំដាប់ណាក៏បាន, "
            "ចំនួនប៉ុន្មានក៏បាន — ធ្វើម្តងច្រើនដងក៏បាន)។\n\n"
            f"📊 កំណត់រួចហើយ: {sum(1 for v in EMOJI_MAP.values() if v)}/{len(EMOJI_MAP)}\n"
            f"នៅសល់ {len(missing)} emoji។ ប្រើ /emojilist ដើម្បីមើលបញ្ជីទាំងអស់។",
            parse_mode="HTML")
        return
    report = _apply_setemojis(src)
    if not report:
        bot.reply_to(message, "❌ រកមិនឃើញ premium/custom emoji ក្នុងសារនោះទេ។")
        return
    bot.reply_to(message, report, parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
#  PREMIUM EMOJI STATUS (admin-only) — មើលថា emoji មួយណាទាន់កំណត់ /
#  មិនទាន់កំណត់ premium icon
# ═══════════════════════════════════════════════════════════
def _emoji_status_text():
    done = [ch for ch, v in EMOJI_MAP.items() if v]
    missing = [ch for ch, v in EMOJI_MAP.items() if not v]
    lines = [f"📊 <b>Premium Emoji Status</b> — {len(done)}/{len(EMOJI_MAP)} កំណត់រួច\n"]
    if done:
        lines.append("✅ រួចហើយ: " + " ".join(done))
    if missing:
        lines.append("\n⬜ នៅសល់ (fallback ទៅ unicode ធម្មតា): " + " ".join(missing))
    return "\n".join(lines)

@bot.message_handler(commands=["emojilist"])
def cmd_emojilist(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.reply_to(message, _emoji_status_text(), parse_mode="HTML")

# ═══════════════════════════════════════════════════════════
#  PREMIUM EMOJI PREVIEW (admin-only) — បង្ហាញ icon ជាក់ស្តែងទាំងអស់ក្នុងសារ
#  តែមួយ ដើម្បីឲ្យ Admin មើលឃើញផ្ទាល់ភ្នែកថា emoji នីមួយៗត្រូវបានប្តូរ
#  ត្រឹមត្រូវឬអត់ (មិនមែនគ្រាន់តែ checkmark ជាអក្សរនៅក្នុង /emojilist ទេ)
# ═══════════════════════════════════════════════════════════
def _build_emoji_preview():
    """សាងសង់ (text, entities, count) សម្រាប់បង្ហាញ Premium Emoji ទាំងអស់ដែល
    បានកំណត់រួម គ្នាក្នុងសារតែមួយ។ offset/length គិតជា UTF-16 code units
    ដូចលក្ខណៈពិតរបស់ MessageEntity (សំខាន់ណាស់សម្រាប់ flag emoji ដូច 🇰🇭
    ដែលមាន 4 units ក្រៅពី 1)."""
    done = [(ch, eid) for ch, eid in EMOJI_MAP.items() if eid]
    if not done:
        return "", [], 0
    parts, entities, offset = [], [], 0
    for ch, eid in done:
        parts.append(ch)
        length = len(ch.encode("utf-16-le")) // 2
        entities.append(_MessageEntity(type="custom_emoji", offset=offset,
                                        length=length, custom_emoji_id=eid))
        offset += length + 1  # +1 សម្រាប់ដកឃ្លាបំបែក
        parts.append(" ")
    text = "".join(parts).rstrip()
    return text, entities, len(done)

# ═══════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.chat.id
    waiting.pop(uid, None)
    _track_user(message)
    if is_banned(uid):
        bot.send_message(uid, t(uid, "banned")); return
    if uid == ADMIN_ID:
        _multibot_hint = "\n🤖 /newbot បង្កើត Bot ថ្មី · /mybots គ្រប់គ្រង Bot រង\n" if IS_MASTER else ""
        bot.send_message(uid,
            f"🤖 <b>Panel Admin — {_bot_brand()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{ADMIN_ID}</code>\n"
            f"💹 ចំណេញ SMM: <b>{_smm_profit_pct():.0f}%</b>\n"
            f"⏱ Poll: <b>{smm_poll.get('interval',5)}s</b>\n"
            f"📊 Services: <b>{len(smm_services)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━{_multibot_hint}",
            parse_mode="HTML", reply_markup=admin_kb())
        return
    if uid in sub_admins:
        bot.send_message(uid,
            f"🛡️ <b>Sub Admin Panel — {_bot_brand()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{uid}</code>\n"
            f"📊 Services: <b>{len(smm_services)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML", reply_markup=sub_admin_kb())
        return
    if str(uid) not in user_lang:
        bot.send_message(uid,
            "សួស្តី! 👋 ជ្រើសភាសាដែលអ្នកចូលចិត្តសិន\n"
            "<i>Hi! Pick your language first 😊</i>",
            parse_mode="HTML", reply_markup=lang_select_kb())
        return
    _show_welcome(uid)

WELCOME_SETTINGS_FILE = _dpath("smm_welcome.json")
welcome_cfg = _load(WELCOME_SETTINGS_FILE, {"photo_id": ""})

TUTORIAL_VIDEO_FILE = _dpath("smm_tutorial.json")
tutorial_cfg = _load(TUTORIAL_VIDEO_FILE, {"file_id": ""})

# ═══════════════════════════════════════════════════════════
#  MANUAL DEPOSIT (ដាក់លុយដោយដៃ) — User ស្កេន QR ថេរដែល Admin កំណត់ផ្ទាល់
#  ផ្ញើភស្តុតាង (Screenshot) មក Admin ត្រួតពិនិត្យ + អនុម័តដោយដៃ
# ═══════════════════════════════════════════════════════════
MANUAL_QR_FILE = _dpath("manual_qr.json")
manual_qr_cfg  = _load(MANUAL_QR_FILE, {"enabled": False, "photo_id": "", "info": ""})

MANUAL_DEP_FILE = _dpath("manual_deposits.json")
manual_deps     = _load(MANUAL_DEP_FILE, {})

def _gen_manual_dep_id():
    return "MD" + str(int(time.time()))[-8:] + str(len(manual_deps) % 100).zfill(2)

def manual_qr_admin_kb():
    on = manual_qr_cfg.get("enabled", False)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📷 ប្តូររូប QR", callback_data="mqr:photo", color="active"))
    kb.add(InlineKeyboardButton("✏️ ប្តូរព័ត៌មាន (ឈ្មោះ/លេខគណនី)", callback_data="mqr:info", color="active"))
    kb.add(InlineKeyboardButton(("🔴 បិទ" if on else "🟢 បើក") + " Manual Deposit",
                                 callback_data="mqr:toggle", color=("danger" if on else "success")))
    return kb

def _manual_qr_status_text():
    on = manual_qr_cfg.get("enabled", False)
    has_photo = bool(manual_qr_cfg.get("photo_id"))
    return (f"🧾 <b>QR ដាក់លុយដោយដៃ (Manual Deposit)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"ស្ថានភាព: {'🟢 បើក' if on else '🔴 បិទ'}\n"
            f"រូប QR: {'✅ បានកំណត់' if has_photo else '❌ មិនទាន់មាន'}\n"
            f"ព័ត៌មាន: {manual_qr_cfg.get('info') or '<i>មិនទាន់មាន</i>'}\n\n"
            f"👇 គ្រប់គ្រង:")

@bot.callback_query_handler(func=lambda c: c.data.startswith("mqr:"))
def cb_mqr_admin(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id); return
    action = call.data.split(":", 1)[1]
    if action == "photo":
        bot.answer_callback_query(call.id)
        waiting[uid] = "await_manual_qr_photo"
        bot.send_message(uid, "📷 សូមផ្ញើរូប QR (Bakong/ធនាគារ) ដែលចង់ឲ្យ User ស្កេន:",
                          reply_markup=cancel_kb())
    elif action == "info":
        bot.answer_callback_query(call.id)
        waiting[uid] = "await_manual_qr_info"
        bot.send_message(uid,
            "✏️ សូមផ្ញើព័ត៌មានបង្ហាញអោយ User (ឧ. ឈ្មោះម្ចាស់គណនី, លេខទូរស័ព្ទ/Bakong ID):",
            reply_markup=cancel_kb())
    elif action == "toggle":
        manual_qr_cfg["enabled"] = not manual_qr_cfg.get("enabled", False)
        if manual_qr_cfg["enabled"] and not manual_qr_cfg.get("photo_id"):
            manual_qr_cfg["enabled"] = False
            bot.answer_callback_query(call.id, "❌ សូមកំណត់រូប QR ជាមុនសិន!", show_alert=True)
        else:
            _save(MANUAL_QR_FILE, manual_qr_cfg)
            bot.answer_callback_query(call.id, "✅ រួចរាល់")
        try:
            bot.edit_message_text(_manual_qr_status_text(), chat_id=uid,
                message_id=call.message.message_id, parse_mode="HTML", reply_markup=manual_qr_admin_kb())
        except Exception as _e:
            logger.debug(f"[silent] {_e}")

# ═══════════════════════════════════════════════════════════
#  FORCE-SUBSCRIBE (ការពារ User ក្លែងក្លាយ) — តម្រូវឲ្យ User ចូល Channel
#  មុននឹងប្រើប្រាស់ Bot បាន។ Admin/Sub-admin មិនប៉ះពាល់ទេ។
# ═══════════════════════════════════════════════════════════
FORCE_SUB_FILE = _dpath("force_sub.json")
force_sub_cfg  = _load(FORCE_SUB_FILE, {"enabled": False, "channel_id": "", "channel_link": ""})

def _is_channel_member(uid):
    """ត្រឡប់ True បើ User ជាសមាជិក Channel ដែលកំណត់ (ឬបើ Force-sub មិនបានបើក
    ឬ channel_id មិនទាន់កំណត់)។ ប្រសិនបើហៅ Telegram API មិនកើត (ឧ. Bot មិន
    មែនជា admin របស់ channel នោះ, ឬ channel_id ខុស) — fail-open (ត្រឡប់ True)
    ដើម្បីកុំឲ្យ User ទាំងអស់ ជាប់គាំងទាំងស្រុងដោយសារកំហុស config តែមួយ។"""
    if not force_sub_cfg.get("enabled"):
        return True
    ch = force_sub_cfg.get("channel_id", "")
    if not ch:
        return True
    try:
        m = bot.get_chat_member(ch, uid)
        return m.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"⚠️ Force-sub check failed (fail-open): {e}")
        return True

def _force_sub_kb():
    kb = InlineKeyboardMarkup()
    link = force_sub_cfg.get("channel_link", "")
    if link:
        kb.add(InlineKeyboardButton("📢 ចូល Channel", url=link, color="active"))
    kb.add(InlineKeyboardButton("✅ ខ្ញុំចូលរួចហើយ", callback_data="fsub:check", color="success"))
    return kb

def _force_sub_gate_text():
    return ("🔒 <b>សូមចូល Channel មុននឹងប្រើប្រាស់ Bot!</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "ដើម្បីការពារ User ក្លែងក្លាយ និងទទួលព័ត៌មានថ្មីៗ សូម Join Channel ខាងក្រោម "
            "រួចចុច ✅ ខ្ញុំចូលរួចហើយ")

@bot.callback_query_handler(func=lambda c: c.data == "fsub:check")
def cb_fsub_check(call):
    uid = call.message.chat.id
    bot.answer_callback_query(call.id)
    if _is_channel_member(uid):
        try:
            bot.edit_message_text("✅ <b>អ្នកបានចូល Channel រួចហើយ!</b> កំពុងបើក Bot...",
                chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
        except Exception as _e:
            logger.debug(f"[silent] {_e}")
        if str(uid) not in user_lang:
            bot.send_message(uid,
                "សួស្តី! 👋 ជ្រើសភាសាដែលអ្នកចូលចិត្តសិន\n<i>Hi! Pick your language first 😊</i>",
                parse_mode="HTML", reply_markup=lang_select_kb())
        else:
            _show_welcome(uid)
    else:
        bot.answer_callback_query(call.id, "❌ អ្នកមិនទាន់ចូល Channel ទេ! សូម Join រួចចុចម្តងទៀត។", show_alert=True)

def _save_welcome_photo(file_id):
    welcome_cfg["photo_id"] = file_id
    _save(WELCOME_SETTINGS_FILE, welcome_cfg)

def _save_tutorial_video(file_id):
    tutorial_cfg["file_id"] = file_id
    _save(TUTORIAL_VIDEO_FILE, tutorial_cfg)

def _show_welcome(uid):
    b       = bal(uid)
    custom_msg = welcome_cfg.get("custom_msg", "")
    if custom_msg:
        caption = custom_msg.format(b) if "{}" in custom_msg else custom_msg + f"\n💳 Balance: <b>${b:.2f}</b>"
    elif BOT_WELCOME_MSG:
        caption = BOT_WELCOME_MSG.format(b) if "{}" in BOT_WELCOME_MSG else BOT_WELCOME_MSG + f"\n💳 Balance: <b>${b:.2f}</b>"
    else:
        caption = t(uid, "welcome", b)
    photo_id = welcome_cfg.get("photo_id", "")
    if photo_id:
        try:
            bot.send_photo(
                uid,
                photo=photo_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=main_kb(uid)
            )
            return
        except Exception:
            pass
    # Fallback: text only
    bot.send_message(uid, caption, parse_mode="HTML", reply_markup=main_kb(uid))

# ═══════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("setlang:"))
def cb_setlang(call):
    uid  = call.message.chat.id
    lang = call.data.split(":")[1]
    user_lang[str(uid)] = lang
    _save(LANG_FILE, user_lang)
    bot.answer_callback_query(call.id, t(uid, "lang_set"))
    try: bot.delete_message(uid, call.message.message_id)
    except Exception as _e: logger.debug(f"[silent] {_e}")
    _show_welcome(uid)

@bot.callback_query_handler(func=lambda c: c.data.startswith("poll:"))
def cb_poll(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    sec = int(call.data.split(":")[1])
    smm_poll["interval"] = sec; _save(SMM_POLL_FILE, smm_poll)
    bot.answer_callback_query(call.id, f"✅ Poll = {sec}s")
    try: bot.edit_message_text(f"✅ Poll Speed = <b>{sec} វិ</b>",
                               chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
    except Exception as _e: logger.debug(f"[silent] {_e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("depbonus:"))
def cb_depbonus(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID and uid not in sub_admins:
        bot.answer_callback_query(call.id); return
    action = call.data.split(":", 1)[1]
    if action == "toggle":
        dep_bonus_cfg["enabled"] = not dep_bonus_cfg.get("enabled", True)
        _save(DEP_BONUS_FILE, dep_bonus_cfg)
        bot.answer_callback_query(call.id, "✅ បានប្តូរស្ថានភាព")
        btns = InlineKeyboardMarkup()
        toggle_label = "🔴 បិទ Auto Bonus" if dep_bonus_cfg.get("enabled", True) else "🟢 បើក Auto Bonus"
        btns.add(InlineKeyboardButton(toggle_label, callback_data="depbonus:toggle",
                                      color=("danger" if dep_bonus_cfg.get("enabled", True) else "active")))
        btns.add(InlineKeyboardButton("✏️ កែ % / ចំនួនអប្បបរមា", callback_data="depbonus:edit", color="progress"))
        try:
            bot.edit_message_text(
                f"{_dep_bonus_status_text()}\n━━━━━━━━━━━━━━━━━━\n"
                f"👉 អ្នកប្រើដាក់លុយចាប់ពី <b>${float(dep_bonus_cfg.get('min_amount',1.0)):.2f}</b> ឡើងទៅ "
                f"នឹងទទួល Bonus <b>{float(dep_bonus_cfg.get('pct',5.0)):.0f}%</b> បញ្ចូល Balance ដោយស្វ័យប្រវត្តិ "
                f"(បូកបន្ថែមលើ Promo Code ប្រសិនបើមាន)។",
                chat_id=uid, message_id=call.message.message_id, parse_mode="HTML", reply_markup=btns)
        except Exception as _e: logger.debug(f"[silent] {_e}")
        return
    if action == "edit":
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "depbonus_edit"}
        bot.send_message(uid,
            f"✏️ <b>កែ Bonus ដាក់លុយ</b>\n"
            f"បច្ចុប្បន្ន: ចាប់ពី ${float(dep_bonus_cfg.get('min_amount',1.0)):.2f} → {float(dep_bonus_cfg.get('pct',5.0)):.0f}%\n\n"
            f"ផ្ញើជា <code>ចំនួនអប្បបរមា,ភាគរយ</code>\nឧ: <code>1,5</code> (ដាក់ $1 ឡើងទៅ ទទួល 5%)",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

@bot.callback_query_handler(func=lambda c: c.data.startswith("qrcd:"))
def cb_qrcooldown(call):
    """⏳ QR Cooldown — ការពារ Spam បង្កើត QR ។ Admin/Sub-admin កែបានតែម្នាក់ (v14)"""
    uid = call.message.chat.id
    if uid != ADMIN_ID and uid not in sub_admins:
        bot.answer_callback_query(call.id); return
    action = call.data.split(":", 1)[1]
    if action == "off":
        dep_qr_cooldown_cfg["seconds"] = 0
        _save(DEP_QR_COOLDOWN_FILE, dep_qr_cooldown_cfg)
        bot.answer_callback_query(call.id, "✅ Cooldown បិទ")
        try:
            bot.edit_message_text(_dep_qr_cooldown_status_text(),
                                  chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        return
    if action == "edit":
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "qrcooldown_edit"}
        bot.send_message(uid,
            f"✏️ <b>កែ QR Cooldown</b>\n"
            f"បច្ចុប្បន្ន: <b>{int(dep_qr_cooldown_cfg.get('seconds', DEP_QR_COOLDOWN_SEC))} វិនាទី</b>\n\n"
            f"ផ្ញើចំនួន<b>វិនាទី</b>ថ្មី (ឧ: <code>15</code>) — ផ្ញើ <code>0</code> ដើម្បីបិទ Cooldown:",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

@bot.callback_query_handler(func=lambda c: c.data.startswith("dep:"))
def cb_dep(call):
    uid     = call.message.chat.id
    uid_str = str(uid)
    lang    = get_lang(uid)
    val     = call.data[4:]
    bot.answer_callback_query(call.id)

    # ── ជ្រើស amount preset ──
    if val.startswith("amt:"):
        amount = float(val.split(":")[1])
        waiting.pop(uid, None)
        _process_deposit(uid, uid_str, amount, None)
        return

    # ── custom amount ──
    if val == "custom":
        waiting[uid] = {"step": "dep_custom_amt"}
        bot.send_message(uid,
            "✏️ <b>វាយចំនួន (USD):</b>\nឧ: <code>3</code> ឬ <code>7.50</code>" if lang=="kh" else
            "✏️ <b>Enter amount (USD):</b>\ne.g. <code>3</code> or <code>7.50</code>",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

    # ── Manual Deposit (QR ថេរ + ភស្តុតាង) ──
    if val == "manual":
        if not (manual_qr_cfg.get("enabled") and manual_qr_cfg.get("photo_id")):
            bot.send_message(uid, "❌ Manual Deposit មិនទាន់មានទេ។", reply_markup=main_kb(uid))
            return
        waiting[uid] = "await_manual_dep_amount"
        info = manual_qr_cfg.get("info") or ""
        caption = (f"🧾 <b>ដាក់លុយដោយដៃ (Manual Deposit)</b>\n"
                   f"━━━━━━━━━━━━━━━━━━\n"
                   f"{info}\n\n"
                   f"👇 ស្កេន QR ខាងលើ ផ្ទេរប្រាក់ រួចវាយចំនួនប្រាក់ដែលបានផ្ទេរ:")
        try:
            bot.send_photo(uid, manual_qr_cfg["photo_id"], caption=caption,
                            parse_mode="HTML", reply_markup=cancel_kb())
        except Exception as _e:
            logger.debug(f"[silent] {_e}")
            bot.send_message(uid, caption, parse_mode="HTML", reply_markup=cancel_kb())
        return

@bot.callback_query_handler(func=lambda c: c.data.startswith("mdep:"))
def cb_mdep_admin(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id); return
    _, action, dep_id = call.data.split(":", 2)
    dep = manual_deps.get(dep_id)
    if not dep:
        bot.answer_callback_query(call.id, "❌ រកមិនឃើញសំណើនេះទេ (ប្រហែលត្រូវបានធ្វើរួច)។", show_alert=True)
        return
    if dep.get("status") != "pending":
        bot.answer_callback_query(call.id, f"⚠️ សំណើនេះត្រូវបានធ្វើរួច ({dep.get('status')})", show_alert=True)
        return
    target_uid = int(dep["uid"])
    amount = float(dep["amount"])
    if action == "ok":
        bonus = _auto_dep_bonus(amount)
        total = round(amount + bonus, 2)
        add_bal(target_uid, total)
        dep["status"] = "approved"; dep["approved_amount"] = total
        _save(MANUAL_DEP_FILE, manual_deps)
        bot.answer_callback_query(call.id, "✅ អនុម័តរួច")
        new_b = bal(target_uid)
        msg = (f"✅ <b>ដាក់លុយបានជោគជ័យ!</b> 🎉\n━━━━━━━━━━━━━━━━━━\n"
               f"💰 បានទទួល: <b>${amount:.2f}</b>")
        if bonus > 0:
            msg += f"\n🎁 Bonus: <b>+${bonus:.2f}</b>"
        msg += f"\n💳 Balance: <b>${new_b:.2f}</b>"
        try: bot.send_message(target_uid, msg, parse_mode="HTML", reply_markup=main_kb(target_uid))
        except Exception as _e: logger.debug(f"[silent] {_e}")
        try:
            bot.edit_message_caption(f"✅ <b>អនុម័តរួច</b> — ${amount:.2f} (+${bonus:.2f} bonus)\n👤 <code>{dep['uid']}</code>",
                chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
    else:
        dep["status"] = "rejected"
        _save(MANUAL_DEP_FILE, manual_deps)
        bot.answer_callback_query(call.id, "❌ បដិសេធរួច")
        try:
            bot.send_message(target_uid,
                f"❌ <b>សំណើដាក់លុយត្រូវបានបដិសេធ</b>\n💰 ${amount:.2f}\n\nសូមទាក់ទង Admin បើមានចម្ងល់។",
                parse_mode="HTML", reply_markup=main_kb(target_uid))
        except Exception as _e: logger.debug(f"[silent] {_e}")
        try:
            bot.edit_message_caption(f"❌ <b>បដិសេធរួច</b> — ${amount:.2f}\n👤 <code>{dep['uid']}</code>",
                chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("back:"))
def cb_back(call):
    uid  = call.message.chat.id
    dest = call.data[5:]
    bot.answer_callback_query(call.id)
    waiting.pop(uid, None)
    if dest == "main":
        try: bot.delete_message(uid, call.message.message_id)
        except Exception as _e: logger.debug(f"[silent] {_e}")
        _show_welcome(uid)
    elif dest == "smmcats":
        try:
            bot.edit_message_text("📊 <b>SMM Services</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Platform:",
                                  chat_id=uid, message_id=call.message.message_id,
                                  parse_mode="HTML", reply_markup=smm_cat_kb())
        except:
            bot.send_message(uid, "📊 <b>SMM Services</b>",
                             parse_mode="HTML", reply_markup=smm_cat_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmcat:"))
def cb_smmcat(call):
    uid = call.message.chat.id
    cat = call.data[7:]
    bot.answer_callback_query(call.id)
    svcs = _smm_get_svcs_in_cat(cat)
    if not svcs:
        try: bot.answer_callback_query(call.id, "❌ គ្មាន Service", show_alert=True)
        except Exception as _e: logger.debug(f"[silent] {_e}")
        return
    is_tiktok_khmer = "tiktok khmer" in cat.lower()
    if is_tiktok_khmer:
        header = (
            f"🇰🇭 <b>TikTok Khmer Services!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"• ធានាបានអ្នកមើលខ្មែរ 100%\n"
            f"• អាចបានលើសទៅតាមវីដេអូ\n\n"
            f"ជ្រើសសេវាកម្ម:"
        )
    else:
        header = f"📂 <b>{cat}</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Service:"
    try:
        bot.edit_message_text(header,
                              chat_id=uid, message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=smm_svc_kb(cat))
    except:
        bot.send_message(uid, header, parse_mode="HTML", reply_markup=smm_svc_kb(cat))

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmsvc:"))
def cb_smmsvc(call):
    uid  = call.message.chat.id
    slug = call.data[7:]
    bot.answer_callback_query(call.id)
    s = smm_services.get(slug)
    if not s: return
    sr   = _smm_sell_rate(s["cost_rate"], slug)
    lang = get_lang(uid)
    # Price display
    if s.get("flat_price"):
        price_line = f"💰 តម្លៃ: <b>${float(s['flat_price']):.2f} / order</b>"
    else:
        price_line = f"💰 {'តម្លៃ' if lang=='kh' else 'Price'}: <b>${sr:.2f}/1K</b>\n📏 Min: {s.get('min',10):,}  ·  Max: {s.get('max',100000):,}"
    desc_line = f"\n📋 {s['description']}" if s.get("description") else ""
    txt  = (f"⚡ <b>{s.get('label',slug)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{price_line}"
            f"{desc_line}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{'ជ្រើស Quantity:' if lang=='kh' else 'Choose Quantity:'}")
    try:
        bot.edit_message_text(txt, chat_id=uid, message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=smm_qty_kb(slug, s))
    except:
        bot.send_message(uid, txt, parse_mode="HTML", reply_markup=smm_qty_kb(slug, s))

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmqty:"))
def cb_smmqty(call):
    uid = call.message.chat.id
    bot.answer_callback_query(call.id)
    parts = call.data.split(":")
    slug  = parts[1]; qty = int(parts[2])
    s     = smm_services.get(slug)
    if not s: return
    price = _smm_price_for_order(slug, qty)
    lang  = get_lang(uid)
    is_tiktok_promote = s.get("flat_price") and "tiktok" in slug.lower()
    if is_tiktok_promote:
        link_prompt = (
            f"🔗 <b>ផ្ញើ Link វីដេអូ TikTok:</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 {s.get('label',slug)}\n"
            f"💰 តម្លៃ: <b>${price:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>សំខាន់!</b> បន្ទាប់ពី order:\n"
            f"1️⃣ ចូល TikTok Inbox\n"
            f"2️⃣ System notifications → Promote Assistant\n"
            f"3️⃣ ចុច <b>Respond</b> → <b>Authorize</b> → <b>Confirm</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📎 ឧ: <code>https://www.tiktok.com/@user/video/123</code>"
        )
    else:
        link_prompt = (
            f"🔗 <b>{'ផ្ញើ Link:' if lang=='kh' else 'Send Link:'}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 {s.get('label',slug)}\n"
            f"💰 {qty:,} — <b>${price:.4f}</b>"
        )
    waiting[uid] = {"step": "smm_link", "slug": slug, "qty": qty, "price": price}
    try:
        bot.edit_message_text(
            link_prompt,
            chat_id=uid, message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="back:main", color="inactive")]]))
    except:
        bot.send_message(uid, link_prompt, parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmapi:"))
def cb_smmapi(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    action = call.data[7:]
    bot.answer_callback_query(call.id)

    if action == "setup":
        waiting[uid] = "smm_api_url"
        bot.send_message(uid,
            "🌐 <b>ផ្ញើ SMM API URL</b>\nឧ: <code>https://smmking.net/api/v2</code>",
            parse_mode="HTML", reply_markup=cancel_kb())

    elif action == "test":
        url = smm_api.get("url",""); key = smm_api.get("key","")
        if not url or not key:
            bot.send_message(uid, "❌ API មិនទាន់ set!", reply_markup=admin_kb()); return
        try:
            r = http.post(url, data={"key": key, "action": "balance"}, timeout=10)
            d = r.json()
            balance  = d.get("balance", d.get("Balance", "?"))
            currency = d.get("currency", d.get("Currency", "USD"))
            bot.send_message(uid,
                f"✅ <b>Connection OK!</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"💰 Balance: <b>{balance} {currency}</b>",
                parse_mode="HTML", reply_markup=admin_kb())
        except Exception as e:
            bot.send_message(uid, f"❌ Connection failed: <code>{e}</code>",
                             parse_mode="HTML", reply_markup=admin_kb())

    elif action == "clear":
        smm_api.clear(); smm_api.update({"url":"","key":""})
        _save(SMM_API_FILE, smm_api)
        bot.send_message(uid, "🗑️ SMM API cleared!", reply_markup=admin_kb())

# ── Admin: Confirm / Reject deposit ──
@bot.callback_query_handler(func=lambda c: c.data.startswith("admconf:"))
def cb_admconf(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    dep_id = call.data[8:]
    dep    = smm_deps.get(dep_id)
    if not dep or dep.get("status") != "pending":
        bot.answer_callback_query(call.id, "⚠️ Deposit មិន pending ទេ", show_alert=True); return
    bot.answer_callback_query(call.id)
    # Ask admin for amount
    waiting[uid] = {"step": "adm_confirm_dep", "dep_id": dep_id}
    bot.send_message(uid,
        f"💰 <b>Enter amount received (USD):</b>\n"
        f"📌 Ref: <code>{dep.get('reference','')}</code>\n"
        f"👤 User: <code>{dep.get('uid','')}</code>",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("admrej:"))
def cb_admrej(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    dep_id = call.data[7:]
    dep    = smm_deps.get(dep_id)
    if not dep:
        bot.answer_callback_query(call.id, "❌ Deposit រកមិនឃើញ", show_alert=True); return
    bot.answer_callback_query(call.id)
    dep["status"] = "rejected"; _save(SMM_DEP_FILE, smm_deps)
    try:
        bot.edit_message_text(
            f"❌ <b>Deposit Rejected</b>\n📌 Ref: <code>{dep.get('reference','')}</code>",
            chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
    except Exception as _e: logger.debug(f"[silent] {_e}")
    try:
        bot.send_message(int(dep["uid"]),
            "❌ <b>ការ Deposit ត្រូវបាន Reject!</b>\nទំនាក់ Admin: @KhmerSmm099",
            parse_mode="HTML")
    except Exception as _e: logger.debug(f"[silent] {_e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("mansvc_cat:"))
def cb_mansvc_cat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    cat = call.data[len("mansvc_cat:"):]
    bot.answer_callback_query(call.id)
    step = waiting.get(uid, {})
    label = step.get("label", "") if isinstance(step, dict) else ""
    if cat == "__custom__":
        waiting[uid] = {"step": "manual_svc_cat_custom", "label": label}
        bot.send_message(uid,
            "✏️ <b>វាយ Category ផ្ទាល់ខ្លួន:</b>\nឧ: <code>TikTok Khmer</code>",
            parse_mode="HTML", reply_markup=cancel_kb())
    else:
        waiting[uid] = {"step": "manual_svc_price", "label": label, "cat": cat}
        bot.send_message(uid,
            f"💰 <b>ដាក់តម្លៃ (USD per 1000)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📂 Category: <b>{cat}</b>\n"
            f"📝 ឈ្មោះ: <b>{label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"ឧ: <code>0.50</code> = $0.50 per 1K\n"
            f"ឧ: <code>1.20</code> = $1.20 per 1K",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("mansvcplat:"))
def cb_mansvcplat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    key = call.data[len("mansvcplat:"):]
    bot.answer_callback_query(call.id)
    step = waiting.get(uid, {})
    if not isinstance(step, dict): return
    waiting[uid] = {"step": "manual_svc_price", "label": step.get("label",""),
                     "cat": step.get("cat",""), "platform": key}
    plabel = _PLATFORM_LABEL_BY_KEY.get(key, key)
    bot.send_message(uid,
        f"💰 <b>ដាក់តម្លៃ (USD per 1000)</b>\n"
        f"🌐 Platform: <b>{plabel}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ឧ: <code>0.50</code> = $0.50 per 1K\n"
        f"ឧ: <code>1.20</code> = $1.20 per 1K",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("pkgcat:"))
def cb_pkgcat(call):
    """Admin: choose category for a new flat-price Package"""
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    cat = call.data[len("pkgcat:"):]
    bot.answer_callback_query(call.id)
    step = waiting.get(uid, {})
    label = step.get("label", "") if isinstance(step, dict) else ""
    if cat == "__custom__":
        waiting[uid] = {"step": "pkg_cat_custom", "label": label}
        bot.send_message(uid,
            "✏️ <b>វាយ Category ផ្ទាល់ខ្លួន:</b>\nឧ: <code>TikTok Khmer</code>",
            parse_mode="HTML", reply_markup=cancel_kb())
    else:
        waiting[uid] = {"step": "pkg_desc", "label": label, "cat": cat}
        bot.send_message(uid,
            f"📂 Category: <b>{cat}</b>\n📝 ឈ្មោះ: <b>{label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>ការពិពណ៌នា Package (Description)</b>\n"
            f"ឧ: <code>1K-2K Likes ❤️ + 3.5K Views 👁</code>\n"
            f"ឬ វាយ <code>-</code> ដើម្បីរំលង",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("pkgplat:"))
def cb_pkgplat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    key = call.data[len("pkgplat:"):]
    bot.answer_callback_query(call.id)
    step = waiting.get(uid, {})
    if not isinstance(step, dict): return
    waiting[uid] = {"step": "pkg_desc", "label": step.get("label",""),
                     "cat": step.get("cat",""), "platform": key}
    plabel = _PLATFORM_LABEL_BY_KEY.get(key, key)
    bot.send_message(uid,
        f"🌐 Platform: <b>{plabel}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>ការពិពណ៌នា Package (Description)</b>\n"
        f"ឧ: <code>1K-2K Likes ❤️ + 3.5K Views 👁</code>\n"
        f"ឬ វាយ <code>-</code> ដើម្បីរំលង",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("editprice:"))
def cb_editprice(call):
    """Admin: edit the price of an existing service/package"""
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    slug = call.data[len("editprice:"):]
    s = smm_services.get(slug)
    if not s:
        bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb()); return
    waiting[uid] = {"step": "edit_svc_price", "slug": slug}
    if s.get("flat_price"):
        cur = f"${float(s['flat_price']):.2f} / order"
    else:
        cur = f"${float(s.get('cost_rate',0)):.2f} / 1K"
    bot.send_message(uid,
        f"💰 <b>កែតម្លៃ</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📝 {s.get('label', slug)}\n"
        f"💵 តម្លៃបច្ចុប្បន្ន: <b>{cur}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"វាយ <b>តម្លៃថ្មី</b> (លេខទទេ):",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("manord:"))
def cb_manord(call):
    """Admin: mark manual order as completed"""
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    parts = call.data.split(":")
    action = parts[1]
    oid    = parts[2] if len(parts) > 2 else ""
    bot.answer_callback_query(call.id)
    o = smm_orders.get(oid)
    if not o:
        bot.send_message(uid, f"❌ Order <code>{oid}</code> រកមិនឃើញ",
                         parse_mode="HTML"); return
    # ការពារចុច Done/Reject ដដែលៗ (ឧ. Admin ចុចលឿនពីរដង) ដែលអាចធ្វើឲ្យសងលុយ/Complete ២ដង
    if o.get("status") in ("completed", "rejected", "canceled", "partial"):
        bot.send_message(uid,
            f"⚠️ Order <code>{oid}</code> ត្រូវបានដំណើរការរួចហើយ (ស្ថានភាព: <b>{o.get('status')}</b>)",
            parse_mode="HTML"); return
    if action == "done":
        waiting[uid] = {"step": "manual_order_done", "oid": oid, "user_uid": o["uid"]}
        bot.send_message(uid,
            f"✅ <b>Complete Order</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{oid}</code>\n"
            f"👤 User: <code>{o['uid']}</code>\n"
            f"📊 {o.get('label','?')} × {o.get('qty',0):,}\n"
            f"🔗 <code>{o.get('link','?')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>វាយ Note ឲ្យ User</b> (ឬ <code>-</code> ដើម្បីរំលង):",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "reject":
        smm_orders[oid]["status"] = "rejected"
        smm_orders[oid]["refunded"] = float(o.get("price") or 0)
        _save(SMM_ORD_FILE, smm_orders)
        try:
            bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
        except Exception as _e: logger.debug(f"[silent] {_e}")
        # Refund — ដាច់ដោយឡែកពី Notify, ដើម្បីកុំឲ្យ User ខាតលុយបើផ្ញើសារទៅគាត់មិនចេញ (ឧ. Block Bot)
        add_bal(int(o["uid"]), float(o.get("price") or 0))
        try:
            bot.send_message(int(o["uid"]),
                f"❌ <b>Order ត្រូវបាន Reject!</b>\n"
                f"🆔 <code>{oid}</code>\n"
                f"💳  លុយបានដក (${ o.get('price',0):.4f}) ត្រូវបានសងវិញ\n"
                f"ទំនាក់ Admin ប្រសិនបើចង់ដឹង: @smos_sne1",
                parse_mode="HTML")
        except Exception as _e: logger.debug(f"[silent] {_e}")
        bot.send_message(uid,
            f"❌ <b>Rejected & Refunded</b>\n🆔 <code>{oid}</code>",
            parse_mode="HTML", reply_markup=admin_kb())


@bot.callback_query_handler(func=lambda c: c.data.startswith("editsvc:"))
def cb_editsvc(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    slug = call.data[len("editsvc:"):]
    s = smm_services.get(slug)
    if not s:
        bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb()); return
    old_label = s.get("label", slug)
    api_id    = s.get("api_id", "?")
    cur_plabel = _PLATFORM_LABEL_BY_KEY.get(s.get("platform"), "⚠️ មិនទាន់កំណត់ (Guess ស្វ័យប្រវត្តិ)")
    waiting[uid] = {"step": "edit_svc_name", "slug": slug}
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🌐 កែ Platform (សម្រាប់ Link)",
                                 callback_data=f"editsvcplat:{slug}", color="progress"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data="back:main", color="inactive"))
    bot.send_message(uid,
        f"✏️ <b>កែ Service</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆔 API ID: <code>{api_id}</code>\n"
        f"📝 ឈ្មោះ​បច្ចុប្បន្ន:\n<b>{old_label}</b>\n"
        f"🌐 Platform បច្ចុប្បន្ន: <b>{cur_plabel}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"វាយ <b>ឈ្មោះថ្មី</b> ដើម្បីប្ដូរ, ឬចុច 🌐 ដើម្បីកែ Platform:",
        parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("editsvcplat:"))
def cb_editsvcplat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    bot.answer_callback_query(call.id)
    slug = call.data[len("editsvcplat:"):]
    if slug not in smm_services:
        bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb()); return
    waiting[uid] = {"step": "edit_svc_platform_pick", "slug": slug}
    bot.send_message(uid,
        f"🌐 <b>ជ្រើស Platform ថ្មី</b>\n"
        f"📝 {smm_services[slug].get('label', slug)}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ចុច 🔓 ផ្សេង បើ Service នេះទទួល Link ណាក៏បាន",
        parse_mode="HTML", reply_markup=_platform_pick_kb("editsvcplatpick"))

@bot.callback_query_handler(func=lambda c: c.data.startswith("editsvcplatpick:"))
def cb_editsvcplatpick(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    bot.answer_callback_query(call.id)
    key = call.data[len("editsvcplatpick:"):]
    step = waiting.get(uid, {})
    slug = step.get("slug") if isinstance(step, dict) else None
    if not slug or slug not in smm_services:
        bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb()); return
    smm_services[slug]["platform"] = key
    _save(SMM_SVC_FILE, smm_services)
    waiting.pop(uid, None)
    plabel = _PLATFORM_LABEL_BY_KEY.get(key, key)
    bot.send_message(uid,
        f"✅ <b>Platform កែរួច!</b>\n"
        f"📝 {smm_services[slug].get('label', slug)}\n"
        f"🌐 Platform: <b>{plabel}</b>",
        parse_mode="HTML", reply_markup=admin_kb())


@bot.callback_query_handler(func=lambda c: c.data.startswith("smmaddcat:"))
def cb_smmaddcat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    cat = call.data[len("smmaddcat:"):]
    bot.answer_callback_query(call.id)
    if cat == "custom":
        waiting[uid] = "smm_add_cat"
        bot.send_message(uid, "✏️ វាយ Category name (ឧ: TikTok Live, Spotify):",
                         reply_markup=cancel_kb())
    else:
        waiting[uid] = {"step": "smm_add_ids", "cat": cat}
        bot.send_message(uid,
            f"📂 Category: <b>{cat}</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"ផ្ញើ Service IDs (comma separated):\n"
            f"ឧ: <code>5441,5448,5502</code>\n\n"
            f"💡 IDs រក នៅ SMM Panel → Services",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmaddplat:"))
def cb_smmaddplat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    key = call.data[len("smmaddplat:"):]
    bot.answer_callback_query(call.id)
    step = waiting.get(uid, {})
    if not isinstance(step, dict): return
    cat = step.get("cat","")
    waiting[uid] = {"step": "smm_add_ids", "cat": cat, "platform": key}
    plabel = _PLATFORM_LABEL_BY_KEY.get(key, key)
    bot.send_message(uid,
        f"📂 Category: <b>{cat}</b> · 🌐 Platform: <b>{plabel}</b>\n"
        f"ផ្ញើ API Service IDs (comma):\n"
        f"ឧ: <code>5441,5448,5502</code>\n\n"
        f"💡 រក IDs នៅ SMM API Panel ➡️ Services",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("delsvc:"))
def cb_delsvc(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    parts = call.data.split(":", 2)

    if len(parts) == 3 and parts[1] == "cat":
        cat = parts[2]
        to_del = [slug for slug, s in smm_services.items() if s.get("category") == cat]
        for slug in to_del:
            smm_services.pop(slug, None)
        _save(SMM_SVC_FILE, smm_services)
        try: bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
        except Exception as _e: logger.debug(f"[silent] {_e}")
        bot.send_message(uid,
            f"✅ Deleted <b>{len(to_del)}</b> services in <b>{cat}</b>",
            parse_mode="HTML", reply_markup=admin_kb())
        return

    slug = parts[1]
    s    = smm_services.get(slug)
    if not s:
        bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb()); return
    label  = s.get("label", slug)
    api_id = s.get("api_id", "?")
    smm_services.pop(slug, None)
    _save(SMM_SVC_FILE, smm_services)
    try: bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except Exception as _e: logger.debug(f"[silent] {_e}")
    bot.send_message(uid,
        f"✅ Deleted: <b>[{api_id}] {label}</b>\n"
        f"📊 Remaining: <b>{len(smm_services)}</b>",
        parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("useraction:"))
def cb_useraction(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    parts  = call.data.split(":")
    action = parts[1]
    target = parts[2] if len(parts) > 2 else ""

    if action == "addbal":
        waiting[uid] = {"step": "add_balance_amt", "target": target}
        bot.send_message(uid,
            f"💸 <b>បន្ថែមប្រាក់</b>\n👤 UID: <code>{target}</code>\n"
            f"💳 Balance: <b>${bal(int(target)):.2f}</b>\nផ្ញើ Amount $:",
            parse_mode="HTML", reply_markup=cancel_kb())

    elif action == "dedbal":
        waiting[uid] = {"step": "deduct_balance_amt", "target": target}
        bot.send_message(uid,
            f"💔 <b>កាត់ប្រាក់</b>\n👤 UID: <code>{target}</code>\n"
            f"💳 Balance: <b>${bal(int(target)):.2f}</b>\nផ្ញើ Amount $ ដក:",
            parse_mode="HTML", reply_markup=cancel_kb())

    elif action == "ban":
        users_db[target]["banned"] = True; _save(USERS_FILE, users_db)
        bot.send_message(uid, f"🚫 Banned <code>{target}</code>",
                         parse_mode="HTML", reply_markup=admin_kb())

    elif action == "unban":
        users_db[target]["banned"] = False; _save(USERS_FILE, users_db)
        bot.send_message(uid, f"🔓 Unbanned <code>{target}</code>",
                         parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("adminpromo:"))
def cb_adminpromo(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    action = call.data[len("adminpromo:"):]
    if action == "add":
        waiting[uid] = "promo_add_code"
        bot.send_message(uid,
            "🎟️ <b>បន្ថែម Promo Code</b>\n━━━━━━━━━━━━━━━━━━\n"
            "Format: <code>CODE DISCOUNT TYPE USES</b></code>\n\n"
            "TYPE: <code>pct</code> (%) ឬ <code>fix</code> ($)\n\n"
            "ឧទាហរណ៍:\n"
            "<code>SAVE50 50 pct 100</code>  → 50% off, 100 uses\n"
            "<code>GIFT1 1.00 fix 50</code>  → $1 bonus, 50 uses",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "list":
        _show_promos(uid)

# ═══════════════════════════════════════════════════════════
#  /newbot CONFIRMATION + CLONE MANAGEMENT CALLBACKS
# ═══════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data == "newbot_confirm_yes")
def cb_newbot_confirm_yes(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    step = waiting.get(uid)
    if not isinstance(step, dict) or step.get("step") != "newbot_confirm":
        bot.answer_callback_query(call.id, "Session ផុតកំណត់"); return
    name = step["name"]
    pay_method = step.get("pay_method", "auto")
    cfg = {
        "token": step["token"],
        "admin_id": step["new_admin_id"],
        "camrapid_key": step.get("camrapid_key", ""),
        "port": step["port"],
        "display_name": step.get("display_name", step["name"]),
        "welcome_msg":  step.get("welcome_msg", ""),
        "pay_method": pay_method,
        "manual_qr_photo_id": step.get("manual_qr_photo_id", ""),
        "manual_qr_info": step.get("manual_qr_info", ""),
        "aba_key": step.get("aba_key", ""),
        "aba_merchant": step.get("aba_merchant", ""),
    }
    clone_registry[name] = cfg
    _save(CLONES_REGISTRY, clone_registry)
    if pay_method == "manual" and cfg["manual_qr_photo_id"]:
        try:
            wdir = _clone_dir(name)
            _save(os.path.join(wdir, "manual_qr.json"), {
                "enabled": True,
                "photo_id": cfg["manual_qr_photo_id"],
                "info": cfg["manual_qr_info"],
            })
        except Exception as _e:
            logger.error(f"Pre-seed manual_qr.json failed for clone '{name}': {_e}")
    waiting.pop(uid, None)
    bot.answer_callback_query(call.id, "កំពុងបង្កើត...")
    try:
        _spawn_clone(name, cfg)
        bot.send_message(uid,
            f"🎉 បានបង្កើត Bot '<b>{name}</b>' ជោគជ័យ ហើយកំពុងដំណើរការ!\n"
            f"មាន feature ដូចគ្នា ១០០% ជា bot នេះ តែទិន្នន័យដាច់ដោយឡែកទាំងស្រុង។\n"
            f"ប្រើ /mybots ដើម្បីគ្រប់គ្រង។",
            parse_mode="HTML", reply_markup=admin_kb())
    except Exception as e:
        bot.send_message(uid, f"❌ បង្កើតមិនជោគជ័យ: {e}", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data == "newbot_confirm_no")
def cb_newbot_confirm_no(call):
    uid = call.message.chat.id
    waiting.pop(uid, None)
    bot.answer_callback_query(call.id, "បានបោះបង់")
    bot.send_message(uid, "❌ បានបោះបង់ការបង្កើត bot ថ្មី។", reply_markup=admin_kb())

def _clone_pay_txt(pay_method):
    """Label ស្តង់ដារសម្រាប់វិធីទូទាត់របស់ clone មួយ — ប្រើទាំង /mybots view និង
    ក្រោយប្តូរ Step ទូទាត់ (cln_pay) ដើម្បីកុំឲ្យ text ខុសគ្នារវាងកន្លែង។"""
    if pay_method == "manual":
        return "🖼 Manual QR (Step 2)"
    if pay_method == "aba":
        return "🏦 ABA PayWay Auto (Step 3)"
    return "🔄 CamRapidPay Auto (Step 1)"

_STEP_EMOJI = ["0️⃣","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣"]
def _step_label(n, total=None):
    """បង្កើត label ជំហានស្តង់ដារ ('3️⃣ ជំហានទី 3/7') សម្រាប់ wizard /newbot
    — ធានាថាលេខមិនត្រូវគ្នា/ដដែលៗរវាងជំហាន ហើយ total (7=Auto, 8=Manual)
    បង្ហាញភ្លាមៗពេលដឹងផ្លូវ (Auto/Manual) ។"""
    e = _STEP_EMOJI[n] if 0 <= n < len(_STEP_EMOJI) else f"{n}."
    return f"{e} ជំហានទី {n}/{total}" if total else f"{e} ជំហានទី {n}"

@bot.callback_query_handler(func=lambda c: c.data.startswith("newbot_pay|"))
def cb_newbot_paymethod(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    step = waiting.get(uid)
    if not isinstance(step, dict) or step.get("step") != "newbot_paymethod":
        bot.answer_callback_query(call.id, "Session ផុតកំណត់"); return
    method = call.data.split("|", 1)[1]
    bot.answer_callback_query(call.id)
    if method == "auto":
        waiting[uid] = {**step, "step": "newbot_key", "pay_method": "auto"}
        bot.send_message(uid, f"{_step_label(5, 7)} — វាយ <b>CamRapidPay API Key</b> សម្រាប់ bot នេះ:",
                          parse_mode="HTML", reply_markup=cancel_kb())
    elif method == "aba":
        waiting[uid] = {**step, "step": "newbot_aba_key", "pay_method": "aba", "camrapid_key": ""}
        bot.send_message(uid,
            f"{_step_label(5, 8)} — វាយ <b>ABA PayWay Profile Key</b> សម្រាប់ bot នេះ "
            "(ពី khmer-system.com/operator/profile):",
            parse_mode="HTML", reply_markup=cancel_kb())
    else:
        waiting[uid] = {**step, "step": "newbot_manual_qr_photo", "pay_method": "manual", "camrapid_key": ""}
        bot.send_message(uid,
            f"{_step_label(5, 8)} — ផ្ញើ <b>រូបភាព QR</b> (Bakong KHQR) សម្រាប់ bot នេះ (ផ្ញើជារូបភាព):",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_view|"))
def cb_cln_view(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    cfg = clone_registry.get(name)
    if not cfg:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    status = "🟢 កំពុងដំណើរការ" if _clone_is_running(name) else "🔴 បិទ"
    masked = cfg["token"][:10] + "..." + cfg["token"][-4:]
    pay_txt = _clone_pay_txt(cfg.get("pay_method"))
    text = (f"🤖 <b>{name}</b>\nស្ថានភាព: {status}\n"
            f"ឈ្មោះ Display: <code>{cfg.get('display_name', name)}</code>\n"
            f"Admin ID: <code>{cfg['admin_id']}</code>\nToken: <code>{masked}</code>\n"
            f"ការទូទាត់: {pay_txt}\n"
            f"Port: <code>{cfg['port']}</code>")
    kb = InlineKeyboardMarkup(row_width=2)
    if _clone_is_running(name):
        kb.add(InlineKeyboardButton("🛑 បិទ", callback_data=f"cln_stop|{name}", color="inactive"),
               InlineKeyboardButton("🔄 Restart", callback_data=f"cln_restart|{name}", color="progress"))
    else:
        kb.add(InlineKeyboardButton("▶️ ដំណើរការ", callback_data=f"cln_start|{name}", color="active"))
    kb.add(InlineKeyboardButton("🔁 ប្តូរ Step ទូទាត់", callback_data=f"cln_pay|{name}", color="progress"))
    kb.add(InlineKeyboardButton("👤 ប្តូរ Admin", callback_data=f"cln_admin|{name}", color="progress"))
    kb.add(InlineKeyboardButton("✏️ ប្តូរ ឈ្មោះ Bot", callback_data=f"cln_rename|{name}", color="progress"))
    kb.add(InlineKeyboardButton("⚙️ ការកំណត់ផ្សេងទៀត", callback_data=f"cln_more|{name}", color="progress"))
    kb.add(InlineKeyboardButton("🗑️ លុប", callback_data=f"cln_delete|{name}", color="inactive"))
    kb.add(InlineKeyboardButton("⬅️ ត្រឡប់", callback_data="cln_list", color="inactive"))
    bot.send_message(uid, text, parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_pay|"))
def cb_cln_pay(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("1️⃣ Step 1 — CamRapidPay QR ស្វ័យប្រវត្តិ", callback_data=f"cln_paysel|auto|{name}", color="active"))
    kb.add(InlineKeyboardButton("3️⃣ Step 3 — ABA PayWay ស្វ័យប្រវត្តិ", callback_data=f"cln_paysel|aba|{name}", color="active"))
    kb.add(InlineKeyboardButton("2️⃣ Step 2 — QR ដាក់ដោយដៃ (Manual)", callback_data=f"cln_paysel|manual|{name}", color="progress"))
    kb.add(InlineKeyboardButton("⬅️ ត្រឡប់", callback_data=f"cln_view|{name}", color="inactive"))
    bot.send_message(uid,
        f"🔁 <b>ប្តូរ Step ទូទាត់ — {name}</b>\n\n"
        "1️⃣ <b>Step 1</b> — CamRapidPay API Key → QR ស្វ័យប្រវត្តិ\n"
        "3️⃣ <b>Step 3</b> — ABA PayWay Profile Key + Merchant ID → QR ស្វ័យប្រវត្តិ\n"
        "2️⃣ <b>Step 2</b> — Upload រូប QR ដាក់ដោយដៃ",
        parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_paysel|"))
def cb_cln_paysel(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    _, method, name = call.data.split("|", 2)
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    if method == "auto":
        waiting[uid] = {"step": "cln_pay_key", "clone": name}
        bot.send_message(uid, f"វាយ <b>CamRapidPay API Key</b> ថ្មីសម្រាប់ '{name}':",
                          parse_mode="HTML", reply_markup=cancel_kb())
    elif method == "aba":
        waiting[uid] = {"step": "cln_pay_aba_key", "clone": name}
        bot.send_message(uid, f"វាយ <b>ABA PayWay Profile Key</b> ថ្មីសម្រាប់ '{name}':",
                          parse_mode="HTML", reply_markup=cancel_kb())
    else:
        waiting[uid] = {"step": "cln_pay_qr_photo", "clone": name}
        bot.send_message(uid, f"ផ្ញើ <b>រូបភាព QR</b> (Bakong KHQR) ថ្មីសម្រាប់ '{name}':",
                          parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_admin|"))
def cb_cln_admin(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    cfg = clone_registry.get(name)
    if not cfg:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    waiting[uid] = {"step": "cln_change_admin", "clone": name}
    bot.send_message(uid,
        f"👤 <b>ប្តូរ Admin — {name}</b>\n"
        f"Admin ID បច្ចុប្បន្ន: <code>{cfg['admin_id']}</code>\n\n"
        f"វាយ <b>Telegram ID</b> ថ្មីរបស់ admin (លេខ):",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_rename|"))
def cb_cln_rename(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    cfg = clone_registry.get(name)
    if not cfg:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    waiting[uid] = {"step": "cln_rename_name", "clone": name}
    bot.send_message(uid,
        f"✏️ <b>ប្តូរ ឈ្មោះ Bot (Display Name) — {name}</b>\n"
        f"ឈ្មោះបច្ចុប្បន្ន: <code>{cfg.get('display_name', name)}</code>\n\n"
        f"វាយ <b>ឈ្មោះថ្មី</b> ដែលបង្ហាញដល់អ្នកប្រើ (ឧ. <code>Jak Like Shop</code>)\n"
        f"ចំណាំ: នេះជាឈ្មោះបង្ហាញ (display) ប៉ុណ្ណោះ — មិនប៉ះពាល់ឈ្មោះ internal (<code>{name}</code>) ដែលប្រើសម្គាល់ក្នុង /mybots ទេ:",
        parse_mode="HTML", reply_markup=cancel_kb())

# ═══════════════════════════════════════════════════════════
#  Clone ⚙️ ការកំណត់ផ្សេងទៀត (Support / Sub Admins / Bakong / QR Cooldown)
#  — កែផ្ទាល់ពី Master តាម /mybots ដោយសរសេរ file JSON ចូល bot_clones/<n>/
#    ដោយផ្ទាល់ (ដូចលក្ខណៈ manual_qr.json ដែលមានស្រាប់) — clone process
#    ត្រូវ restart ដើម្បីអានតម្លៃថ្មី (config files ទាំងនេះផ្ទុកតែម្តងពេល startup)
# ═══════════════════════════════════════════════════════════
def _clone_file(name, filename):
    return os.path.join(_clone_dir(name), filename)

def _clone_load(name, filename, default):
    return _load(_clone_file(name, filename), default)

def _clone_save_restart(uid, name, filename, data, ok_text):
    _save(_clone_file(name, filename), data)
    cfg = clone_registry.get(name)
    was_running = cfg and _clone_is_running(name)
    if was_running:
        _stop_clone(name); time.sleep(1); _spawn_clone(name, cfg)
    bot.send_message(uid, ok_text + (" ហើយ restart រួច។" if was_running else " (bot នេះកំពុងបិទ — ចាប់ផ្តើមវាដើម្បីអនុវត្ត)។"),
                      parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_more|"))
def cb_cln_more(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("💬 Support Message", callback_data=f"cln_support|{name}", color="progress"))
    kb.add(InlineKeyboardButton("👥 Sub Admins", callback_data=f"cln_subadmin|{name}", color="progress"))
    kb.add(InlineKeyboardButton("🏦 Bakong Deep Link", callback_data=f"cln_bakong|{name}", color="progress"))
    kb.add(InlineKeyboardButton("⏳ QR Cooldown", callback_data=f"cln_cooldown|{name}", color="progress"))
    kb.add(InlineKeyboardButton("⬅️ ត្រឡប់", callback_data=f"cln_view|{name}", color="inactive"))
    bot.send_message(uid, f"⚙️ <b>ការកំណត់ផ្សេងទៀត — {name}</b>", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_support|"))
def cb_cln_support(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    cur = _clone_load(name, "smm_support.json", {"kh": "", "en": ""})
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✏️ កែ ខ្មែរ", callback_data=f"cln_support_lang|kh|{name}", color="progress"))
    kb.add(InlineKeyboardButton("✏️ កែ English", callback_data=f"cln_support_lang|en|{name}", color="progress"))
    kb.add(InlineKeyboardButton("⬅️ ត្រឡប់", callback_data=f"cln_more|{name}", color="inactive"))
    bot.send_message(uid,
        f"💬 <b>Support Message — {name}</b>\n"
        f"ខ្មែរ: <code>{(cur.get('kh') or '(default)')[:200]}</code>\n"
        f"English: <code>{(cur.get('en') or '(default)')[:200]}</code>",
        parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_support_lang|"))
def cb_cln_support_lang(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    _, lang, name = call.data.split("|", 2)
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    waiting[uid] = {"step": "cln_support_text", "clone": name, "lang": lang}
    bot.send_message(uid,
        f"✏️ <b>វាយ Support Message {'(ខ្មែរ)' if lang=='kh' else '(English)'} — {name}</b>\n"
        "ឬផ្ញើ <code>-</code> ដើម្បី reset ទៅ default:",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_subadmin|"))
def cb_cln_subadmin(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    cur = _clone_load(name, "smm_sub_admins.json", [])
    kb = InlineKeyboardMarkup(row_width=1)
    for sa in cur:
        kb.add(InlineKeyboardButton(f"🗑️ លុប {sa}", callback_data=f"cln_subadmin_del|{sa}|{name}", color="inactive"))
    kb.add(InlineKeyboardButton("➕ បន្ថែម Sub Admin", callback_data=f"cln_subadmin_add|{name}", color="active"))
    kb.add(InlineKeyboardButton("⬅️ ត្រឡប់", callback_data=f"cln_more|{name}", color="inactive"))
    bot.send_message(uid,
        f"👥 <b>Sub Admins — {name}</b> ({len(cur)})",
        parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_subadmin_add|"))
def cb_cln_subadmin_add(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    waiting[uid] = {"step": "cln_subadmin_add_id", "clone": name}
    bot.send_message(uid, f"➕ <b>បន្ថែម Sub Admin — {name}</b>\nផ្ញើ Telegram ID (លេខ):",
                      parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_subadmin_del|"))
def cb_cln_subadmin_del(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    _, sa_id, name = call.data.split("|", 2)
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    cur = _clone_load(name, "smm_sub_admins.json", [])
    sa_id = int(sa_id)
    if sa_id in cur:
        cur.remove(sa_id)
    _clone_save_restart(uid, name, "smm_sub_admins.json", cur,
                         f"✅ លុប Sub Admin <code>{sa_id}</code> ចេញពី '<b>{name}</b>'")

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_bakong|"))
def cb_cln_bakong(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    waiting[uid] = {"step": "cln_bakong_token", "clone": name}
    bot.send_message(uid,
        f"🏦 <b>ផ្ញើ Bakong Developer Token ថ្មី — {name}</b>\n"
        "(យកពី https://api-bakong.nbc.gov.kh/register/)\n"
        "ឬផ្ញើ <code>-</code> ដើម្បី reset ទៅ env/default:",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("cln_cooldown|"))
def cb_cln_cooldown(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    name = call.data.split("|", 1)[1]
    if name not in clone_registry:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return
    bot.answer_callback_query(call.id)
    cur = _clone_load(name, "dep_qr_cooldown.json", {"seconds": DEP_QR_COOLDOWN_SEC})
    waiting[uid] = {"step": "cln_cooldown_sec", "clone": name}
    bot.send_message(uid,
        f"⏳ <b>QR Cooldown — {name}</b>\nបច្ចុប្បន្ន: <b>{cur.get('seconds', DEP_QR_COOLDOWN_SEC)} វិនាទី</b>\n\n"
        "វាយ <b>ចំនួនវិនាទី</b> ថ្មី (0 = បិទ Cooldown):",
        parse_mode="HTML", reply_markup=cancel_kb())

def _apply_clone_pay_update(uid, name, pay_method, camrapid_key="", manual_photo_id="", manual_info="",
                             aba_key="", aba_merchant=""):
    """កែប្រែ payment method របស់ clone ដែលមានស្រាប់ ហើយ restart វា"""
    cfg = clone_registry.get(name)
    if not cfg:
        bot.send_message(uid, "❌ រកមិនឃើញ bot នេះទេ (ប្រហែលត្រូវបានលុប)។", reply_markup=admin_kb())
        return
    cfg["pay_method"] = pay_method
    if pay_method == "auto":
        cfg["camrapid_key"] = camrapid_key
        cfg["manual_qr_photo_id"] = ""
        cfg["manual_qr_info"] = ""
        cfg["aba_key"] = ""
        cfg["aba_merchant"] = ""
    elif pay_method == "aba":
        cfg["aba_key"] = aba_key
        cfg["aba_merchant"] = aba_merchant
        cfg["manual_qr_photo_id"] = ""
        cfg["manual_qr_info"] = ""
        cfg["camrapid_key"] = ""
    else:
        cfg["manual_qr_photo_id"] = manual_photo_id
        cfg["manual_qr_info"] = manual_info
        cfg["camrapid_key"] = ""
        cfg["aba_key"] = ""
        cfg["aba_merchant"] = ""
    clone_registry[name] = cfg
    _save(CLONES_REGISTRY, clone_registry)
    try:
        wdir = _clone_dir(name)
        _save(os.path.join(wdir, "manual_qr.json"), {
            "enabled": pay_method == "manual",
            "photo_id": cfg.get("manual_qr_photo_id", ""),
            "info": cfg.get("manual_qr_info", ""),
        })
    except Exception as _e:
        logger.error(f"Update manual_qr.json failed for clone '{name}': {_e}")
    was_running = _clone_is_running(name)
    if was_running:
        _stop_clone(name); time.sleep(1); _spawn_clone(name, cfg)
    pay_txt = _clone_pay_txt(pay_method)
    bot.send_message(uid,
        f"✅ បានប្តូរការទូទាត់សម្រាប់ '<b>{name}</b>' ទៅជា {pay_txt}"
        + (" ហើយ restart រួច។" if was_running else " (bot នេះកំពុងបិទ — ចាប់ផ្តើមវាដើម្បីអនុវត្ត)។"),
        parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data == "cln_list")
def cb_cln_list(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    bot.answer_callback_query(call.id)
    if not clone_registry:
        bot.send_message(uid, "📭 មិនទាន់មាន Bot រងណាមួយទេ។", reply_markup=admin_kb()); return
    kb = InlineKeyboardMarkup(row_width=1)
    for nm in clone_registry:
        st = "🟢" if _clone_is_running(nm) else "🔴"
        kb.add(InlineKeyboardButton(f"{st} {nm}", callback_data=f"cln_view|{nm}", color="default"))
    bot.send_message(uid, "📋 <b>Bot រងទាំងអស់</b>", parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("cln_start|", "cln_stop|", "cln_restart|", "cln_delete|")))
def cb_cln_actions(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID or not IS_MASTER:
        bot.answer_callback_query(call.id, "🚫 គ្មានសិទ្ធិ"); return
    action, name = call.data.split("|", 1)
    cfg = clone_registry.get(name)
    if not cfg:
        bot.answer_callback_query(call.id, "រកមិនឃើញ"); return

    if action == "cln_start":
        _spawn_clone(name, cfg)
        bot.answer_callback_query(call.id, "ដំណើរការ...")
        bot.send_message(uid, f"✅ ដំណើរការ '{name}' ជោគជ័យ")
    elif action == "cln_stop":
        _stop_clone(name)
        bot.answer_callback_query(call.id, "បានបិទ")
        bot.send_message(uid, f"🛑 បានបិទ '{name}'")
    elif action == "cln_restart":
        _stop_clone(name); time.sleep(1); _spawn_clone(name, cfg)
        bot.answer_callback_query(call.id, "Restarting...")
        bot.send_message(uid, f"🔄 បាន restart '{name}'")
    elif action == "cln_delete":
        _stop_clone(name)
        clone_registry.pop(name, None)
        _save(CLONES_REGISTRY, clone_registry)
        bot.answer_callback_query(call.id, "បានលុប")
        bot.send_message(uid, f"🗑 បានលុប '{name}' ចេញពី registry (ទិន្នន័យ bot_clones/{name}/ នៅសល់)")
        return
    bot.send_message(uid, f"ស្ថានភាព '{name}':")
    cb_cln_view_inline = InlineKeyboardMarkup(row_width=2)
    if _clone_is_running(name):
        cb_cln_view_inline.add(InlineKeyboardButton("🛑 បិទ", callback_data=f"cln_stop|{name}", color="inactive"),
                                InlineKeyboardButton("🔄 Restart", callback_data=f"cln_restart|{name}", color="progress"))
    else:
        cb_cln_view_inline.add(InlineKeyboardButton("▶️ ដំណើរការ", callback_data=f"cln_start|{name}", color="active"))
    cb_cln_view_inline.add(InlineKeyboardButton("🗑️ លុប", callback_data=f"cln_delete|{name}", color="inactive"))
    bot.send_message(uid, f"🤖 {name}", reply_markup=cb_cln_view_inline)

# ═══════════════════════════════════════════════════════════
#  SETTINGS CALLBACKS — Support / Sub Admin / CamRapidPay / Welcome
# ═══════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_support:"))
def cb_set_support(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id, "🚫"); return
    lang = call.data.split(":")[1]
    bot.answer_callback_query(call.id)
    waiting[uid] = {"step": "set_support_text", "lang": lang}
    bot.send_message(uid,
        f"✏️ <b>វាយ Support Message {'(ខ្មែរ)' if lang=='kh' else '(English)'}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 HTML tags អនុញ្ញាត: <code>&lt;b&gt;</code>, <code>&lt;i&gt;</code>, <code>&lt;code&gt;</code>\n"
        f"ឬផ្ញើ <code>-</code> ដើម្បី reset ទៅ default:",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("subadmin:"))
def cb_subadmin(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id, "🚫"); return
    action = call.data.split(":")[1]
    bot.answer_callback_query(call.id)
    if action == "add":
        waiting[uid] = "subadmin_add_id"
        bot.send_message(uid,
            "➕ <b>បន្ថែម Sub Admin</b>\n━━━━━━━━━━━━━━━━━━\nផ្ញើ Telegram ID (លេខ) របស់ Sub Admin:",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "list_del":
        if not sub_admins:
            bot.send_message(uid, "📭 គ្មាន Sub Admin ទេ", reply_markup=admin_kb()); return
        kb2 = InlineKeyboardMarkup(row_width=1)
        for sa in sub_admins:
            kb2.add(InlineKeyboardButton(f"🗑️ លុប {sa}", callback_data=f"subadmin:del:{sa}", color="inactive"))
        bot.send_message(uid, "👥 <b>ជ្រើស Sub Admin ដើម្បីលុប:</b>",
                         parse_mode="HTML", reply_markup=kb2)
    else:
        # del:<id>
        parts = call.data.split(":")
        if len(parts) == 3:
            del_id = int(parts[2])
            if del_id in sub_admins:
                sub_admins.remove(del_id)
                _save(SUB_ADMIN_FILE, sub_admins)
            bot.send_message(uid, f"✅ លុប Sub Admin <code>{del_id}</code> ចេញ",
                             parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_camrapid:"))
def cb_set_camrapid(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id, "🚫"); return
    action = call.data.split(":")[1]
    bot.answer_callback_query(call.id)
    if action == "edit":
        waiting[uid] = "set_camrapid_key"
        bot.send_message(uid,
            "🔑 <b>ផ្ញើ CamRapidPay API Key ថ្មី:</b>\n"
            "ឬផ្ញើ <code>-</code> ដើម្បី reset ទៅ env/default",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "webhook":
        waiting[uid] = "set_webhook_url"
        bot.send_message(uid,
            "🌐 <b>ផ្ញើ Webhook URL ថ្មី:</b>\n"
            "ឧ: <code>https://your-domain.com/webhook/camrapid</code>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💡 CamRapidPay ទាមទារ Field នេះជានិច្ច (Required) — Bot មាន Route "
            "<code>/webhook/camrapid</code> ស្រាប់ដើម្បីទទួល។\n"
            "ឬផ្ញើ <code>-</code> ដើម្បី Reset ទៅ Auto-detect (Render URL ឬ Placeholder)",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "test":
        key = _effective_camrapid_key()
        try:
            r = http.get(CAMRAPID_CHECK, params={"api_key": key, "reference": "test_ping"}, timeout=10)
            d = r.json()
            ok = r.status_code < 500
            bot.send_message(uid,
                f"{'✅' if ok else '❌'} <b>CamRapidPay Test (Check Endpoint)</b>\n"
                f"Status: <b>{r.status_code}</b>\n"
                f"Response: <code>{str(d)[:200]}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Status 404 + \"Transaction not found\" នៅទីនេះជារឿងធម្មតា — "
                f"មិនមែនសញ្ញាបញ្ហាទេ ព្រោះ reference ដែល Test ជា Fake។ Endpoint នេះមិនមែនជាកន្លែង "
                f"Generate QR ទេ — ប្រើ 🧾 Test Generate QR ខាងក្រោមដើម្បីរកមូលហេតុពិត។</i>",
                parse_mode="HTML", reply_markup=admin_kb())
        except Exception as e:
            bot.send_message(uid, f"❌ Test failed: <code>{e}</code>",
                             parse_mode="HTML", reply_markup=admin_kb())
    elif action == "testcreate":
        key = _effective_camrapid_key()
        test_ref = f"TEST{uid}_{int(time.time())}"[:50]
        bot.send_message(uid, "⏳ កំពុង Test ការ Generate QR ជាមួយ CAMRAPID_CREATE endpoint ($0.10)...")
        try:
            payload = {"api_key": key, "amount": 0.10, "reference": test_ref,
                       "webhook_url": _effective_webhook_url()}
            r = http.post(CAMRAPID_CREATE, json=payload,
                          headers={"Content-Type": "application/json", "Accept": "application/json"},
                          timeout=15)
            try:
                d = r.json()
            except Exception:
                d = {"raw_text": r.text[:300]}
            ok = isinstance(d, dict) and d.get("success")
            bot.send_message(uid,
                f"{'✅' if ok else '❌'} <b>CamRapidPay Test (Create Endpoint — QR ពិតប្រាកដ)</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🌐 URL: <code>{CAMRAPID_CREATE}</code>\n"
                f"🔑 Key: <code>{key[:8]}...{key[-4:] if len(key)>12 else ''}</code>\n"
                f"📡 HTTP Status: <b>{r.status_code}</b>\n"
                f"📋 Response: <code>{str(d)[:500]}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                + ("✅ QR គួរតែចេញបានធម្មតា!" if ok else
                   "❌ នេះជាមូលហេតុពិតប្រាកដដែល QR មិនចេញ — សូមអានសារ Error ខាងលើ "
                   "(ឧ. \"Invalid API Key\", \"Insufficient balance\", \"Merchant not found\" ។ល។)"),
                parse_mode="HTML", reply_markup=admin_kb())
        except Exception as e:
            bot.send_message(uid,
                f"❌ <b>Connection Failed</b>\n<code>{e}</code>\n\n"
                f"💡 ប្រហែល Network/Egress ត្រូវបាន Block លើ Server ដែល Deploy Bot នេះ "
                f"(Render/VPS) ពី <code>pay.camrapidpay.com</code>",
                parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_aba:"))
def cb_set_aba(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id, "🚫"); return
    action = call.data.split(":")[1]
    bot.answer_callback_query(call.id)
    if action == "edit_key":
        waiting[uid] = "set_aba_key"
        bot.send_message(uid,
            "🔑 <b>ផ្ញើ ABA PayWay Profile Key ថ្មី</b> (khmer-system.com/operator/profile):\n"
            "ឬផ្ញើ <code>-</code> ដើម្បី reset ទៅ env/default",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "edit_merchant":
        waiting[uid] = "set_aba_merchant"
        bot.send_message(uid,
            "🏪 <b>ផ្ញើ ABA PayWay Merchant ID ថ្មី</b> (ឧ. <code>r72mCt</code>):\n"
            "ឬផ្ញើ <code>-</code> ដើម្បី reset ទៅ env/default",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "testcreate":
        bot.send_message(uid, "⏳ កំពុង Test Generate QR ជាមួយ ABA PayWay ($0.10)...")
        test_data = _aba_create(uid, 0.10, f"tg{uid}")
        ok = bool(test_data)
        bot.send_message(uid,
            f"{'✅' if ok else '❌'} <b>ABA PayWay Test (Generate QR)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🌐 URL: <code>{ABA_CREATE_URL}</code>\n"
            f"📋 Response: <code>{str(test_data if ok else _last_aba_error)[:500]}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            + ("✅ QR គួរតែចេញបានធម្មតា!" if ok else
               "❌ សូមអានសារ Error ខាងលើ (ឧ. Key/Merchant ID មិនត្រឹមត្រូវ, service down ។ល។)"),
            parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_bakong:"))
def cb_set_bakong(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id, "🚫"); return
    action = call.data.split(":")[1]
    bot.answer_callback_query(call.id)
    if action == "edit":
        waiting[uid] = "set_bakong_token"
        bot.send_message(uid,
            "🏦 <b>ផ្ញើ Bakong Developer Token ថ្មី:</b>\n"
            "(យកពី https://api-bakong.nbc.gov.kh/register/)\n"
            "ឬផ្ញើ <code>-</code> ដើម្បី reset ទៅ env/default",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "reset":
        bakong_cfg["token"] = ""
        _save(BAKONG_CFG_FILE, bakong_cfg)
        bot.send_message(uid, "✅ Bakong Token reset ទៅ env/default!",
                         parse_mode="HTML", reply_markup=admin_kb())
    elif action == "test":
        tok = _effective_bakong_token()
        if not tok:
            bot.send_message(uid, "⚠️ មិនទាន់កំណត់ Bakong Token ទេ!",
                             parse_mode="HTML", reply_markup=admin_kb()); return
        # KHQR ខ្សែសាកល្បង (generic Bakong test string) — គ្រាន់ត្រួតពិនិត្យថា token/API ដំណើរការ
        test_dl = _bakong_deeplink("00020101021129180014A00000067701011201150096600123456789530384054031005802KH5910TEST MERCHANT6010PHNOM PENH62070503***6304ABCD", uid)
        ok = bool(test_dl)
        bot.send_message(uid,
            f"{'✅' if ok else '❌'} <b>Bakong Deep Link Test</b>\n"
            f"{'Deep link: <code>' + test_dl + '</code>' if ok else 'Token invalid ឬ API មិនឆ្លើយតប — ពិនិត្យ log'}",
            parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_welcome:"))
def cb_set_welcome(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id, "🚫"); return
    action = call.data.split(":")[1]
    bot.answer_callback_query(call.id)
    if action == "text":
        waiting[uid] = "set_welcome_msg_text"
        bot.send_message(uid,
            "📝 <b>វាយ Welcome Message ថ្មី:</b>\n"
            "💡 ប្រើ <code>{}</code> ដើម្បីដាក់ balance\n"
            "ឬផ្ញើ <code>-</code> ដើម្បី reset ទៅ default:",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "reset":
        welcome_cfg.pop("custom_msg", None)
        _save(WELCOME_SETTINGS_FILE, welcome_cfg)
        bot.send_message(uid, "✅ Welcome Message reset ទៅ default!", reply_markup=admin_kb())
# ═══════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("emojimenu:"))
def cb_emojimenu(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "🚫 Master Admin only!"); return
    action = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)
    if action == "set":
        waiting.pop(uid, None)   # ជម្រះ state ចាស់ ពេលបើក grid ថ្មី
        missing = [ch for ch, v in EMOJI_MAP.items() if not v]
        if not missing:
            bot.send_message(uid, "🎉 <b>Emoji ទាំងអស់បានកំណត់រួច 100% ហើយ!</b>",
                parse_mode="HTML", reply_markup=admin_kb()); return
        bot.send_message(uid,
            "✏️ <b>ជ្រើស Emoji ដែលចង់កំណត់</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👇 ចុចលើ emoji ណាមួយខាងក្រោម រួចផ្ញើ ឬ Forward Premium version របស់វា\n"
            "<i>bot នឹងចាប់យក custom_emoji_id ដោយស្វ័យប្រវត្តិ — មិនចាំបាច់ដឹង ID ដោយខ្លួនឯងទេ</i>\n\n"
            f"📊 កំណត់រួច: {sum(1 for v in EMOJI_MAP.values() if v)}/{len(EMOJI_MAP)} — នៅសល់ {len(missing)}",
            parse_mode="HTML", reply_markup=missing_emoji_kb())
    elif action == "change":
        waiting.pop(uid, None)   # ជម្រះ state ចាស់ ពេលបើក grid ថ្មី
        done_n = sum(1 for v in EMOJI_MAP.values() if v)
        bot.send_message(uid,
            "🔄 <b>ប្តូរ Premium Emoji ដែលមានស្រាប់</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👇 ចុចលើ Emoji ណាមួយខាងក្រោម (✅ = មានស្រាប់, ⬜ = មិនទាន់កំណត់)\n"
            "រួចផ្ញើ ឬ Forward Premium version ថ្មី — Bot នឹងជំនួស ID ចាស់ភ្លាមៗ\n\n"
            f"📊 កំណត់រួច: {done_n}/{len(EMOJI_MAP)}",
            parse_mode="HTML", reply_markup=all_emoji_kb())
    elif action == "menu":
        waiting.pop(uid, None)   # ជម្រះ state ចាស់ (ដូចជា await_setemoji_single) បើនៅសល់
        done_n = sum(1 for v in EMOJI_MAP.values() if v)
        bot.send_message(uid,
            f"😊 <b>Premium Emoji Settings</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"កំណត់រួច: <b>{done_n}/{len(EMOJI_MAP)}</b>\n\n"
            f"ជ្រើសសកម្មភាព:",
            parse_mode="HTML", reply_markup=emoji_menu_kb())
    elif action == "setmulti":
        waiting[uid] = "await_setemojis"
        missing = [ch for ch, v in EMOJI_MAP.items() if not v]
        preview = " ".join(missing[:40]) + (" ..." if len(missing) > 40 else "")
        bot.send_message(uid,
            "📋 <b>កំណត់ Emoji ច្រើនម្តង (Advanced)</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📤 ផ្ញើ ឬ Forward សារដែលមាន Premium Emoji ច្រើនក្នុងសារតែមួយ\n"
            "<i>(លំដាប់ណាក៏បាន — ផ្ញើជាប់ៗគ្នាបានច្រើនសារដោយមិនចាំបាច់ចុច Menu ម្តងទៀត)</i>\n\n"
            f"📊 កំណត់រួចហើយ: {sum(1 for v in EMOJI_MAP.values() if v)}/{len(EMOJI_MAP)} — នៅសល់ {len(missing)}\n"
            + (f"⬜ នៅសល់: {preview}\n\n" if missing else "\n") +
            "✕ Cancel ពេលរួចរាល់",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "list":
        bot.send_message(uid, _emoji_status_text(), parse_mode="HTML", reply_markup=admin_kb())
    elif action == "preview":
        text, entities, n = _build_emoji_preview()
        if n == 0:
            bot.send_message(uid, "⚠️ មិនទាន់មាន Emoji ណាមួយបានកំណត់ទេ។",
                reply_markup=emoji_menu_kb())
            return
        bot.send_message(uid,
            f"🎨 <b>មើលសាកល្បង Premium Emoji</b> ({n} icon)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👇 នេះជារូបរាងជាក់ស្តែងនៃ icon ដែលបានកំណត់:",
            parse_mode="HTML")
        bot.send_message(uid, text, entities=entities, reply_markup=emoji_menu_kb())
    elif action == "id":
        waiting[uid] = "await_emojiid"
        bot.send_message(uid,
            "🆔 <b>យក Emoji ID</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📤 ផ្ញើ ឬ Forward សារដែលមាន Premium Emoji មកទីនេះ",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("emojipick:"))
def cb_emojipick(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id, "🚫 Master Admin only!"); return
    ch = call.data.split(":", 1)[1]
    ch = _emoji_key_lookup(ch) or ch
    if ch not in EMOJI_MAP:
        bot.answer_callback_query(call.id, "❌ Emoji នេះលែងមាន!"); return
    bot.answer_callback_query(call.id)
    waiting[uid] = {"step": "await_setemoji_single", "char": ch}
    bot.send_message(uid,
        f"✏️ <b>កំណត់ Premium Emoji សម្រាប់ {ch}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📤 ផ្ញើ ឬ Forward សារដែលមាន Premium version របស់ {ch} ចូលទីនេះ\n"
        f"<i>bot នឹងចាប់យក ID ដោយស្វ័យប្រវត្តិ ហើយភ្ជាប់ទៅ {ch} ភ្លាមៗ</i>",
        parse_mode="HTML", reply_markup=cancel_kb())

def _do_broadcast(admin_uid, message):
    waiting.pop(admin_uid, None)
    sent = failed = 0
    for u_id in list(users_db.keys()):
        try:
            if message.photo:
                bot.send_photo(int(u_id), message.photo[-1].file_id, caption=message.caption or "")
            elif message.video:
                bot.send_video(int(u_id), message.video.file_id, caption=message.caption or "")
            else:
                bot.send_message(int(u_id), message.text or "", parse_mode="HTML")
            sent += 1
        except: failed += 1
        time.sleep(0.05)
    bot.send_message(admin_uid,
        f"📢 <b>ផ្សព្វផ្សាយរួចរាល់!</b>\n✅ បានផ្ញើ: {sent} | ❌ បរាជ័យ: {failed}",
        parse_mode="HTML", reply_markup=admin_kb())

# ═══════════════════════════════════════════════════════════
#  PHOTO HANDLER
# ═══════════════════════════════════════════════════════════
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    uid = message.chat.id
    step = waiting.get(uid)

    # ── User (រួមទាំង Admin បើសាកល្បង) ផ្ញើភស្តុតាង ដាក់លុយដោយដៃ ──────
    if isinstance(step, dict) and step.get("step") == "await_manual_dep_proof":
        amount   = float(step.get("amount", 0))
        uid_str  = str(uid)
        dep_id   = _gen_manual_dep_id()
        proof_id = message.photo[-1].file_id
        manual_deps[dep_id] = {
            "uid": uid_str, "amount": amount, "proof_photo_id": proof_id,
            "status": "pending", "ts": int(time.time()),
        }
        _save(MANUAL_DEP_FILE, manual_deps)
        waiting.pop(uid, None)
        bot.send_message(uid,
            f"⏳ <b>សំណើដាក់លុយរបស់អ្នកកំពុងត្រូវបានពិនិត្យ!</b>\n"
            f"💰 ចំនួន: <b>${amount:.2f}</b>\n"
            f"📌 Ref: <code>{dep_id}</code>\n\n"
            f"Admin នឹងអនុម័តក្នុងពេលឆាប់ៗនេះ 🙏",
            parse_mode="HTML", reply_markup=main_kb(uid))
        try:
            u = users_db.get(uid_str, {})
            name = u.get("name") or u.get("username") or "?"
            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("✅ អនុម័ត", callback_data=f"mdep:ok:{dep_id}", color="success"),
                InlineKeyboardButton("❌ បដិសេធ", callback_data=f"mdep:no:{dep_id}", color="danger"),
            )
            bot.send_photo(ADMIN_ID, proof_id,
                caption=f"🧾 <b>សំណើដាក់លុយដោយដៃ ថ្មី!</b>\n"
                        f"👤 {name} (<code>{uid_str}</code>)\n"
                        f"💰 ចំនួន: <b>${amount:.2f}</b>\n"
                        f"📌 Ref: <code>{dep_id}</code>",
                parse_mode="HTML", reply_markup=kb)
        except Exception as _e:
            logger.debug(f"[silent] {_e}")
        return

    if uid == ADMIN_ID and step == "await_manual_qr_photo":
        manual_qr_cfg["photo_id"] = message.photo[-1].file_id
        _save(MANUAL_QR_FILE, manual_qr_cfg)
        waiting.pop(uid, None)
        bot.send_message(uid, "✅ រូប QR បានកំណត់ជោគជ័យ!", parse_mode="HTML",
                          reply_markup=manual_qr_admin_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "newbot_manual_qr_photo":
        photo_id = message.photo[-1].file_id
        waiting[uid] = {**step, "step": "newbot_manual_qr_info", "manual_qr_photo_id": photo_id}
        bot.send_message(uid,
            f"{_step_label(6, 8)} — វាយ <b>ព័ត៌មានបន្ថែម</b> ខាងក្រោម QR (ឧ. ឈ្មោះគណនី/លេខទូរស័ព្ទ)\n"
            "ឬផ្ញើ <code>-</code> បើគ្មាន:",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "cln_pay_qr_photo":
        photo_id = message.photo[-1].file_id
        waiting[uid] = {**step, "step": "cln_pay_qr_info", "manual_qr_photo_id": photo_id}
        bot.send_message(uid,
            "វាយ <b>ព័ត៌មានបន្ថែម</b> ខាងក្រោម QR (ឧ. ឈ្មោះគណនី/លេខទូរស័ព្ទ)\n"
            "ឬផ្ញើ <code>-</code> បើគ្មាន:",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID:
        # ── Premium Emoji flows also accept forwarded photos (caption emoji) ──
        if isinstance(step, dict) and step.get("step") == "await_setemoji_single":
            ch = step["char"]
            found = _extract_custom_emoji(message)
            if not found:
                bot.send_message(uid,
                    f"❌ រកមិនឃើញ premium emoji ក្នុងសារនោះទេ។ ផ្ញើ Emoji ថ្មី ឬ ✕ Cancel។",
                    parse_mode="HTML", reply_markup=cancel_kb())
                return
            # ✅ ទទួល emoji ណាក៏បាន (មិនតម្រូវឲ្យដូច ch ដើមទេ — តាមសំណើអ្នកប្រើ)
            match_eid = found[0][1]
            EMOJI_MAP[ch] = match_eid
            _save(EMOJI_FILE, EMOJI_MAP)
            waiting.pop(uid, None)
            remaining = [c for c, v in EMOJI_MAP.items() if not v]
            done_n = sum(1 for v in EMOJI_MAP.values() if v)
            if remaining:
                bot.send_message(uid,
                    f"✅ {ch} → <code>{match_eid}</code> កំណត់ជោគជ័យ!\n"
                    f"📊 {done_n}/{len(EMOJI_MAP)} — នៅសល់ {len(remaining)}\n\n"
                    f"👇 ជ្រើស emoji បន្ត:",
                    parse_mode="HTML", reply_markup=missing_emoji_kb())
            else:
                bot.send_message(uid,
                    f"✅ {ch} → <code>{match_eid}</code> កំណត់ជោគជ័យ!\n\n"
                    f"🎉 <b>រួចរាល់! Emoji ទាំងអស់បានកំណត់ 100%!</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            return
        if step == "await_setemojis":
            report = _apply_setemojis(message)
            remaining = sum(1 for v in EMOJI_MAP.values() if not v)
            if not report:
                bot.send_message(uid,
                    "❌ រកមិនឃើញ premium/custom emoji ក្នុងសារនោះទេ។ ផ្ញើសារផ្សេងទៀត ឬ ✕ Cancel។",
                    parse_mode="HTML", reply_markup=cancel_kb())
                return
            if remaining == 0:
                waiting.pop(uid, None)
                bot.send_message(uid,
                    report + "\n\n🎉 <b>រួចរាល់! Emoji ទាំងអស់បានកំណត់ 100%!</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            else:
                missing_preview = " ".join(ch for ch, v in EMOJI_MAP.items() if not v)[:200]
                bot.send_message(uid,
                    report + f"\n\n📤 ផ្ញើសារបន្តទៀត ({remaining} នៅសល់) ឬ ✕ Cancel ពេលរួច:\n⬜ {missing_preview}",
                    parse_mode="HTML", reply_markup=cancel_kb())
            return
        if step == "await_emojiid":
            report = _emojiid_text(message)
            if report:
                bot.send_message(uid, report + "\n\n📤 ផ្ញើសារបន្តទៀត ឬ ✕ Cancel ពេលរួច:",
                    parse_mode="HTML", reply_markup=cancel_kb())
            else:
                bot.send_message(uid,
                    "❌ រកមិនឃើញ premium/custom emoji ក្នុងសារនោះទេ។ ផ្ញើសារផ្សេងទៀត ឬ ✕ Cancel។",
                    parse_mode="HTML", reply_markup=cancel_kb())
            return
        if step == "broadcast_msg":
            _do_broadcast(uid, message)
        elif step == "set_welcome_photo":
            file_id = message.photo[-1].file_id
            _save_welcome_photo(file_id)
            waiting.pop(uid, None)
            bot.send_message(uid,
                "✅ <b>Welcome Photo បានរក្សា!</b>\n"
                "រូបនេះនឹងបង្ហាញពេល User ចុច /start",
                parse_mode="HTML", reply_markup=admin_kb())
        return

# ═══════════════════════════════════════════════════════════
#  VIDEO HANDLER — Admin ផ្ញើវីដេអូបង្រៀន (Tutorial Video) ដែលនឹង
#  បង្ហាញដល់ User ពេលចុច 💡 របៀបប្រើប្រាស់ ក្នុង Main Menu ។
# ═══════════════════════════════════════════════════════════
@bot.message_handler(content_types=["video"])
def handle_video(message):
    uid  = message.chat.id
    step = waiting.get(uid)
    if uid != ADMIN_ID and uid not in sub_admins:
        return
    if step == "set_tutorial_video":
        file_id = message.video.file_id
        _save_tutorial_video(file_id)
        waiting.pop(uid, None)
        bot.send_message(uid,
            "✅ <b>វីដេអូបង្រៀនបានរក្សា!</b>\n"
            "វីដេអូនេះនឹងបង្ហាញពេល User ចុច 💡 របៀបប្រើប្រាស់",
            parse_mode="HTML", reply_markup=admin_kb())

# ═══════════════════════════════════════════════════════════
#  STICKER HANDLER — ចាំបាច់សម្រាប់ Premium Emoji ដែលផ្ញើមកជា
#  content_type="sticker" (sticker.type == "custom_emoji") ។ ដោយគ្មាន
#  content_type="sticker" (sticker.type == "custom_emoji") ។ ដោយគ្មាន
#  handler នេះ សារបែបនេះនឹងមិនចូល photo handler ក៏មិនចូល handle_msg
#  (ដែល default content_types=['text'] តែប៉ុណ្ណោះ ព្រោះមិនបានបញ្ជាក់
#  content_types ច្បាស់លាស់) ធ្វើឲ្យ Bot ស្ងាត់ស្ងៀមទាំងស្រុងគ្មាន reply
#  ═══════════════════════════════════════════════════════════
@bot.message_handler(content_types=["sticker"])
def handle_sticker(message):
    uid = message.chat.id
    step = waiting.get(uid)
    if uid != ADMIN_ID:
        return
    if isinstance(step, dict) and step.get("step") == "await_setemoji_single":
        ch = step["char"]
        found = _extract_custom_emoji(message)
        if not found:
            bot.send_message(uid,
                f"❌ រកមិនឃើញ premium emoji ក្នុងសារនោះទេ។ ផ្ញើ Emoji ថ្មី ឬ ✕ Cancel។",
                parse_mode="HTML", reply_markup=cancel_kb())
            return
        # ✅ ទទួល emoji ណាក៏បាន (មិនតម្រូវឲ្យដូច ch ដើមទេ — តាមសំណើអ្នកប្រើ)
        match_eid = found[0][1]
        EMOJI_MAP[ch] = match_eid
        _save(EMOJI_FILE, EMOJI_MAP)
        waiting.pop(uid, None)
        remaining = [c for c, v in EMOJI_MAP.items() if not v]
        done_n = sum(1 for v in EMOJI_MAP.values() if v)
        if remaining:
            bot.send_message(uid,
                f"✅ {ch} → <code>{match_eid}</code> កំណត់ជោគជ័យ!\n"
                f"📊 {done_n}/{len(EMOJI_MAP)} — នៅសល់ {len(remaining)}\n\n"
                f"👇 ជ្រើស emoji បន្ត:",
                parse_mode="HTML", reply_markup=missing_emoji_kb())
        else:
            bot.send_message(uid,
                f"✅ {ch} → <code>{match_eid}</code> កំណត់ជោគជ័យ!\n\n"
                f"🎉 <b>រួចរាល់! Emoji ទាំងអស់បានកំណត់ 100%!</b>",
                parse_mode="HTML", reply_markup=admin_kb())
        return
    if step == "await_setemojis":
        report = _apply_setemojis(message)
        remaining = sum(1 for v in EMOJI_MAP.values() if not v)
        if not report:
            bot.send_message(uid,
                "❌ រកមិនឃើញ premium/custom emoji ក្នុងសារនោះទេ។ ផ្ញើសារផ្សេងទៀត ឬ ✕ Cancel។",
                parse_mode="HTML", reply_markup=cancel_kb())
            return
        if remaining == 0:
            waiting.pop(uid, None)
            bot.send_message(uid,
                report + "\n\n🎉 <b>រួចរាល់! Emoji ទាំងអស់បានកំណត់ 100%!</b>",
                parse_mode="HTML", reply_markup=admin_kb())
        else:
            missing_preview = " ".join(ch for ch, v in EMOJI_MAP.items() if not v)[:200]
            bot.send_message(uid,
                report + f"\n\n📤 ផ្ញើសារបន្តទៀត ({remaining} នៅសល់) ឬ ✕ Cancel ពេលរួច:\n⬜ {missing_preview}",
                parse_mode="HTML", reply_markup=cancel_kb())
        return
    if step == "await_emojiid":
        report = _emojiid_text(message)
        if report:
            bot.send_message(uid, report + "\n\n📤 ផ្ញើសារបន្តទៀត ឬ ✕ Cancel ពេលរួច:",
                parse_mode="HTML", reply_markup=cancel_kb())
        else:
            bot.send_message(uid,
                "❌ រកមិនឃើញ premium/custom emoji ក្នុងសារនោះទេ។ ផ្ញើសារផ្សេងទៀត ឬ ✕ Cancel។",
                parse_mode="HTML", reply_markup=cancel_kb())
        return

# ═══════════════════════════════════════════════════════════
#  MAIN MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: True)
def handle_msg(message):
    uid     = message.chat.id
    uid_str = str(uid)
    text    = message.text or ""
    # ── Restore stripped-emoji text ──
    # បើ text នេះជា button ដែលមាន premium emoji icon (KeyboardButton.to_dict()
    # បានកាត់ emoji unicode ចេញពី label ដើម្បីកុំឲ្យស្ទួន icon), Telegram នឹង
    # ត្រឡប់តែ text ដែលកាត់រួច (គ្មាន emoji) មកវិញ។ ត្រូវ restore ទៅ text ដើម
    # (មាន emoji) វិញនៅទីនេះ មុននឹង logic ខាងក្រោម match text == / text in (...)
    # ណាមួយ — បើមិនធ្វើដូច្នេះទេ ប៊ូតុងទាំងអស់ដែលកំណត់ emoji premium នឹងធ្លាក់
    # ចូល fallback "មិនស្គាល់ button" រាល់ដង។
    text    = _STRIPPED_TEXT_MAP.get(text, text)
    lang    = get_lang(uid)
    step    = waiting.get(uid)

    _track_user(message)

    if is_banned(uid) and uid != ADMIN_ID:
        bot.send_message(uid, t(uid, "banned")); return

    # ── Cancel ──
    if text == "✕ Cancel":
        waiting.pop(uid, None)
        bot.send_message(uid, t(uid, "cancel_ok"),
                         reply_markup=main_kb(uid) if uid not in sub_admins and uid != ADMIN_ID
                         else (admin_kb() if uid == ADMIN_ID else sub_admin_kb()))
        return

    # ════════════════════════════════════════
    #  ADMIN SECTION
    # ════════════════════════════════════════
    if uid == ADMIN_ID or uid in sub_admins:
        _is_master_admin = (uid == ADMIN_ID)  # gate for master-only features

        # ── Premium Emoji button flow (replaces manual /setemojis, /emojiid) ──
        if isinstance(step, dict) and step.get("step") == "await_setemoji_single" and uid == ADMIN_ID:
            ch = step["char"]
            found = _extract_custom_emoji(message)
            if not found:
                bot.send_message(uid,
                    f"❌ រកមិនឃើញ premium emoji ក្នុងសារនោះទេ។ ផ្ញើ Emoji ថ្មី ឬ ✕ Cancel។",
                    parse_mode="HTML", reply_markup=cancel_kb())
                return  # stay in loop, waiting untouched
            # ✅ ទទួល emoji ណាក៏បាន (មិនតម្រូវឲ្យដូច ch ដើមទេ — តាមសំណើអ្នកប្រើ)
            match_eid = found[0][1]
            EMOJI_MAP[ch] = match_eid
            _save(EMOJI_FILE, EMOJI_MAP)
            waiting.pop(uid, None)
            remaining = [c for c, v in EMOJI_MAP.items() if not v]
            done_n = sum(1 for v in EMOJI_MAP.values() if v)
            if remaining:
                bot.send_message(uid,
                    f"✅ {ch} → <code>{match_eid}</code> កំណត់ជោគជ័យ!\n"
                    f"📊 {done_n}/{len(EMOJI_MAP)} — នៅសល់ {len(remaining)}\n\n"
                    f"👇 ជ្រើស emoji បន្ត:",
                    parse_mode="HTML", reply_markup=missing_emoji_kb())
            else:
                bot.send_message(uid,
                    f"✅ {ch} → <code>{match_eid}</code> កំណត់ជោគជ័យ!\n\n"
                    f"🎉 <b>រួចរាល់! Emoji ទាំងអស់បានកំណត់ 100%!</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "await_setemojis" and uid == ADMIN_ID:
            report = _apply_setemojis(message)
            remaining = sum(1 for v in EMOJI_MAP.values() if not v)
            if not report:
                bot.send_message(uid,
                    "❌ រកមិនឃើញ premium/custom emoji ក្នុងសារនោះទេ។ ផ្ញើសារផ្សេងទៀត ឬ ✕ Cancel។",
                    parse_mode="HTML", reply_markup=cancel_kb())
                return  # stay in loop, waiting untouched
            if remaining == 0:
                waiting.pop(uid, None)
                bot.send_message(uid,
                    report + "\n\n🎉 <b>រួចរាល់! Emoji ទាំងអស់បានកំណត់ 100%!</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            else:
                # stay in the flow so admin can keep forwarding messages back-to-back
                missing_preview = " ".join(ch for ch, v in EMOJI_MAP.items() if not v)[:200]
                bot.send_message(uid,
                    report + f"\n\n📤 ផ្ញើសារបន្តទៀត ({remaining} នៅសល់) ឬ ✕ Cancel ពេលរួច:\n⬜ {missing_preview}",
                    parse_mode="HTML", reply_markup=cancel_kb())
            return

        if step == "await_emojiid" and uid == ADMIN_ID:
            report = _emojiid_text(message)
            if report:
                bot.send_message(uid, report + "\n\n📤 ផ្ញើសារបន្តទៀត ឬ ✕ Cancel ពេលរួច:",
                    parse_mode="HTML", reply_markup=cancel_kb())
            else:
                bot.send_message(uid,
                    "❌ រកមិនឃើញ premium/custom emoji ក្នុងសារនោះទេ។ ផ្ញើសារផ្សេងទៀត ឬ ✕ Cancel។",
                    parse_mode="HTML", reply_markup=cancel_kb())
            return  # stay in loop, waiting untouched

        # Admin commands
        if text.startswith("/addbal"):
            parts = text.split()
            if len(parts) < 3:
                bot.send_message(uid, "ប្រើ: /addbal UID AMOUNT"); return
            try:
                target = parts[1]; amt = float(parts[2])
                add_bal(int(target), amt)
                bot.send_message(uid,
                    f"✅ +${amt:.2f} → <code>{target}</code>\n💳 Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"✅ Admin បន្ថែមលុយ! +${amt:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except Exception as _e: logger.debug(f"[silent] {_e}")
            except: bot.send_message(uid, "❌ Format ខុស")
            return

        if text.startswith("/deductbal"):
            parts = text.split()
            if len(parts) < 3:
                bot.send_message(uid, "ប្រើ: /deductbal UID AMOUNT"); return
            try:
                target = parts[1]; amt = float(parts[2])
                cur = bal(int(target))
                ded = min(amt, cur)
                ded_bal(int(target), ded)
                bot.send_message(uid,
                    f"✅ -${ded:.2f} → <code>{target}</code>\n💳 Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except: bot.send_message(uid, "❌ Format ខុស")
            return

        # ── /newbot — បង្កើត Bot ថ្មីដោយផ្ទាល់ខាងក្នុង Telegram (តែ master bot) ──
        if text == "/newbot":
            if not IS_MASTER:
                bot.send_message(uid, "🚫 Bot នេះជា bot រង — មិនអាចបង្កើត bot ថ្មីបានទេ។ សូមប្រើ bot ដើម។")
                return
            waiting[uid] = {"step": "newbot_name"}
            bot.send_message(uid,
                "🤖 <b>បង្កើត Bot ថ្មី</b>\n\n"
                f"{_step_label(1)} — វាយឈ្មោះសម្គាល់ bot នេះ (អក្សរ/លេខ/_ តែប៉ុណ្ណោះ គ្មានគម្លាត)\n"
                "ឧ. <code>shop2</code>, <code>freefire_shop</code>\n\n✕ Cancel ដើម្បីបោះបង់",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        # ── /mybots — មើល/គ្រប់គ្រង bot ដែលបានបង្កើតទាំងអស់ (តែ master bot) ──
        if text == "/mybots":
            if not IS_MASTER:
                bot.send_message(uid, "🚫 Bot នេះជា bot រង — មិនមាន bot រងផ្សេងទេ។")
                return
            if not clone_registry:
                bot.send_message(uid, "📭 មិនទាន់មាន Bot រងណាមួយត្រូវបានបង្កើតទេ។ ប្រើ /newbot ដើម្បីបង្កើត។")
                return
            kb = InlineKeyboardMarkup(row_width=1)
            for nm in clone_registry:
                status = "🟢" if _clone_is_running(nm) else "🔴"
                kb.add(InlineKeyboardButton(f"{status} {nm}", callback_data=f"cln_view|{nm}", color="active" if _clone_is_running(nm) else "inactive"))
            bot.send_message(uid, "📋 <b>Bot រងទាំងអស់</b>\n🟢 = ដំណើរការ  🔴 = បិទ",
                              parse_mode="HTML", reply_markup=kb)
            return

        # ── Waiting steps for /newbot wizard ──
        if isinstance(step, dict) and step.get("step") == "newbot_name":
            safe = "".join(ch for ch in text.strip() if (ch.isascii() and ch.isalnum()) or ch == "_")
            if not safe:
                bot.send_message(uid, "⚠️ ឈ្មោះមិនត្រឹមត្រូវ សូមវាយម្តងទៀត:", reply_markup=cancel_kb()); return
            if safe in clone_registry:
                bot.send_message(uid, "⚠️ ឈ្មោះនេះមានរួចហើយ សូមប្រើឈ្មោះផ្សេង:", reply_markup=cancel_kb()); return
            waiting[uid] = {"step": "newbot_token", "name": safe}
            bot.send_message(uid, f"{_step_label(2)} — វាយ <b>Bot Token</b> (ពី @BotFather):",
                              parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "newbot_token":
            tok = text.strip()
            if ":" not in tok or len(tok) < 20:
                bot.send_message(uid, "⚠️ Token មិនត្រឹមត្រូវ សូមផ្ញើម្តងទៀត:", reply_markup=cancel_kb()); return
            waiting[uid] = {**step, "step": "newbot_admin", "token": tok}
            bot.send_message(uid, f"{_step_label(3)} — វាយ <b>Admin Telegram ID</b> របស់អ្នកគ្រប់គ្រង bot នេះ (លេខ):",
                              parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "newbot_admin":
            if not text.strip().isdigit():
                bot.send_message(uid, "⚠️ សូមផ្ញើជាលេខតែប៉ុណ្ណោះ:", reply_markup=cancel_kb()); return
            waiting[uid] = {**step, "step": "newbot_paymethod", "new_admin_id": int(text.strip())}
            kb = InlineKeyboardMarkup(row_width=1)
            kb.add(InlineKeyboardButton("🔄 CamRapidPay QR ស្វ័យប្រវត្តិ (7 ជំហាន)", callback_data="newbot_pay|auto", color="active"))
            kb.add(InlineKeyboardButton("🏦 ABA PayWay ស្វ័យប្រវត្តិ (8 ជំហាន)", callback_data="newbot_pay|aba", color="active"))
            kb.add(InlineKeyboardButton("🖼 QR ដាក់ដោយដៃ Manual (8 ជំហាន)", callback_data="newbot_pay|manual", color="progress"))
            bot.send_message(uid,
                f"{_step_label(4)} — ជ្រើសរើស <b>របៀបទទួលទឹក</b> សម្រាប់ bot នេះ:\n\n"
                "🔄 <b>CamRapidPay Auto</b> — ប្រើ API Key បង្កើត QR ស្វ័យប្រវត្តិ (ត្រូវការ API Key) — សរុប 7 ជំហាន\n"
                "🏦 <b>ABA PayWay Auto</b> — ប្រើ Profile Key + Merchant ID (KHMER SYSTEM) បង្កើត QR ស្វ័យប្រវត្តិ — សរុប 8 ជំហាន\n"
                "🖼 <b>Manual QR</b> — Upload រូប QR (Bakong KHQR) ដាក់ដោយដៃ គ្មានត្រូវការ API Key — សរុប 8 ជំហាន",
                parse_mode="HTML", reply_markup=kb)
            return

        if isinstance(step, dict) and step.get("step") == "newbot_key":
            key = text.strip()
            if len(key) < 10:
                bot.send_message(uid, "⚠️ API Key ខ្លីពេក សូមផ្ញើម្តងទៀត:", reply_markup=cancel_kb()); return
            name = step["name"]; tok = step["token"]; new_admin = step["new_admin_id"]
            port = _next_clone_port()
            masked_tok = tok[:10] + "..." + tok[-4:]
            masked_key = key[:6] + "..." + key[-4:]
            waiting[uid] = {**step, "step": "newbot_display", "camrapid_key": key, "port": port}
            bot.send_message(uid,
                f"{_step_label(6, 7)} — វាយ <b>ឈ្មោះ bot</b> ដែលបង្ហាញដល់អ្នកប្រើ (ឧ. <code>Jak Like Shop</code>)\n"
                "ឬផ្ញើ <code>-</code> ដើម្បីប្រើឈ្មោះ internal (<code>"
                + step["name"] + "</code>) ជំនួស:",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "newbot_aba_key":
            key = text.strip()
            if len(key) < 10:
                bot.send_message(uid, "⚠️ Profile Key ខ្លីពេក សូមផ្ញើម្តងទៀត:", reply_markup=cancel_kb()); return
            waiting[uid] = {**step, "step": "newbot_aba_merchant", "aba_key": key}
            bot.send_message(uid,
                f"{_step_label(6, 8)} — វាយ <b>ABA Merchant ID</b> សម្រាប់ bot នេះ (ឧ. <code>r72mCt</code>):",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "newbot_aba_merchant":
            merchant = text.strip()
            if not merchant:
                bot.send_message(uid, "⚠️ Merchant ID មិនត្រឹមត្រូវ សូមផ្ញើម្តងទៀត:", reply_markup=cancel_kb()); return
            name = step["name"]
            port = _next_clone_port()
            waiting[uid] = {**step, "step": "newbot_display", "aba_merchant": merchant, "port": port}
            bot.send_message(uid,
                f"{_step_label(7, 8)} — វាយ <b>ឈ្មោះ bot</b> ដែលបង្ហាញដល់អ្នកប្រើ (ឧ. <code>Jak Like Shop</code>)\n"
                "ឬផ្ញើ <code>-</code> ដើម្បីប្រើឈ្មោះ internal (<code>"
                + name + "</code>) ជំនួស:",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "newbot_manual_qr_info":
            raw = text.strip()
            info = "" if raw == "-" else raw
            port = _next_clone_port()
            waiting[uid] = {**step, "step": "newbot_display", "manual_qr_info": info, "port": port}
            bot.send_message(uid,
                f"{_step_label(7, 8)} — វាយ <b>ឈ្មោះ bot</b> ដែលបង្ហាញដល់អ្នកប្រើ (ឧ. <code>Jak Like Shop</code>)\n"
                "ឬផ្ញើ <code>-</code> ដើម្បីប្រើឈ្មោះ internal (<code>"
                + step["name"] + "</code>) ជំនួស:",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        # ── ប្តូរ Step ទូទាត់ របស់ clone ដែលមានស្រាប់ (ពី /mybots) ──
        if isinstance(step, dict) and step.get("step") == "cln_pay_key":
            key = text.strip()
            if len(key) < 10:
                bot.send_message(uid, "⚠️ API Key ខ្លីពេក សូមផ្ញើម្តងទៀត:", reply_markup=cancel_kb()); return
            name = step["clone"]
            waiting.pop(uid, None)
            _apply_clone_pay_update(uid, name, "auto", camrapid_key=key)
            return

        if isinstance(step, dict) and step.get("step") == "cln_pay_aba_key":
            key = text.strip()
            if len(key) < 10:
                bot.send_message(uid, "⚠️ Profile Key ខ្លីពេក សូមផ្ញើម្តងទៀត:", reply_markup=cancel_kb()); return
            name = step["clone"]
            waiting[uid] = {"step": "cln_pay_aba_merchant", "clone": name, "aba_key": key}
            bot.send_message(uid, f"វាយ <b>ABA Merchant ID</b> ថ្មីសម្រាប់ '{name}' (ឧ. <code>r72mCt</code>):",
                              parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "cln_pay_aba_merchant":
            merchant = text.strip()
            if not merchant:
                bot.send_message(uid, "⚠️ Merchant ID មិនត្រឹមត្រូវ សូមផ្ញើម្តងទៀត:", reply_markup=cancel_kb()); return
            name = step["clone"]
            waiting.pop(uid, None)
            _apply_clone_pay_update(uid, name, "aba", aba_key=step.get("aba_key", ""), aba_merchant=merchant)
            return

        if isinstance(step, dict) and step.get("step") == "cln_pay_qr_info":
            raw = text.strip()
            info = "" if raw == "-" else raw
            name = step["clone"]
            waiting.pop(uid, None)
            _apply_clone_pay_update(uid, name, "manual",
                                     manual_photo_id=step.get("manual_qr_photo_id", ""),
                                     manual_info=info)
            return

        if isinstance(step, dict) and step.get("step") == "cln_change_admin":
            if not text.strip().isdigit():
                bot.send_message(uid, "⚠️ សូមផ្ញើជាលេខតែប៉ុណ្ណោះ:", reply_markup=cancel_kb()); return
            name = step["clone"]
            new_admin_id = int(text.strip())
            cfg = clone_registry.get(name)
            waiting.pop(uid, None)
            if not cfg:
                bot.send_message(uid, "❌ រកមិនឃើញ bot នេះទេ (ប្រហែលត្រូវបានលុប)។", reply_markup=admin_kb())
                return
            old_admin_id = cfg["admin_id"]
            cfg["admin_id"] = new_admin_id
            clone_registry[name] = cfg
            _save(CLONES_REGISTRY, clone_registry)
            was_running = _clone_is_running(name)
            if was_running:
                _stop_clone(name); time.sleep(1); _spawn_clone(name, cfg)
            bot.send_message(uid,
                f"✅ បានប្តូរ Admin សម្រាប់ '<b>{name}</b>'\n"
                f"ចាស់: <code>{old_admin_id}</code> → ថ្មី: <code>{new_admin_id}</code>"
                + (" ហើយ restart រួច។" if was_running else " (bot នេះកំពុងបិទ — ចាប់ផ្តើមវាដើម្បីអនុវត្ត)។"),
                parse_mode="HTML", reply_markup=admin_kb())
            return

        if isinstance(step, dict) and step.get("step") == "cln_rename_name":
            new_name = text.strip()[:60]
            if not new_name:
                bot.send_message(uid, "⚠️ ឈ្មោះមិនត្រឹមត្រូវ សូមផ្ញើម្តងទៀត:", reply_markup=cancel_kb()); return
            name = step["clone"]
            cfg = clone_registry.get(name)
            waiting.pop(uid, None)
            if not cfg:
                bot.send_message(uid, "❌ រកមិនឃើញ bot នេះទេ (ប្រហែលត្រូវបានលុប)។", reply_markup=admin_kb())
                return
            old_name = cfg.get("display_name", name)
            cfg["display_name"] = new_name
            clone_registry[name] = cfg
            _save(CLONES_REGISTRY, clone_registry)
            was_running = _clone_is_running(name)
            if was_running:
                _stop_clone(name); time.sleep(1); _spawn_clone(name, cfg)
            bot.send_message(uid,
                f"✅ បានប្តូរ ឈ្មោះ Bot សម្រាប់ '<b>{name}</b>'\n"
                f"ចាស់: <code>{old_name}</code> → ថ្មី: <code>{new_name}</code>"
                + (" ហើយ restart រួច។" if was_running else " (bot នេះកំពុងបិទ — ចាប់ផ្តើមវាដើម្បីអនុវត្ត)។"),
                parse_mode="HTML", reply_markup=admin_kb())
            return

        # ── Clone ⚙️ ការកំណត់ផ្សេងទៀត — Support / Sub Admins / Bakong / QR Cooldown ──
        if isinstance(step, dict) and step.get("step") == "cln_support_text":
            name = step["clone"]; lang = step["lang"]
            raw = text.strip()
            cur = _clone_load(name, "smm_support.json", {"kh": "", "en": ""})
            cur[lang] = "" if raw == "-" else raw
            waiting.pop(uid, None)
            _clone_save_restart(uid, name, "smm_support.json", cur,
                f"✅ Support Message ({'ខ្មែរ' if lang=='kh' else 'English'}) បានរក្សាទុកសម្រាប់ '<b>{name}</b>'")
            return

        if isinstance(step, dict) and step.get("step") == "cln_subadmin_add_id":
            if not text.strip().isdigit():
                bot.send_message(uid, "⚠️ សូមផ្ញើជាលេខតែប៉ុណ្ណោះ:", reply_markup=cancel_kb()); return
            name = step["clone"]
            new_id = int(text.strip())
            cur = _clone_load(name, "smm_sub_admins.json", [])
            if new_id not in cur:
                cur.append(new_id)
            waiting.pop(uid, None)
            _clone_save_restart(uid, name, "smm_sub_admins.json", cur,
                f"✅ បន្ថែម Sub Admin <code>{new_id}</code> ចូល '<b>{name}</b>'")
            return

        if isinstance(step, dict) and step.get("step") == "cln_bakong_token":
            name = step["clone"]
            raw = text.strip()
            token = "" if raw == "-" else raw
            waiting.pop(uid, None)
            _clone_save_restart(uid, name, "smm_bakong.json", {"token": token},
                f"✅ Bakong Token បានរក្សាទុកសម្រាប់ '<b>{name}</b>'")
            return

        if isinstance(step, dict) and step.get("step") == "cln_cooldown_sec":
            raw = text.strip()
            if not raw.isdigit():
                bot.send_message(uid, "⚠️ សូមផ្ញើជាលេខតែប៉ុណ្ណោះ (0 = បិទ):", reply_markup=cancel_kb()); return
            name = step["clone"]
            sec = int(raw)
            waiting.pop(uid, None)
            _clone_save_restart(uid, name, "dep_qr_cooldown.json", {"seconds": sec},
                f"✅ QR Cooldown បានកំណត់ទៅ <b>{sec} វិនាទី</b> សម្រាប់ '<b>{name}</b>'")
            return

        if isinstance(step, dict) and step.get("step") == "newbot_display":
            raw = text.strip()
            display = step["name"] if raw == "-" else raw[:60]
            waiting[uid] = {**step, "step": "newbot_welcome", "display_name": display}
            _total = 7 if step.get("pay_method", "auto") == "auto" else 8
            bot.send_message(uid,
                f"{_step_label(_total, _total)} — វាយ <b>Welcome Message</b> custom សម្រាប់ bot នេះ\n"
                "ប្រើ <code>{}</code> ដើម្បីដាក់ balance ក្នុង text\n"
                "ឬផ្ញើ <code>-</code> ដើម្បីប្រើ welcome message default:",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "newbot_welcome":
            raw = text.strip()
            welcome = "" if raw == "-" else raw
            name = step["name"]; tok = step["token"]; new_admin = step["new_admin_id"]
            port = step["port"]; display = step["display_name"]
            pay_method = step.get("pay_method", "auto")
            masked_tok = tok[:10] + "..." + tok[-4:]
            if pay_method == "manual":
                pay_line = "🖼 QR ដាក់ដោយដៃ (Manual) — Step 2"
            elif pay_method == "aba":
                masked_key = step["aba_key"][:6] + "..." + step["aba_key"][-4:]
                pay_line = f"🏦 ABA PayWay — Key (<code>{masked_key}</code>) / Merchant (<code>{step['aba_merchant']}</code>)"
            else:
                masked_key = step["camrapid_key"][:6] + "..." + step["camrapid_key"][-4:]
                pay_line = f"🔄 CamRapidPay Key — Step 1 (<code>{masked_key}</code>)"
            waiting[uid] = {**step, "step": "newbot_confirm", "welcome_msg": welcome}
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("✅ បង្កើត ហើយ ដំណើរការ", callback_data="newbot_confirm_yes", color="active"))
            kb.add(InlineKeyboardButton("❌ បោះបង់", callback_data="newbot_confirm_no", color="inactive"))
            bot.send_message(uid,
                f"📋 <b>ត្រួតពិនិត្យ</b>\n\n"
                f"ឈ្មោះ internal: <code>{name}</code>\n"
                f"ឈ្មោះ display: <code>{display}</code>\n"
                f"Token: <code>{masked_tok}</code>\n"
                f"Admin ID: <code>{new_admin}</code>\n"
                f"ការទូទាត់: {pay_line}\n"
                f"Welcome: <code>{'(default)' if not welcome else welcome[:80]}</code>\n\n"
                f"ត្រឹមត្រូវទេ?",
                parse_mode="HTML", reply_markup=kb)
            return

        # ── Waiting steps ──
        if isinstance(step, dict) and step.get("step") == "add_balance_amt":
            target = step["target"]
            try:
                amt = float(text.replace("$",""))
                add_bal(int(target), amt)
                _save(WALLETS_FILE, wallets)
                waiting.pop(uid, None)
                bot.send_message(uid,
                    f"✅ <b>បន្ថែម Balance</b>\n👤 <code>{target}</code>\n"
                    f"💰 +${amt:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"✅ <b>Admin បន្ថែមលុយ!</b>\n💰 +${amt:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except Exception as _e: logger.debug(f"[silent] {_e}")
            except: bot.send_message(uid, "❌ Amount ខុស! ឧ: <code>5.00</code>", parse_mode="HTML")
            return

        if isinstance(step, dict) and step.get("step") == "deduct_balance_amt":
            target = step["target"]
            try:
                amt  = float(text.replace("$",""))
                cur  = bal(int(target))
                ded  = min(amt, cur)
                ded_bal(int(target), ded)
                waiting.pop(uid, None)
                bot.send_message(uid,
                    f"✅ <b>កាត់ Balance</b>\n👤 <code>{target}</code>\n"
                    f"💔 -${ded:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"⚠️ <b>Admin កាត់លុយ!</b>\n💔 -${ded:.2f} | Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except Exception as _e: logger.debug(f"[silent] {_e}")
            except: bot.send_message(uid, "❌ Amount ខុស!")
            return

        if isinstance(step, dict) and step.get("step") == "edit_svc_name":
            slug = step.get("slug")
            s    = smm_services.get(slug)
            if not s:
                bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb())
                waiting.pop(uid, None); return
            old_label = s.get("label", slug)
            new_label = text.strip()
            if not new_label:
                bot.send_message(uid, "❌ ឈ្មោះទទេ! សូមវាយម្តងទៀត"); return
            smm_services[slug]["label"] = new_label
            _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ <b>ឈ្មោះ Service បានផ្លាស់ប្តូរ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 API ID: <code>{s.get('api_id','?')}</code>\n"
                f"📝 ចាស់: <s>{old_label}</s>\n"
                f"✨ ថ្មី: <b>{new_label}</b>",
                parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "promo_add_code":
            parts = text.strip().split()
            if len(parts) < 4:
                bot.send_message(uid,
                    "❌ Format ខុស!\nឧ: <code>SAVE50 50 pct 100</code>\n"
                    "ឬ: <code>GIFT1 1.00 fix 50</code>", parse_mode="HTML"); return
            code = parts[0].upper()
            try:
                discount = float(parts[1])
                pct  = (parts[2].lower() == "pct")
                uses = int(parts[3])
            except:
                bot.send_message(uid, "❌ Format ខុស!", parse_mode="HTML"); return
            promos[code] = {"discount": discount, "pct": pct, "uses": uses, "used": 0}
            _save(PROMO_FILE, promos)
            waiting.pop(uid, None)
            dtype = f"{discount:.0f}%" if pct else f"${discount:.2f}"
            bot.send_message(uid,
                f"✅ <b>Promo Code Created!</b>\n"
                f"🎟️ <code>{code}</code> — <b>{dtype}</b> | {uses} uses",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if step == "broadcast_msg":
            _do_broadcast(uid, message); return

        if step == "smm_add_cat":
            waiting[uid] = {"step": "smm_add_platform", "cat": text}
            bot.send_message(uid,
                f"🌐 <b>ជ្រើស Platform</b> (សម្រាប់ផ្គូផ្គង Link)\n"
                f"📂 Category: <b>{text}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ជ្រើស Platform ត្រឹមត្រូវ ដើម្បីឲ្យ Bot ច្រានចោល Link ខុស Platform\n"
                f"(ចុច 🔓 ផ្សេង បើ Service ទាំងនេះទទួល Link ណាក៏បាន)",
                parse_mode="HTML", reply_markup=_platform_pick_kb("smmaddplat")); return

        if isinstance(step, dict) and step.get("step") == "smm_add_ids":
            cat = step["cat"]
            platform = step.get("platform") or _CAT_TO_PLATFORM_KEY.get(cat)
            # Check API configured first
            if not smm_api.get("url") or not smm_api.get("key"):
                waiting.pop(uid, None)
                bot.send_message(uid,
                    "❌ <b>SMM API មិនទាន់ Set!</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "ចុច <b>🔗 Set SMM API</b> ជាមុន រួចទើបបន្ថែម Service",
                    parse_mode="HTML", reply_markup=admin_kb()); return
            ids = [i.strip() for i in text.replace(" ", "").split(",") if i.strip().isdigit()]
            if not ids:
                bot.send_message(uid, "❌ ផ្ញើ IDs ជាលេខ ឧ: <code>5441,5448</code>",
                                 parse_mode="HTML"); return
            bot.send_message(uid, f"⏳ Fetching {len(ids)} service(s) from API...")
            ok, fail = [], []
            for api_id in ids:
                info = _smm_fetch_service(api_id)
                if info:
                    slug = f"{cat.lower().replace(' ', '_')}_{api_id}"
                    smm_services[slug] = {
                        "api_id":    api_id,
                        "cost_rate": info["cost_rate"],
                        "min":       info["min"],
                        "max":       info["max"],
                        "label":     _smm_clean_name(info["raw_name"]),
                        "category":  cat,
                        "platform":  platform,
                    }
                    ok.append(f"✅ <code>{api_id}</code> — {smm_services[slug]['label']}")
                else:
                    fail.append(f"❌ <code>{api_id}</code> — not found / API error")
            if ok:
                _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            msg = f"<b>📊 SMM Import — {cat}</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(ok)
            if fail: msg += "\n\n<b>Failed:</b>\n" + "\n".join(fail)
            msg += f"\n\n✅ Total services: <b>{len(smm_services)}</b>"
            bot.send_message(uid, msg, parse_mode="HTML", reply_markup=admin_kb()); return

        if step == "smm_api_url":
            smm_api["url"] = text.strip().rstrip("/")
            waiting[uid] = "smm_api_key"
            bot.send_message(uid,
                f"✅ URL: <code>{smm_api['url']}</code>\n\n🔑 ឥឡូវ ផ្ញើ API Key:",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if step == "smm_api_key":
            smm_api["key"] = text.strip()
            _save(SMM_API_FILE, smm_api)
            waiting.pop(uid, None)
            bot.send_message(uid, "⏳ Testing connection...", reply_markup=admin_kb())
            try:
                r = http.post(smm_api["url"],
                              data={"key": smm_api["key"], "action": "balance"}, timeout=10)
                d = r.json()
                balance  = d.get("balance", d.get("Balance", "?"))
                currency = d.get("currency", d.get("Currency", "USD"))
                bot.send_message(uid,
                    f"✅ <b>SMM API ភ្ជាប់ហើយ!</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"🌐 URL: <code>{smm_api['url']}</code>\n"
                    f"💰 Balance: <b>{balance} {currency}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except Exception as e:
                bot.send_message(uid,
                    f"⚠️ API Saved ប៉ុន្តែ test failed: <code>{e}</code>",
                    parse_mode="HTML", reply_markup=admin_kb())
            return

        if isinstance(step, dict) and step.get("step") == "depbonus_edit":
            try:
                parts = [p.strip() for p in text.replace("$", "").split(",")]
                if len(parts) != 2:
                    raise ValueError
                min_amt = float(parts[0]); pct = float(parts[1])
                if min_amt < 0 or pct < 0:
                    raise ValueError
                dep_bonus_cfg["min_amount"] = min_amt
                dep_bonus_cfg["pct"] = pct
                _save(DEP_BONUS_FILE, dep_bonus_cfg)
                waiting.pop(uid, None)
                bot.send_message(uid, f"✅ បានកែ!\n{_dep_bonus_status_text()}",
                                 parse_mode="HTML", reply_markup=admin_kb())
            except Exception:
                bot.send_message(uid,
                    "❌ ទម្រង់ខុស! សូមផ្ញើជា <code>ចំនួនអប្បបរមា,ភាគរយ</code>\nឧ: <code>1,5</code> (ដាក់ $1 ឡើងទៅ ទទួល 5%)",
                    parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "qrcooldown_edit":
            try:
                sec = int(float(text.strip()))
                if sec < 0:
                    raise ValueError
                dep_qr_cooldown_cfg["seconds"] = sec
                _save(DEP_QR_COOLDOWN_FILE, dep_qr_cooldown_cfg)
                waiting.pop(uid, None)
                bot.send_message(uid, f"✅ បានកែ!\n{_dep_qr_cooldown_status_text()}",
                                 parse_mode="HTML", reply_markup=admin_kb())
            except Exception:
                bot.send_message(uid,
                    "❌ ទម្រង់ខុស! សូមផ្ញើជាលេខវិនាទី (ចំនួនគត់, ≥ 0)\nឧ: <code>15</code>",
                    parse_mode="HTML", reply_markup=cancel_kb())
            return

        if isinstance(step, dict) and step.get("step") == "smm_set_profit":
            try:
                pct = float(text)
                smm_profit["pct"] = pct; _save(SMM_PROFIT_FILE, smm_profit)
                waiting.pop(uid, None)
                bot.send_message(uid, f"✅ SMM Profit <b>{pct:.0f}%</b>",
                                 parse_mode="HTML", reply_markup=admin_kb())
            except: bot.send_message(uid, "❌ ត្រូវជាលេខ")
            return

        if step == "await_dreport_hour":
            try:
                hour = int(text.strip())
                if not (0 <= hour <= 23):
                    raise ValueError
                daily_report_cfg["hour"] = hour; _save(DAILY_REPORT_FILE, daily_report_cfg)
                waiting.pop(uid, None)
                bot.send_message(uid, f"✅ កំណត់ម៉ោងផ្ញើ Daily Report ទៅ {hour:02d}:00 (ម៉ោងកម្ពុជា)",
                                 parse_mode="HTML", reply_markup=daily_report_kb())
            except (ValueError, TypeError):
                bot.send_message(uid, "❌ ត្រូវជាលេខ 0-23", reply_markup=cancel_kb())
            return

        if step == "await_manual_qr_info":
            manual_qr_cfg["info"] = text.strip()
            _save(MANUAL_QR_FILE, manual_qr_cfg)
            waiting.pop(uid, None)
            bot.send_message(uid, "✅ ព័ត៌មានបានកំណត់ជោគជ័យ!", parse_mode="HTML",
                              reply_markup=manual_qr_admin_kb())
            return

        # ── Manual service: step 1 label ──
        if isinstance(step, dict) and step.get("step") == "manual_svc_label":
            label = text.strip()
            if not label:
                bot.send_message(uid, "❌ ឈ្មោះទទេ! វាយម្តងទៀត:", reply_markup=cancel_kb()); return
            waiting[uid] = {"step": "manual_svc_cat", "label": label}
            cats_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎵 TikTok",    callback_data="mansvc_cat:TikTok", color="active"),
                 InlineKeyboardButton("📘 Facebook",  callback_data="mansvc_cat:Facebook", color="active")],
                [InlineKeyboardButton("📸 Instagram", callback_data="mansvc_cat:Instagram", color="active"),
                 InlineKeyboardButton("▶️ YouTube",   callback_data="mansvc_cat:YouTube", color="active")],
                [InlineKeyboardButton("📱 Telegram",  callback_data="mansvc_cat:Telegram", color="active"),
                 InlineKeyboardButton("🐦 Twitter",   callback_data="mansvc_cat:Twitter", color="active")],
                [InlineKeyboardButton("✏️ ផ្សេង (Custom)", callback_data="mansvc_cat:__custom__", color="progress")],
            ])
            bot.send_message(uid,
                f"📂 <b>ជ្រើស Category</b>\n"
                f"📝 ឈ្មោះ: <b>{label}</b>",
                parse_mode="HTML", reply_markup=cats_kb); return

        if isinstance(step, dict) and step.get("step") == "manual_svc_cat_custom":
            cat = text.strip()
            if not cat:
                bot.send_message(uid, "❌ Category ទទេ!", reply_markup=cancel_kb()); return
            waiting[uid] = {"step": "manual_svc_platform", "label": step["label"], "cat": cat}
            bot.send_message(uid,
                f"🌐 <b>ជ្រើស Platform</b> (សម្រាប់ផ្គូផ្គង Link)\n"
                f"📂 Category: <b>{cat}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ជ្រើស Platform ត្រឹមត្រូវ ដើម្បីឲ្យ Bot ច្រានចោល Link ខុស Platform\n"
                f"(ចុច 🔓 ផ្សេង បើ Service នេះទទួល Link ណាក៏បាន)",
                parse_mode="HTML", reply_markup=_platform_pick_kb("mansvcplat")); return

        if isinstance(step, dict) and step.get("step") == "manual_svc_price":
            try:
                price = float(text.replace("$","").strip())
                if price <= 0: raise ValueError
            except:
                bot.send_message(uid, "❌ តម្លៃខុស! ឧ: <code>0.50</code>",
                                 parse_mode="HTML", reply_markup=cancel_kb()); return
            waiting[uid] = {**step, "step": "manual_svc_min", "price": price}
            bot.send_message(uid,
                f"🔢 <b>Min Order</b> (ចំនួនអប្បបរមា)\n"
                f"ឧ: <code>100</code>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "manual_svc_min":
            try:
                mn = int(text.strip())
                if mn <= 0: raise ValueError
            except:
                bot.send_message(uid, "❌ ត្រូវជាលេខ! ឧ: <code>100</code>",
                                 parse_mode="HTML", reply_markup=cancel_kb()); return
            waiting[uid] = {**step, "step": "manual_svc_max", "min": mn}
            bot.send_message(uid,
                f"🔢 <b>Max Order</b> (ចំនួនអតិបរមា)\n"
                f"ឧ: <code>50000</code>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "manual_svc_max":
            try:
                mx = int(text.strip())
                if mx <= 0: raise ValueError
            except:
                bot.send_message(uid, "❌ ត្រូវជាលេខ! ឧ: <code>50000</code>",
                                 parse_mode="HTML", reply_markup=cancel_kb()); return
            # Save manual service
            label = step["label"]; cat = step["cat"]; price = step["price"]; mn = step["min"]
            slug  = f"manual_{cat.lower().replace(' ','_')}_{int(time.time())}"
            platform = step.get("platform") or _CAT_TO_PLATFORM_KEY.get(cat)
            smm_services[slug] = {
                "api_id":       None,          # No API — manual
                "manual":       True,
                "cost_rate":    price,
                "min":          mn,
                "max":          mx,
                "label":        label,
                "category":     cat,
                "platform":     platform,
            }
            _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            plabel = _PLATFORM_LABEL_BY_KEY.get(platform, "គ្មាន (Any Link)")
            bot.send_message(uid,
                f"✅ <b>Manual Service បានបន្ថែម!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 ឈ្មោះ: <b>{label}</b>\n"
                f"📂 Category: <b>{cat}</b>\n"
                f"🌐 Platform: <b>{plabel}</b>\n"
                f"💰 តម្លៃ: <b>${price:.2f}/1K</b>\n"
                f"🔢 Min: <b>{mn:,}</b> · Max: <b>{mx:,}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✍️ <i>Service នេះ Admin ត្រូវ process ដោយដៃ</i>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        # ── Admin: Update manual order status ──
        if isinstance(step, dict) and step.get("step") == "manual_order_done" and uid == ADMIN_ID:
            oid      = step.get("oid")
            user_uid = step.get("user_uid")
            o        = smm_orders.get(oid)
            if not o:
                bot.send_message(uid, "❌ Order រកមិនឃើញ", reply_markup=admin_kb())
                waiting.pop(uid, None); return
            note = text.strip()
            smm_orders[oid]["status"]   = "completed"
            smm_orders[oid]["note"]     = note
            _save(SMM_ORD_FILE, smm_orders)
            waiting.pop(uid, None)
            try:
                bot.send_message(int(user_uid),
                    f"✅ <b>Order បានដំណើរការហើយ!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 <code>{oid}</code>\n"
                    f"📊 {o.get('label','?')}\n"
                    f"🔢 ចំនួន: <b>{o.get('qty',0):,}</b>\n"
                    + (f"📝 Note: {note}\n" if note and note != "-" else "") +
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🙏 អរគុណ!",
                    parse_mode="HTML")
            except Exception as _e: logger.debug(f"[silent] {_e}")
            bot.send_message(uid,
                f"✅ <b>Order Completed!</b>\n🆔 <code>{oid}</code>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "✍️ Manual SMM":
            waiting[uid] = {"step": "manual_svc_label"}
            bot.send_message(uid,
                "✍️ <b>បន្ថែម Manual Service</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>Service ប្រភេទនេះ Admin process ដោយដៃ\n"
                "ប្រើសម្រាប់: TikTok Khmer, Reseller, ល.ល</i>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "📝 <b>វាយ ឈ្មោះ Service:</b>\n"
                "ឧ: <code>TikTok Likes Khmer</code>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        # ── Package (flat-price bundle): step 1 label ──
        if text == "📦 បន្ថែម Package":
            waiting[uid] = {"step": "pkg_label"}
            bot.send_message(uid,
                "📦 <b>បន្ថែម Package ថ្មី (កញ្ចប់តម្លៃថេរ)</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>ប្រើសម្រាប់កញ្ចប់ Like+View+Follow ដូច TikTok Khmer\n"
                "(តម្លៃថេរក្នុងមួយ Order — មិនគិតតាម 1K ទេ)</i>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "📝 <b>វាយ ឈ្មោះ Package:</b>\n"
                "ឧ: <code>1K-2K Like + 3.5K View</code>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "pkg_label":
            label = text.strip()
            if not label:
                bot.send_message(uid, "❌ ឈ្មោះទទេ! វាយម្តងទៀត:", reply_markup=cancel_kb()); return
            waiting[uid] = {"step": "pkg_cat", "label": label}
            cats_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🇰🇭 TikTok Khmer", callback_data="pkgcat:🇰🇭 TikTok Khmer", color="active")],
                [InlineKeyboardButton("🎵 TikTok",    callback_data="pkgcat:TikTok", color="active"),
                 InlineKeyboardButton("📘 Facebook",  callback_data="pkgcat:Facebook", color="active")],
                [InlineKeyboardButton("📸 Instagram", callback_data="pkgcat:Instagram", color="active"),
                 InlineKeyboardButton("▶️ YouTube",   callback_data="pkgcat:YouTube", color="active")],
                [InlineKeyboardButton("✏️ ផ្សេង (Custom)", callback_data="pkgcat:__custom__", color="progress")],
            ])
            bot.send_message(uid,
                f"📂 <b>ជ្រើស Category</b>\n📝 ឈ្មោះ: <b>{label}</b>",
                parse_mode="HTML", reply_markup=cats_kb); return

        if isinstance(step, dict) and step.get("step") == "pkg_cat_custom":
            cat = text.strip()
            if not cat:
                bot.send_message(uid, "❌ Category ទទេ!", reply_markup=cancel_kb()); return
            waiting[uid] = {"step": "pkg_platform", "label": step["label"], "cat": cat}
            bot.send_message(uid,
                f"🌐 <b>ជ្រើស Platform</b> (សម្រាប់ផ្គូផ្គង Link)\n"
                f"📂 Category: <b>{cat}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ជ្រើស Platform ត្រឹមត្រូវ ដើម្បីឲ្យ Bot ច្រានចោល Link ខុស Platform\n"
                f"(ចុច 🔓 ផ្សេង បើ Package នេះទទួល Link ណាក៏បាន)",
                parse_mode="HTML", reply_markup=_platform_pick_kb("pkgplat")); return

        if isinstance(step, dict) and step.get("step") == "pkg_desc":
            desc = text.strip()
            waiting[uid] = {**step, "step": "pkg_price", "desc": ("" if desc == "-" else desc)}
            bot.send_message(uid,
                "💰 <b>ដាក់តម្លៃ Package (USD / កញ្ចប់)</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "ឧ: <code>0.99</code> = $0.99 ក្នុងមួយកញ្ចប់",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "pkg_price":
            try:
                price = float(text.replace("$","").strip())
                if price <= 0: raise ValueError
            except:
                bot.send_message(uid, "❌ តម្លៃខុស! ឧ: <code>0.99</code>",
                                 parse_mode="HTML", reply_markup=cancel_kb()); return
            label = step["label"]; cat = step["cat"]; desc = step.get("desc", "")
            platform = step.get("platform") or _CAT_TO_PLATFORM_KEY.get(cat)
            slug = f"manual_pkg_{cat.lower().replace(' ','_')}_{int(time.time())}"
            smm_services[slug] = {
                "api_id":      None,
                "manual":      True,
                "cost_rate":   0,
                "min":         1,
                "max":         1,
                "label":       label,
                "category":    cat,
                "platform":    platform,
                "flat_price":  price,
                "preset_qtys": [1],
                "description": desc,
            }
            _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ <b>Package បានបន្ថែម!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 ឈ្មោះ: <b>{label}</b>\n"
                f"📂 Category: <b>{cat}</b>\n"
                f"💰 តម្លៃ: <b>${price:.2f}/order</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"✍️ <i>Package នេះ Admin ត្រូវ process ដោយដៃ</i>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        # ── Edit price of an existing service/package ──
        if text == "💰 កែតម្លៃ":
            if not smm_services:
                bot.send_message(uid, "❌ គ្មាន SMM Service ទេ", reply_markup=admin_kb()); return
            cats = {}
            for slug, s in smm_services.items():
                cat = s.get("category", "Other")
                cats.setdefault(cat, []).append((slug, s))
            for cat, svcs in cats.items():
                btns = []
                for slug, s in svcs:
                    label = s.get("label", slug)[:28]
                    if s.get("flat_price"):
                        price_txt = f"${float(s['flat_price']):.2f}"
                    else:
                        price_txt = f"${float(s.get('cost_rate',0)):.2f}/1K"
                    btns.append([InlineKeyboardButton(
                        f"💰 {label} ({price_txt})", callback_data=f"editprice:{slug}", color="progress")])
                bot.send_message(uid,
                    f"💰 <b>កែតម្លៃ — {cat}</b>\n━━━━━━━━━━━━━━━━━━\nចុចដើម្បីកែតម្លៃ:",
                    parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
            return

        if isinstance(step, dict) and step.get("step") == "edit_svc_price":
            slug = step.get("slug")
            s    = smm_services.get(slug)
            if not s:
                bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb())
                waiting.pop(uid, None); return
            try:
                new_price = float(text.replace("$","").strip())
                if new_price <= 0: raise ValueError
            except:
                bot.send_message(uid, "❌ តម្លៃខុស! ឧ: <code>1.99</code>",
                                 parse_mode="HTML", reply_markup=cancel_kb()); return
            is_flat = bool(s.get("flat_price"))
            if is_flat:
                old_price = float(s.get("flat_price", 0))
                smm_services[slug]["flat_price"] = new_price
                unit = "/order"
            else:
                old_price = float(s.get("cost_rate", 0))
                smm_services[slug]["cost_rate"] = new_price
                unit = "/1K"
            _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ <b>តម្លៃបានផ្លាស់ប្តូរ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📝 {s.get('label', slug)}\n"
                f"💰 ចាស់: <s>${old_price:.2f}{unit}</s>\n"
                f"✨ ថ្មី: <b>${new_price:.2f}{unit}</b>",
                parse_mode="HTML", reply_markup=admin_kb())
            return

        if text == "📊 ការបញ្ជា SMM":
            if not smm_orders:
                bot.send_message(uid, "❌ គ្មានការបញ្ជា SMM", reply_markup=admin_kb()); return
            lines = ["<b>📊 ការបញ្ជា SMM (20 ចុងក្រោយ)</b>\n━━━━━━━━━━━━━━━━━━"]
            for oid, o in list(smm_orders.items())[-20:]:
                lines.append(f"🆔 <code>{oid}</code> | 👤 <code>{o['uid']}</code>\n  {o.get('label','?')} | Qty:{o.get('qty','?')} | ${o.get('price',0):.4f} | {o.get('status','?')}")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "⚙️ កំណត់ SMM API":
            cur_url = smm_api.get("url","❌ មិនទាន់ set")
            cur_key = smm_api.get("key","❌ មិនទាន់ set")
            masked = cur_key[:6] + "****" + cur_key[-4:] if len(cur_key) > 10 else cur_key
            kb_api = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ កំណត់ URL + Key", callback_data="smmapi:setup", color="progress")],
                [InlineKeyboardButton("🔌 សាកល្បងភ្ជាប់",  callback_data="smmapi:test", color="active")],
                [InlineKeyboardButton("🗑️ លុប API",         callback_data="smmapi:clear", color="inactive")],
            ])
            bot.send_message(uid,
                f"⚙️ <b>SMM API Config</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"🌐 URL: <code>{cur_url}</code>\n"
                f"🔑 Key: <code>{masked}</code>",
                parse_mode="HTML", reply_markup=kb_api); return

        if text == "➕ បន្ថែម SMM":
            cats_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎵 TikTok",    callback_data="smmaddcat:TikTok", color="active"),
                 InlineKeyboardButton("📘 Facebook",  callback_data="smmaddcat:Facebook", color="active")],
                [InlineKeyboardButton("📸 Instagram", callback_data="smmaddcat:Instagram", color="active"),
                 InlineKeyboardButton("▶️ YouTube",   callback_data="smmaddcat:YouTube", color="active")],
                [InlineKeyboardButton("📱 Telegram",  callback_data="smmaddcat:Telegram", color="active"),
                 InlineKeyboardButton("🐦 Twitter",   callback_data="smmaddcat:Twitter", color="active")],
                [InlineKeyboardButton("✏️ Custom Category", callback_data="smmaddcat:custom", color="progress")],
            ])
            bot.send_message(uid,
                "➕ <b>បន្ថែម SMM Service</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Category:",
                parse_mode="HTML", reply_markup=cats_kb); return

        if text == "🗑️ លុប SMM":
            if not smm_services:
                bot.send_message(uid, "❌ គ្មាន SMM Service ទេ", reply_markup=admin_kb()); return
            cats = {}
            for slug, s in smm_services.items():
                cat = s.get("category", "Other")
                cats.setdefault(cat, []).append((slug, s))
            for cat, svcs in cats.items():
                btns = []
                for slug, s in svcs:
                    label = s.get("label", slug)[:30]
                    api_id = s.get("api_id", "?")
                    btns.append([InlineKeyboardButton(
                        f"🗑️ [{api_id}] {label}", callback_data=f"delsvc:{slug}", color="inactive")])
                btns.append([InlineKeyboardButton(
                    f"🗑️ លុបទាំងអស់ {cat}", callback_data=f"delsvc:cat:{cat}", color="inactive")])
                bot.send_message(uid,
                    f"📂 <b>{cat}</b> — {len(svcs)} services\n━━━━━━━━━━━━━━━━━━",
                    parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
            return

        if text == "✏️ កែ SMM":
            if not smm_services:
                bot.send_message(uid, "❌ គ្មាន SMM Service ទេ", reply_markup=admin_kb()); return
            cats = {}
            for slug, s in smm_services.items():
                cat = s.get("category", "Other")
                cats.setdefault(cat, []).append((slug, s))
            for cat, svcs in cats.items():
                btns = []
                for slug, s in svcs:
                    label  = s.get("label", slug)[:35]
                    api_id = s.get("api_id", "?")
                    btns.append([InlineKeyboardButton(
                        f"✏️ [{api_id}] {label}", callback_data=f"editsvc:{slug}", color="progress")])
                bot.send_message(uid,
                    f"✏️ <b>កែឈ្មោះ — {cat}</b>\n━━━━━━━━━━━━━━━━━━\nចុចដើម្បីកែ:",
                    parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
            return

        if text == "📋 SMM Services":
            bot.send_message(uid, _smm_service_list_text(), parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "💹 ប្រាក់ចំណេញ SMM":
            waiting[uid] = {"step": "smm_set_profit"}
            bot.send_message(uid,
                f"💹 <b>ប្រាក់ចំណេញ SMM: {_smm_profit_pct():.0f}%</b>\nផ្ញើ % ថ្មី:",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if text == "📈 របាយការណ៍ចំណេញ":
            bot.send_message(uid, _profit_report_text(), parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "🏆 Top Services/Clients":
            bot.send_message(uid, _top_report_text(), parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "⏰ Daily Report Auto":
            bot.send_message(uid,
                f"⏰ <b>Daily Report Auto</b>\nស្ថានភាព: {'🟢 បើក' if daily_report_cfg.get('enabled', True) else '🔴 បិទ'}\n"
                f"ម៉ោងផ្ញើ: {daily_report_cfg.get('hour', 8):02d}:00 (ម៉ោងកម្ពុជា)\n\n"
                f"Bot នឹងផ្ញើ 📈 ចំណេញ + 🏆 Top Services/Clients មកអ្នកដោយស្វ័យប្រវត្តិរាល់ថ្ងៃ។",
                parse_mode="HTML", reply_markup=daily_report_kb())
            return

        if text == "💾 Backup Data":
            cmd_backup(message); return

        if text == "🧾 QR ដាក់លុយដោយដៃ":
            bot.send_message(uid, _manual_qr_status_text(), parse_mode="HTML", reply_markup=manual_qr_admin_kb())
            return

        if text == "🎁 Bonus ដាក់លុយ":
            btns = InlineKeyboardMarkup()
            toggle_label = "🔴 បិទ Auto Bonus" if dep_bonus_cfg.get("enabled", True) else "🟢 បើក Auto Bonus"
            btns.add(InlineKeyboardButton(toggle_label, callback_data="depbonus:toggle",
                                          color=("danger" if dep_bonus_cfg.get("enabled", True) else "active")))
            btns.add(InlineKeyboardButton("✏️ កែ % / ចំនួនអប្បបរមា", callback_data="depbonus:edit", color="progress"))
            bot.send_message(uid,
                f"{_dep_bonus_status_text()}\n━━━━━━━━━━━━━━━━━━\n"
                f"👉 អ្នកប្រើដាក់លុយចាប់ពី <b>${float(dep_bonus_cfg.get('min_amount',1.0)):.2f}</b> ឡើងទៅ "
                f"នឹងទទួល Bonus <b>{float(dep_bonus_cfg.get('pct',5.0)):.0f}%</b> បញ្ចូល Balance ដោយស្វ័យប្រវត្តិ "
                f"(បូកបន្ថែមលើ Promo Code ប្រសិនបើមាន)។",
                parse_mode="HTML", reply_markup=btns); return

        if text == "⏳ QR Cooldown":
            btns = InlineKeyboardMarkup()
            btns.add(InlineKeyboardButton("✏️ កែ Cooldown (វិនាទី)", callback_data="qrcd:edit", color="progress"))
            btns.add(InlineKeyboardButton("🔴 បិទ Cooldown", callback_data="qrcd:off", color="danger"))
            bot.send_message(uid,
                f"{_dep_qr_cooldown_status_text()}",
                parse_mode="HTML", reply_markup=btns); return

        if text == "💰 ឆែកលុយ API":
            url = smm_api.get("url",""); key = smm_api.get("key","")
            if not url or not key:
                bot.send_message(uid, "❌ SMM API មិនទាន់ set!", reply_markup=admin_kb()); return
            try:
                r = http.post(url, data={"key": key, "action": "balance"}, timeout=10)
                d = r.json()
                balance  = d.get("balance", d.get("Balance", "?"))
                currency = d.get("currency", d.get("Currency", "USD"))
                bot.send_message(uid,
                    f"💰 <b>SMM API Balance</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"💵 Balance: <b>{balance} {currency}</b>\n"
                    f"🌐 API: <code>{url}</code>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except Exception as e:
                bot.send_message(uid, f"❌ API Error: {e}", reply_markup=admin_kb())
            return

        if text == "💰 កាបូបលុយ":
            lines = ["<b>💰 កាបូបលុយអ្នកប្រើ</b>\n━━━━━━━━━━━━━━━━━━"]
            for u_id, u_info in sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:30]:
                b = wallets.get(u_id, 0)
                name = u_info.get("name","?")
                lines.append(f"👤 <b>{name}</b> <code>{u_id}</code> — <b>${float(b):.2f}</b>")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "💳 ប្រាក់បញ្ញើ":
            pend = [(k, v) for k, v in smm_deps.items() if v.get("status")=="pending"]
            if not pend:
                bot.send_message(uid, "✅ គ្មាន pending deposit", reply_markup=admin_kb()); return
            lines = ["<b>💳 ប្រាក់បញ្ញើ រង់ចាំ</b>\n━━━━━━━━━━━━━━━━━━"]
            for k, v in pend:
                lines.append(f"👤 <code>{v.get('uid','?')}</code> | ${v.get('amount',0):.2f}")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "💸 បន្ថែមប្រាក់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:15]
            btns = []
            for u_id, u_info in users_sorted:
                b    = float(wallets.get(u_id, 0))
                name = (u_info.get("name") or "?")[:18]
                btns.append([InlineKeyboardButton(
                    f"👤 {name}  ${b:.2f}", callback_data=f"useraction:addbal:{u_id}", color="active")])
            bot.send_message(uid,
                "💸 <b>បន្ថែមប្រាក់</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសអ្នកប្រើ:",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)); return

        if text == "💔 កាត់ប្រាក់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:15]
            btns = []
            for u_id, u_info in users_sorted:
                b    = float(wallets.get(u_id, 0))
                name = (u_info.get("name") or "?")[:18]
                btns.append([InlineKeyboardButton(
                    f"👤 {name}  ${b:.2f}", callback_data=f"useraction:dedbal:{u_id}", color="progress")])
            bot.send_message(uid,
                "💔 <b>កាត់ប្រាក់</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសអ្នកប្រើ:",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)); return

        if text == "👥 អ្នកប្រើប្រាស់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)
            if not users_sorted:
                bot.send_message(uid, "❌ គ្មានអ្នកប្រើ", reply_markup=admin_kb()); return
            total = len(users_sorted)
            # Build table 20 per page to keep msgs short & avoid HTML issues
            CHUNK = 20
            chunks = [users_sorted[i:i+CHUNK] for i in range(0, total, CHUNK)]
            for page, chunk in enumerate(chunks):
                lines = []
                for i, (u_id, u_info) in enumerate(chunk, start=page*CHUNK+1):
                    b      = float(wallets.get(u_id, 0))
                    name   = (u_info.get("name") or "NoName")[:10]
                    uname  = f"@{u_info['username']}" if u_info.get("username") else "—"
                    banned = "🚫" if u_info.get("banned") else "✅"
                    lines.append(
                        f"{i:>3}. {banned} {u_id}\n"
                        f"     👤 {name}  {uname}  💳${b:.2f}"
                    )
                header = (
                    f"👥 <b>អ្នកប្រើ ({page*CHUNK+1}–{page*CHUNK+len(chunk)}/{total})</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"#    ស្ថានភាព  ID\n"
                    f"     ឈ្មោះ  Username  Balance\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                )
                # Build inline buttons for each page
                ikb_rows = []
                for u_id, _ in chunk:
                    ikb_rows.append([
                        InlineKeyboardButton(f"💸 {u_id}", callback_data=f"useraction:addbal:{u_id}", color="active"),
                        InlineKeyboardButton("💔 កាត់", callback_data=f"useraction:dedbal:{u_id}", color="progress"),
                        InlineKeyboardButton("🚫 Ban", callback_data=f"useraction:ban:{u_id}", color="inactive"),
                    ])
                ikb = InlineKeyboardMarkup(ikb_rows)
                bot.send_message(uid, header + "\n".join(lines),
                    parse_mode="HTML", reply_markup=ikb)
            bot.send_message(uid, f"✅ បង្ហាញ User ទាំង {total} នាក់រួចហើយ!", reply_markup=admin_kb())
            return

        if text == "📊 ស្ថិតិ":
            total_orders = len(smm_orders)
            total_users  = len(users_db)
            total_rev    = sum(float(o.get("price") or 0) for o in smm_orders.values())
            bot.send_message(uid,
                f"📊 <b>ស្ថិតិ</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"👥 អ្នកប្រើ: <b>{total_users}</b>\n"
                f"📊 SMM Orders: <b>{total_orders}</b>\n"
                f"💰 ចំណូលសរុប: <b>${total_rev:.2f}</b>\n"
                f"📋 Services: <b>{len(smm_services)}</b>\n"
                f"🎟️ Promos: <b>{len(promos)}</b>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "📢 ផ្សព្វផ្សាយ":
            waiting[uid] = "broadcast_msg"
            bot.send_message(uid, "📢 <b>ផ្សព្វផ្សាយ</b>\nផ្ញើ Message (text/photo/video):",
                             parse_mode="HTML", reply_markup=cancel_kb()); return

        if text == "⏱ ល្បឿន Poll":
            cur = smm_poll.get("interval", 5)
            bot.send_message(uid, f"⏱ ល្បឿន Poll (បច្ចុប្បន្ន: {cur}s)",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚡ 3s",  callback_data="poll:3", color="active"),
                     InlineKeyboardButton("🟢 5s",  callback_data="poll:5", color="active"),
                     InlineKeyboardButton("🔵 10s", callback_data="poll:10", color="progress")],
                    [InlineKeyboardButton("🟡 15s", callback_data="poll:15", color="progress"),
                     InlineKeyboardButton("🔴 30s", callback_data="poll:30", color="inactive")],
                ])); return

        if text == "🖼️ Welcome Photo":
            cur = "✅ មានរូបហើយ" if welcome_cfg.get("photo_id") else "❌ មិនទាន់មានរូប"
            waiting[uid] = "set_welcome_photo"
            bot.send_message(uid,
                f"🖼️ <b>Welcome Photo</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ស្ថានភាព: <b>{cur}</b>\n\n"
                f"📤 ផ្ញើ រូបភាព ដែលចង់ប្រើ\n"
                f"<i>(រូបនេះនឹងបង្ហាញពេល User ចុច /start)</i>",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if text == "🎬 វីដេអូបង្រៀន":
            cur = "✅ មានវីដេអូហើយ" if tutorial_cfg.get("file_id") else "❌ មិនទាន់មានវីដេអូ"
            waiting[uid] = "set_tutorial_video"
            bot.send_message(uid,
                f"🎬 <b>វីដេអូបង្រៀន (Tutorial Video)</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ស្ថានភាព: <b>{cur}</b>\n\n"
                f"📤 ផ្ញើ វីដេអូ ដែលចង់ប្រើសម្រាប់បង្រៀន User\n"
                f"<i>(វីដេអូនេះនឹងបង្ហាញពេល User ចុច 💡 របៀបប្រើប្រាស់)</i>",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if step == "set_notify_channel":
            waiting.pop(uid, None)
            val = text.strip()
            if val.lower() == "off":
                notify_cfg["enabled"] = False
                _save(NOTIFY_FILE, notify_cfg)
                bot.send_message(uid, "🔕 <b>Notify Channel បានបិទ!</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            else:
                notify_cfg["channel_id"] = val
                notify_cfg["enabled"] = True
                _save(NOTIFY_FILE, notify_cfg)
                bot.send_message(uid,
                    f"✅ <b>Notify Channel បានកំណត់!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📢 Channel/Group: <code>{val}</code>\n"
                    f"ស្ថានភាព: ✅ បើក\n\n"
                    f"⚠️ <b>នៅ Render ត្រូវបន្ថែម Environment Variable:</b>\n"
                    f"<code>NOTIFY_CHANNEL_ID = {val}</code>\n\n"
                    f"<i>💡 ត្រូវប្រាកដថា Bot ជា Admin នៅ Channel/Group នោះ!</i>",
                    parse_mode="HTML", reply_markup=admin_kb())
            return

        if text == "🔔 Notify Channel":
            cid  = notify_cfg.get("channel_id", "") or "មិនទាន់កំណត់"
            ison = "✅ បើក" if notify_cfg.get("enabled") else "❌ បិទ"
            waiting[uid] = "set_notify_channel"
            bot.send_message(uid,
                f"🔔 <b>Notify Channel</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Channel/Group ID: <code>{cid}</code>\n"
                f"ស្ថានភាព: <b>{ison}</b>\n\n"
                f"📝 ផ្ញើ Channel/Group ID ថ្មី\n"
                f"<i>ឧ: <code>-1001234567890</code> ឬ <code>@mychannel</code></i>\n\n"
                f"💡 ដើម្បី <b>បិទ</b> វាយ: <code>off</code>",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if text == "🧪 តេស្ត Notify":
            cfg = _get_notify_cfg()
            cid = cfg.get("channel_id", "")
            if not cid or not cfg.get("enabled", False):
                bot.send_message(uid, "❌ Notify Channel មិនទាន់កំណត់! ចុច 🔔 Notify Channel ដើម្បី setup ជាមុន", parse_mode="HTML", reply_markup=admin_kb())
                return
            try:
                test_msg = "🧪 តេស្ត Notify!\n━━━━━━━━━━━━━━━━━━\n✅ Bot ដំណើរការ\n📢 Channel/Group: <code>" + cid + "</code>\n━━━━━━━━━━━━━━━━━━"
                bot.send_message(cid, test_msg, parse_mode="HTML")
                bot.send_message(uid, "✅ តេស្តបានជោគជ័យ! សារបានចូល Channel/Group ✅", parse_mode="HTML", reply_markup=admin_kb())
            except Exception as e:
                bot.send_message(uid, "❌ តេស្តបរាជ័យ!\nError: <code>" + str(e) + "</code>\n\n💡 ត្រូវប្រាកដថា Bot ជា Admin នៅ Channel/Group!", parse_mode="HTML", reply_markup=admin_kb())
            return
        if text == "🔄 ធ្វើឱ្យទាន់សម័យ":
            bot.send_message(uid, "✅ បានធ្វើឱ្យទាន់សម័យ!", reply_markup=admin_kb()); return

        # ══ NEW: Settings buttons (Master Admin only) ══
        if text == "✏️ កែ Support":
            if uid != ADMIN_ID:
                bot.send_message(uid, "🚫 Master Admin only!", reply_markup=sub_admin_kb()); return
            cur_kh = support_cfg.get("kh","")
            cur_en = support_cfg.get("en","")
            kb2 = InlineKeyboardMarkup()
            kb2.add(InlineKeyboardButton("✏️ កែ (ខ្មែរ)", callback_data="set_support:kh", color="progress"))
            kb2.add(InlineKeyboardButton("✏️ Edit (English)", callback_data="set_support:en", color="progress"))
            bot.send_message(uid,
                f"💬 <b>Support Message Settings</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🇰🇭 KH:\n<code>{cur_kh or '(default)'}</code>\n\n"
                f"🇺🇸 EN:\n<code>{cur_en or '(default)'}</code>",
                parse_mode="HTML", reply_markup=kb2); return

        if text == "👥 Sub Admins":
            if uid != ADMIN_ID:
                bot.send_message(uid, "🚫 Master Admin only!", reply_markup=sub_admin_kb()); return
            kb2 = InlineKeyboardMarkup()
            kb2.add(InlineKeyboardButton("➕ បន្ថែម Sub Admin", callback_data="subadmin:add", color="active"))
            kb2.add(InlineKeyboardButton("🗑️ លុប Sub Admin", callback_data="subadmin:list_del", color="inactive"))
            lines = [f"👥 <b>Sub Admins ({len(sub_admins)})</b>\n━━━━━━━━━━━━━━━━━━"]
            if sub_admins:
                for sa in sub_admins:
                    lines.append(f"• <code>{sa}</code>")
            else:
                lines.append("(គ្មាន Sub Admin ទេ)")
            bot.send_message(uid, "\n".join(lines), parse_mode="HTML", reply_markup=kb2); return

        if text == "🔑 CamRapidPay Key":
            if uid != ADMIN_ID:
                bot.send_message(uid, "🚫 Master Admin only!", reply_markup=sub_admin_kb()); return
            cur = _effective_camrapid_key()
            masked = cur[:8] + "..." + cur[-4:] if len(cur) > 12 else ("*" * len(cur) if cur else cur)
            wh_cur = _effective_webhook_url()
            wh_src = ("📁 Set ក្នុង Bot" if webhook_cfg.get("url")
                      else "⚙️ env WEBHOOK_URL" if WEBHOOK_URL
                      else "🤖 Auto (Render)" if os.getenv("RENDER_EXTERNAL_URL")
                      else "🔧 Placeholder ក្លែងក្លាយ")
            kb2 = InlineKeyboardMarkup()
            kb2.add(InlineKeyboardButton("✏️ ប្តូរ Key ថ្មី", callback_data="set_camrapid:edit", color="progress"))
            kb2.add(InlineKeyboardButton("🌐 ប្តូរ Webhook URL", callback_data="set_camrapid:webhook", color="progress"))
            kb2.add(InlineKeyboardButton("🧪 Test Key (Check Endpoint)", callback_data="set_camrapid:test", color="active"))
            kb2.add(InlineKeyboardButton("🧾 Test Generate QR (Create Endpoint)", callback_data="set_camrapid:testcreate", color="active"))
            bot.send_message(uid,
                f"🔑 <b>CamRapidPay API Key</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Key: <code>{masked}</code>\n"
                f"Source: {'📁 runtime' if camrapid_cfg.get('key') else '⚙️ env/default'}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🌐 Webhook URL: <code>{wh_cur}</code>\n"
                f"Source: {wh_src}",
                parse_mode="HTML", reply_markup=kb2); return

        if text == "💳 ABA PayWay Key":
            if uid != ADMIN_ID:
                bot.send_message(uid, "🚫 Master Admin only!", reply_markup=sub_admin_kb()); return
            cur_key = _effective_aba_key()
            cur_mid = _effective_aba_merchant()
            masked_key = cur_key[:6] + "..." + cur_key[-4:] if len(cur_key) > 10 else (("*" * len(cur_key)) if cur_key else "(មិនទាន់កំណត់)")
            kb2 = InlineKeyboardMarkup()
            kb2.add(InlineKeyboardButton("✏️ ប្តូរ API Key ថ្មី", callback_data="set_aba:edit_key", color="progress"))
            kb2.add(InlineKeyboardButton("✏️ ប្តូរ Merchant ID ថ្មី", callback_data="set_aba:edit_merchant", color="progress"))
            kb2.add(InlineKeyboardButton("🧪 Test Generate QR ($0.10)", callback_data="set_aba:testcreate", color="active"))
            bot.send_message(uid,
                f"💳 <b>ABA PayWay Key (KHMER SYSTEM)</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔑 Profile Key: <code>{masked_key}</code>\n"
                f"🏪 Merchant ID: <code>{cur_mid or '(មិនទាន់កំណត់)'}</code>\n"
                f"Source: {'📁 runtime' if (aba_cfg.get('key') or aba_cfg.get('merchant_id')) else '⚙️ env/default'}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📌 ត្រូវការទាំង ២ (Key + Merchant ID) ដើម្បីបើក ABA PayWay ជាវិធីទូទាត់ស្វ័យប្រវត្តិ។\n"
                f"យកពី: khmer-system.com/operator/profile\n"
                f"💡 បើកំណត់ទាំង CamRapidPay + ABA ព្រមគ្នា Bot នឹងឲ្យ User ជ្រើសរើសពេលដាក់លុយ។",
                parse_mode="HTML", reply_markup=kb2); return

        if text == "🔀 វិធីទូទាត់":
            if uid != ADMIN_ID:
                bot.send_message(uid, "🚫 Master Admin only!", reply_markup=sub_admin_kb()); return
            bot.send_message(uid,
                f"🔀 <b>បិទ/បើក វិធីទូទាត់</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{_paytoggle_status_lines()}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👉 ចុចប៊ូតុងខាងក្រោមដើម្បីបិទ/បើក។ បើមានទាំង ២ (Key កំណត់រួច + Toggle ON) ព្រមគ្នា "
                f"User នឹងឃើញ picker ជ្រើសរើសពេលដាក់លុយ។ បើមានតែមួយ Bot ប្រើវិធីនោះដោយស្វ័យប្រវត្តិ។",
                parse_mode="HTML", reply_markup=_paytoggle_kb()); return

        if text == "🏦 Bakong Deep Link":
            if uid != ADMIN_ID:
                bot.send_message(uid, "🚫 Master Admin only!", reply_markup=sub_admin_kb()); return
            cur = _effective_bakong_token()
            masked = (cur[:8] + "..." + cur[-4:]) if len(cur) > 12 else (("*" * len(cur)) if cur else "(មិនទាន់កំណត់)")
            kb2 = InlineKeyboardMarkup()
            kb2.add(InlineKeyboardButton("✏️ ប្តូរ Token ថ្មី", callback_data="set_bakong:edit", color="progress"))
            kb2.add(InlineKeyboardButton("🧪 Test Token", callback_data="set_bakong:test", color="active"))
            if bakong_cfg.get("token"):
                kb2.add(InlineKeyboardButton("🗑️ Reset (env/default)", callback_data="set_bakong:reset", color="inactive"))
            bot.send_message(uid,
                f"🏦 <b>Bakong Developer Token</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"Token: <code>{masked}</code>\n"
                f"Source: {'📁 runtime' if bakong_cfg.get('token') else '⚙️ env/default'}\n"
                f"📌 ត្រូវការសម្រាប់ button បើក App ធនាគារស្វ័យប្រវត្តិ (ABA/ACLEDA/Bakong) នៅក្រោម QR ដាក់លុយ។\n"
                f"យក Token ពី: https://api-bakong.nbc.gov.kh/register/",
                parse_mode="HTML", reply_markup=kb2); return

        if text == "📝 Welcome Msg":
            if uid != ADMIN_ID:
                bot.send_message(uid, "🚫 Master Admin only!", reply_markup=sub_admin_kb()); return
            cur = BOT_WELCOME_MSG or welcome_cfg.get("custom_msg","")
            kb2 = InlineKeyboardMarkup()
            kb2.add(InlineKeyboardButton("✏️ កែ Welcome Text", callback_data="set_welcome:text", color="progress"))
            kb2.add(InlineKeyboardButton("🗑️ Reset (default)", callback_data="set_welcome:reset", color="inactive"))
            bot.send_message(uid,
                f"📝 <b>Welcome Message</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<code>{cur[:300] if cur else '(default)'}</code>\n\n"
                f"💡 ប្រើ <code>{{}}</code> ដើម្បីដាក់ balance",
                parse_mode="HTML", reply_markup=kb2); return

        if text == "😊 កំណត់ Emoji":
            if uid != ADMIN_ID:
                bot.send_message(uid, "🚫 Master Admin only!", reply_markup=sub_admin_kb()); return
            done_n = sum(1 for v in EMOJI_MAP.values() if v)
            bot.send_message(uid,
                f"😊 <b>Premium Emoji Settings</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"កំណត់រួច: <b>{done_n}/{len(EMOJI_MAP)}</b>\n\n"
                f"ជ្រើសសកម្មភាព:",
                parse_mode="HTML", reply_markup=emoji_menu_kb()); return

        if text.startswith("━━━"):
            bot.send_message(uid, "👇 ជ្រើស menu ខាងក្រោម:", reply_markup=admin_kb()); return

        # ── Settings waiting steps (master admin) ──
        if step == "set_support_text" or (isinstance(step, dict) and step.get("step") == "set_support_text"):
            lang_key = step["lang"] if isinstance(step, dict) else "kh"
            waiting.pop(uid, None)
            if text.strip() == "-":
                support_cfg[lang_key] = ""
                _save(SUPPORT_CFG_FILE, support_cfg)
                bot.send_message(uid, f"✅ Support Message {'(ខ្មែរ)' if lang_key=='kh' else '(English)'} reset ទៅ default!",
                                 reply_markup=admin_kb())
            else:
                support_cfg[lang_key] = text.strip()
                _save(SUPPORT_CFG_FILE, support_cfg)
                bot.send_message(uid, f"✅ Support Message {'(ខ្មែរ)' if lang_key=='kh' else '(English)'} បានរក្សា!",
                                 reply_markup=admin_kb())
            return

        if step == "subadmin_add_id":
            waiting.pop(uid, None)
            if not text.strip().lstrip("-").isdigit():
                bot.send_message(uid, "❌ ត្រូវជាលេខ Telegram ID!", reply_markup=admin_kb()); return
            new_id = int(text.strip())
            if new_id == ADMIN_ID:
                bot.send_message(uid, "⚠️ Master Admin ID មិនចាំបាច់បន្ថែម!", reply_markup=admin_kb()); return
            if new_id not in sub_admins:
                sub_admins.append(new_id)
                _save(SUB_ADMIN_FILE, sub_admins)
            bot.send_message(uid,
                f"✅ <b>Sub Admin បន្ថែម!</b>\n🆔 <code>{new_id}</code>\n"
                f"👥 ចំនួនសរុប: <b>{len(sub_admins)}</b>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if step == "set_camrapid_key":
            waiting.pop(uid, None)
            if text.strip() == "-":
                camrapid_cfg["key"] = ""
                _save(CAMRAPID_CFG_FILE, camrapid_cfg)
                bot.send_message(uid, "✅ CamRapidPay Key reset ទៅ env/default!",
                                 reply_markup=admin_kb())
            else:
                k = text.strip()
                if len(k) < 10:
                    bot.send_message(uid, "❌ Key ខ្លីពេក!", reply_markup=admin_kb()); return
                camrapid_cfg["key"] = k
                _save(CAMRAPID_CFG_FILE, camrapid_cfg)
                masked = k[:8] + "..." + k[-4:] if len(k) > 12 else "*" * len(k)
                bot.send_message(uid, f"✅ CamRapidPay Key ថ្មីបានរក្សា!\n🔑 <code>{masked}</code>",
                                 parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "set_aba_key":
            waiting.pop(uid, None)
            if text.strip() == "-":
                aba_cfg["key"] = ""
                _save(ABA_CFG_FILE, aba_cfg)
                bot.send_message(uid, "✅ ABA PayWay Key reset ទៅ env/default!", reply_markup=admin_kb())
            else:
                k = text.strip()
                if len(k) < 6:
                    bot.send_message(uid, "❌ Key ខ្លីពេក!", reply_markup=admin_kb()); return
                aba_cfg["key"] = k
                _save(ABA_CFG_FILE, aba_cfg)
                masked = k[:6] + "..." + k[-4:] if len(k) > 10 else "*" * len(k)
                bot.send_message(uid, f"✅ ABA PayWay Key ថ្មីបានរក្សា!\n🔑 <code>{masked}</code>",
                                 parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "set_aba_merchant":
            waiting.pop(uid, None)
            if text.strip() == "-":
                aba_cfg["merchant_id"] = ""
                _save(ABA_CFG_FILE, aba_cfg)
                bot.send_message(uid, "✅ ABA PayWay Merchant ID reset ទៅ env/default!", reply_markup=admin_kb())
            else:
                aba_cfg["merchant_id"] = text.strip()
                _save(ABA_CFG_FILE, aba_cfg)
                bot.send_message(uid, f"✅ ABA PayWay Merchant ID ថ្មីបានរក្សា!\n🏪 <code>{text.strip()}</code>",
                                 parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "set_webhook_url":
            waiting.pop(uid, None)
            if text.strip() == "-":
                webhook_cfg["url"] = ""
                _save(WEBHOOK_CFG_FILE, webhook_cfg)
                bot.send_message(uid,
                    f"✅ Webhook URL reset ទៅ Auto-detect!\n🌐 <code>{_effective_webhook_url()}</code>",
                    parse_mode="HTML", reply_markup=admin_kb())
            else:
                u = text.strip()
                if not (u.startswith("http://") or u.startswith("https://")):
                    bot.send_message(uid,
                        "❌ URL ត្រូវចាប់ផ្ដើមដោយ <code>http://</code> ឬ <code>https://</code>!",
                        parse_mode="HTML", reply_markup=admin_kb()); return
                webhook_cfg["url"] = u
                _save(WEBHOOK_CFG_FILE, webhook_cfg)
                bot.send_message(uid, f"✅ Webhook URL ថ្មីបានរក្សា!\n🌐 <code>{u}</code>",
                                 parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "set_bakong_token":
            waiting.pop(uid, None)
            if text.strip() == "-":
                bakong_cfg["token"] = ""
                _save(BAKONG_CFG_FILE, bakong_cfg)
                bot.send_message(uid, "✅ Bakong Token reset ទៅ env/default!",
                                 reply_markup=admin_kb())
            else:
                k = text.strip()
                if len(k) < 10:
                    bot.send_message(uid, "❌ Token ខ្លីពេក!", reply_markup=admin_kb()); return
                bakong_cfg["token"] = k
                _save(BAKONG_CFG_FILE, bakong_cfg)
                masked = k[:8] + "..." + k[-4:] if len(k) > 12 else "*" * len(k)
                bot.send_message(uid, f"✅ Bakong Token ថ្មីបានរក្សា!\n🏦 <code>{masked}</code>\n"
                                       f"🔘 Button បើក App ធនាគារនឹងបង្ហាញលើក QR ថ្មីៗចាប់ពីនេះទៅ",
                                 parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "set_welcome_msg_text":
            waiting.pop(uid, None)
            if text.strip() == "-":
                welcome_cfg.pop("custom_msg", None)
                _save(WELCOME_SETTINGS_FILE, welcome_cfg)
                bot.send_message(uid, "✅ Welcome Message reset ទៅ default!", reply_markup=admin_kb())
            else:
                welcome_cfg["custom_msg"] = text.strip()
                _save(WELCOME_SETTINGS_FILE, welcome_cfg)
                bot.send_message(uid, "✅ Welcome Message ថ្មីបានរក្សា!", reply_markup=admin_kb())
            return

        _kb_reply = admin_kb() if _is_master_admin else sub_admin_kb()
        bot.send_message(uid, "❓ ប្រើប៊ូតុង Menu ខាងក្រោម។", reply_markup=_kb_reply); return

    # ════════════════════════════════════════
    #  USER SECTION
    # ════════════════════════════════════════

    # ── Custom amount step ──
    if isinstance(step, dict) and step.get("step") == "dep_custom_amt":
        try:
            amount = float(text.replace("$","").replace(",","").strip())
            if amount <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! ឧ: <code>3</code> ឬ <code>7.50</code>",
                             parse_mode="HTML", reply_markup=cancel_kb()); return
        waiting.pop(uid, None)
        _process_deposit(uid, uid_str, amount, None)
        return

    # Admin confirm deposit — enter amount
    if isinstance(step, dict) and step.get("step") == "adm_confirm_dep" and uid == ADMIN_ID:
        dep_id = step.get("dep_id")
        dep    = smm_deps.get(dep_id)
        if not dep:
            bot.send_message(uid, "❌ Deposit រកមិនឃើញ", reply_markup=admin_kb())
            waiting.pop(uid, None); return
        try:
            paid = float(text.replace("$","").strip())
            if paid <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! ឧ: <code>5.00</code>", parse_mode="HTML"); return
        waiting.pop(uid, None)
        user_uid = int(dep["uid"])
        # Credit balance manually — recompute auto bonus against the actual paid amount
        promo_bonus = float(dep.get("promo_bonus") or 0)
        auto_bonus  = _auto_dep_bonus(paid)
        bonus = round(promo_bonus + auto_bonus, 2)
        total = round(paid + bonus, 2)
        add_bal(user_uid, total)
        smm_deps[dep_id]["status"]      = "confirmed"
        smm_deps[dep_id]["amount"]      = paid
        smm_deps[dep_id]["bonus"]       = bonus
        smm_deps[dep_id]["auto_bonus"]  = auto_bonus
        _save(SMM_DEP_FILE, smm_deps)
        if dep.get("promo") and promo_bonus > 0:
            confirm_promo(dep["promo"], user_uid)
        new_b = bal(user_uid)
        msg = (f"✅ <b>ដាក់លុយបានជោគជ័យ!</b>\n"
               f"━━━━━━━━━━━━━━━━━━\n"
               f"💰 បញ្ញើ: <b>${paid:.2f}</b>")
        if promo_bonus > 0:
            msg += f"\n🎟️ Promo Bonus: <b>+${promo_bonus:.2f}</b>"
        if auto_bonus > 0:
            msg += f"\n🎁 Auto Bonus: <b>+${auto_bonus:.2f}</b>"
        msg += f"\n💳 Balance: <b>${new_b:.2f}</b>"
        try: bot.send_message(user_uid, msg, parse_mode="HTML", reply_markup=main_kb(user_uid))
        except Exception as _e: logger.debug(f"[silent] {_e}")
        bot.send_message(uid,
            f"✅ <b>Confirmed!</b>\n👤 <code>{dep['uid']}</code>\n💰 <b>${paid:.2f}</b>",
            parse_mode="HTML", reply_markup=admin_kb())
        return

    # ── Manual Deposit: User វាយចំនួនលុយ ──────────────────────────
    if step == "await_manual_dep_amount":
        try:
            amt = float(text.strip().replace("$", ""))
            if amt <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(uid, "❌ សូមវាយចំនួនលុយជាលេខ (ឧ. 5 ឬ 5.50)", reply_markup=cancel_kb())
            return
        waiting[uid] = {"step": "await_manual_dep_proof", "amount": amt}
        bot.send_message(uid,
            f"💰 ចំនួន: <b>${amt:.2f}</b>\n\n"
            f"📷 សូមផ្ញើ <b>Screenshot ភស្តុតាងផ្ទេរប្រាក់</b> (Bakong/App ធនាគារ):",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

    # SMM link step
    if isinstance(step, dict) and step.get("step") == "smm_link":
        slug  = step["slug"]
        qty   = step["qty"]
        price = step["price"]
        link  = text.strip()
        s = smm_services.get(slug)
        if not s:
            waiting.pop(uid, None)
            bot.send_message(uid, t(uid, "fallback"), reply_markup=main_kb(uid)); return
        ok, err = _validate_order_link(link, slug, s)
        if not ok:
            # មិន pop `waiting` ទេ — ឲ្យ user ព្យាយាមផ្ញើ Link ម្ដងទៀត
            bot.send_message(uid, err, parse_mode="HTML", reply_markup=cancel_kb())
            return
        waiting.pop(uid, None)
        if bal(uid) < price:
            bot.send_message(uid,
                f"❌ Balance មិនគ្រប់!\n💳 ${bal(uid):.2f} | Need: ${price:.2f}",
                parse_mode="HTML", reply_markup=main_kb(uid))
            # ជូនដំណឹង Admin ថា User ចង់ Order ប៉ុន្តែលុយមិនគ្រប់ — ជា lead ល្អ
            # សម្រាប់ Admin ទាក់ទងទៅ User ដើម្បីលើកទឹកចិត្តឲ្យបញ្ចូលលុយ
            try: bot.send_message(ADMIN_ID,
                f"💸 <b>User ចង់ Order ប៉ុន្តែ Balance មិនគ្រប់!</b>\n"
                f"👤 {_user_display(uid_str)}\n"
                f"📦 {s.get('label',slug)}\n"
                f"🔢 {qty:,} | 💰 ត្រូវការ: ${price:.4f}\n"
                f"💳 Balance បច្ចុប្បន្ន: ${bal(uid):.2f}",
                parse_mode="HTML")
            except Exception as _e: logger.debug(f"[silent] {_e}")
            return
        ded_bal(uid, price)
        key = smm_api.get("key",""); api_url = smm_api.get("url","")
        res = None
        api_failed = False; api_err_msg = ""
        if key and api_url and not s.get("manual"):
            res = _smm_api_post({"key":key,"action":"add","service":s["api_id"],"link":link,"quantity":qty})
            if not res or not isinstance(res, dict) or res.get("error") or not res.get("order"):
                api_failed = True
                api_err_msg = (str(res.get("error")) if isinstance(res, dict) and res.get("error")
                               else "SMM API មិនឆ្លើយតប ឬបញ្ជាទិញមិនជោគជ័យ")
        # ── API Order បរាជ័យ → សងលុយវិញភ្លាម កុំឲ្យ User ខាតលុយឥតបានការ ──
        if api_failed:
            add_bal(uid, price)
            bot.send_message(uid,
                f"❌ <b>Order មិនជោគជ័យ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📊 {s.get('label',slug)}\n"
                f"⚠️ មូលហេតុ: <i>{api_err_msg}</i>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 លុយត្រូវបានសងវិញ: <b>${price:.2f}</b>\n"
                f"💳 Balance: <b>${bal(uid):.2f}</b>\n"
                f"សូមព្យាយាមម្ដងទៀត ឬទាក់ទង Admin។",
                parse_mode="HTML", reply_markup=main_kb(uid))
            try: bot.send_message(ADMIN_ID,
                f"⚠️ <b>SMM Order បរាជ័យ (Auto-Refunded)</b>\n"
                f"👤 {_user_display(uid_str)}\n"
                f"📊 {s.get('label',slug)} | {qty:,} | ${price:.4f}\n"
                f"🔗 <code>{link}</code>\n"
                f"⚠️ {api_err_msg}",
                parse_mode="HTML")
            except Exception as _e: logger.debug(f"[silent] {_e}")
            return
        api_oid = str(res.get("order","")) if res else ""
        oid = _make_order_id()
        smm_orders[oid] = {
            "uid":uid_str,"slug":slug,"label":s.get("label",slug),
            "qty":qty,"price":price,"link":link,"api_order_id":api_oid,
            "status":"pending","ts":int(time.time())
        }
        _save(SMM_ORD_FILE, smm_orders)

        is_tiktok_promote = s.get("flat_price") and "tiktok" in slug.lower()
        is_manual = s.get("manual", False)

        if is_tiktok_promote:
            bot.send_message(uid,
                f"✅ <b>Order TikTok Promote បានជោគជ័យ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"🎵 {s.get('label',slug)}\n"
                f"💰 <b>${price:.2f}</b>\n"
                f"🔗 <code>{link}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⏳ <b>ចាំ Admin ដំណើរការ 5-15 នាទី</b>\n\n"
                f"📱 <b>រំឭក!</b> ចូល TikTok:\n"
                f"Inbox → System notifications\n"
                f"→ Promote Assistant → <b>Respond</b>\n"
                f"→ Authorize → <b>Confirm</b> ✅\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Balance: <b>${bal(uid):.2f}</b>",
                parse_mode="HTML", reply_markup=main_kb(uid))
        else:
            bot.send_message(uid,
                f"✅ <b>បញ្ជា SMM បានជោគជ័យ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"📊 {s.get('label',slug)}\n"
                f"🔢 ចំនួន: <b>{qty:,}</b> | 💰 <b>${price:.4f}</b>\n"
                f"🔗 <code>{link}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Balance: <b>${bal(uid):.2f}</b>",
                parse_mode="HTML", reply_markup=main_kb(uid))

        # ── Notify Admin ──
        udisp = _user_display(uid_str)
        if is_tiktok_promote:
            admin_msg = (
                f"🎵 <b>TikTok Promote Order!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 {udisp}\n"
                f"💰 <b>${price:.2f}</b>\n"
                f"🔗 <code>{link}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📋 <b>Admin Steps:</b>\n"
                f"1️⃣ ចូល TikTok → video → Promote\n"
                f"2️⃣ ជ្រើស budget → ផ្ញើ invite\n"
                f"3️⃣ User នឹង Accept → ចុច ✅ Done"
            )
            kb_adm = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Done",   callback_data=f"manord:done:{oid}", color="active"),
                InlineKeyboardButton("❌ Reject", callback_data=f"manord:reject:{oid}", color="inactive"),
            ]])
            try: bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=kb_adm)
            except Exception as _e: logger.debug(f"[silent] {_e}")
        elif is_manual:
            admin_msg = (
                f"✍️ <b>Manual SMM Order</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 {udisp}\n"
                f"📊 {s.get('label',slug)}\n"
                f"🔢 {qty:,} | 💰 ${price:.4f}\n"
                f"🔗 <code>{link}</code>"
            )
            kb_adm = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Done",   callback_data=f"manord:done:{oid}", color="active"),
                InlineKeyboardButton("❌ Reject", callback_data=f"manord:reject:{oid}", color="inactive"),
            ]])
            try: bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=kb_adm)
            except Exception as _e: logger.debug(f"[silent] {_e}")
        else:
            try: bot.send_message(ADMIN_ID,
                f"📊 <b>SMM Order</b>\n"
                f"🆔 <code>{oid}</code>\n"
                f"👤 {udisp}\n"
                f"📦 {s.get('label',slug)}\n"
                f"🔢 {qty:,} | 💰 ${price:.4f}\n"
                f"🔗 <code>{link}</code>",
                parse_mode="HTML")
            except Exception as _e: logger.debug(f"[silent] {_e}")
        return

    # Track order
    if step == "track_order":
        oid = text.strip().upper()
        o   = smm_orders.get(oid)
        waiting.pop(uid, None)
        if not o or o.get("uid") != uid_str:
            bot.send_message(uid, "❌ Order រកមិនឃើញ!", reply_markup=main_kb(uid)); return
        # Sync ស្ថានភាព Live ពី Supplier API ភ្លាមៗ (មិនចាំបាច់រង់ចាំ Poll Cycle បន្ទាប់ទេ) —
        # បើ Order ត្រូវ Cancel/Partial នៅខាង Supplier រួច Refund នឹងកើតឡើងស្វ័យប្រវត្តិទីនេះតែម្តង
        if o.get("status") == "pending" and o.get("api_order_id"):
            _smm_sync_order(oid)
            o = smm_orders.get(oid, o)
        bot.send_message(uid,
            f"📊 <b>SMM Order: <code>{oid}</code></b>\n"
            f"{o.get('label','?')}\n"
            f"🔢 ចំនួន: {o.get('qty','?'):,} | 💰 ${o.get('price',0):.4f}\n"
            f"🔗 <code>{o.get('link','?')}</code>\n"
            f"📌 API: <code>{o.get('api_order_id','?')}</code>\n"
            f"✅ ស្ថានភាព: <b>{o.get('status','?')}</b>",
            parse_mode="HTML", reply_markup=main_kb(uid)); return

    # ── Main menu buttons ──
    if text in ("📊 SMM Services", "🛒 បញ្ជាទិញសេវា", "🛒 Order Service"):
        if not smm_services:
            bot.send_message(uid,
                "❌ គ្មាន SMM Service ទេ\n(Admin ចូល ⚙️ កំណត់ SMM API ដើម្បី import)",
                reply_markup=main_kb(uid)); return
        bot.send_message(uid,
            "📊 <b>SMM Services</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Platform:",
            parse_mode="HTML", reply_markup=smm_cat_kb()); return

    if text in ("💰 ដាក់ប្រាក់", "💰 Top Up", "💸 បញ្ចូលលុយ", "💸 Top Up"):
        b = bal(uid)
        waiting.pop(uid, None)
        bonus_line = ""
        if dep_bonus_cfg.get("enabled", True) and float(dep_bonus_cfg.get("pct", 0)) > 0:
            min_amt = float(dep_bonus_cfg.get("min_amount", 1.0))
            pct     = float(dep_bonus_cfg.get("pct", 5.0))
            bonus_line = (
                f"\n🎁 <i>ដាក់ចាប់ពី ${min_amt:.2f} ឡើងទៅ ទទួល Bonus {pct:.0f}% ភ្លាមៗ!</i>\n"
                if lang == "kh" else
                f"\n🎁 <i>Deposit ${min_amt:.2f}+ and get {pct:.0f}% bonus instantly!</i>\n"
            )
        bot.send_message(uid,
            f"💸 <b>{'ដាក់លុយ' if lang=='kh' else 'Top Up'}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 Balance: <b>${b:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━{bonus_line}\n"
            f"{'ជ្រើស ចំនួន:' if lang=='kh' else 'Choose Amount:'}",
            parse_mode="HTML", reply_markup=deposit_amt_kb(uid)); return

    if text in ("📦 ការបញ្ជា", "📦 Orders", "📋 ប្រវត្តិការបញ្ជាទិញ", "📋 Order History"):
        my_orders = {oid: o for oid, o in smm_orders.items() if o.get("uid") == uid_str}
        if not my_orders:
            bot.send_message(uid,
                "📦 <b>ការបញ្ជា</b>\n\n❌ គ្មាន Order ទេ!",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        lines = ["📦 <b>ការបញ្ជា SMM</b>\n━━━━━━━━━━━━━━━━━━"]
        for oid, o in sorted(my_orders.items(), key=lambda x: x[1].get("ts",0), reverse=True)[:10]:
            lines.append(f"📊 <code>{oid}</code> — {o.get('label','?')} x{o.get('qty','?')} | ${o.get('price',0):.4f} | {o.get('status','?')}")
        bot.send_message(uid, "\n".join(lines), parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("📋 ប្រវត្តិ", "📋 History"):
        my_orders = {oid: o for oid, o in smm_orders.items() if o.get("uid") == uid_str}
        if not my_orders:
            bot.send_message(uid,
                "📋 <b>ប្រវត្តិ</b>\n\n❌ គ្មាន Order ទេ!",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        lines = ["📋 <b>ប្រវត្តិ</b>\n━━━━━━━━━━━━━━━━━━"]
        for oid, o in sorted(my_orders.items(), key=lambda x: x[1].get("ts",0), reverse=True)[:15]:
            dt = datetime.datetime.fromtimestamp(o.get("ts",0)).strftime("%d/%m %H:%M")
            lines.append(f"📊 <code>{oid}</code> | {o.get('label','?')} x{o.get('qty','?')} | ${o.get('price',0):.4f} | {o.get('status','?')} | {dt}")
        bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("👜 កាបូបលុយ", "👜 Wallet", "👤 តំណាំការគណនី", "👤 គណនី", "👤 My Account"):
        waiting.pop(uid, None)
        b = bal(uid)
        my_deps = [(k, v) for k, v in smm_deps.items() if v.get("uid") == uid_str]
        confirmed = sum(float(v.get("amount") or 0) for _, v in my_deps if v.get("status") == "confirmed")
        pending   = sum(float(v.get("amount") or 0) for _, v in my_deps if v.get("status") == "pending")
        total_orders = sum(1 for o in smm_orders.values() if o.get("uid") == uid_str)
        u = users_db.get(uid_str, {})
        name = u.get("name", "") or ""
        uname = f"@{u['username']}" if u.get("username") else ""
        if lang == "kh":
            msg = (
                f"👤 <b>គណនីរបស់ខ្ញុំ</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🙍 ឈ្មោះ: <b>{name}</b>  {uname}\n"
                f"🆔 ID: <code>{uid_str}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Balance: <b>${b:.2f}</b>\n"
                f"✅ សរុបដាក់: <b>${confirmed:.2f}</b>\n"
                f"⏳ រង់ចាំ: <b>${pending:.2f}</b>\n"
                f"📦 Orders: <b>{total_orders}</b>"
            )
        else:
            msg = (
                f"👤 <b>My Account</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🙍 Name: <b>{name}</b>  {uname}\n"
                f"🆔 ID: <code>{uid_str}</code>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Balance: <b>${b:.2f}</b>\n"
                f"✅ Total deposited: <b>${confirmed:.2f}</b>\n"
                f"⏳ Pending: <b>${pending:.2f}</b>\n"
                f"📦 Orders: <b>{total_orders}</b>"
            )
        bot.send_message(uid, msg, parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("Track 🔍", "🔍 Track Order", "🔍 តាមដានការបញ្ជាទិញ"):
        bot.send_message(uid,
            "🔍 <b>តាមដាន Order</b>\nផ្ញើ Order ID (ឧ: KZ12345):",
            parse_mode="HTML", reply_markup=cancel_kb())
        waiting[uid] = "track_order"; return

    if text in ("💬 Support", "💬 ជំនួយ"):
        lang = get_lang(uid)
        custom = support_cfg.get(lang) or support_cfg.get("kh") or ""
        msg = custom if custom else t(uid, "support_msg")
        bot.send_message(uid, msg, parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("💡 របៀបប្រើប្រាស់", "💡 How to Use"):
        video_id = tutorial_cfg.get("file_id")
        if video_id:
            try:
                bot.send_video(uid, video_id, reply_markup=main_kb(uid))
            except Exception as e:
                logger.warning(f"⚠️ send tutorial video failed: {e}")
                bot.send_message(uid, t(uid, "how_to_use"), parse_mode="HTML", reply_markup=main_kb(uid))
        else:
            bot.send_message(uid, t(uid, "how_to_use"), parse_mode="HTML", reply_markup=main_kb(uid))
        return

    bot.send_message(uid, t(uid, "fallback"), reply_markup=main_kb(uid))

# ═══════════════════════════════════════════════════════════
#  FLASK CONTROL SERVER
# ═══════════════════════════════════════════════════════════
flask_app = Flask(__name__)

def _check_key():
    key = flask_request.args.get("key") or (flask_request.get_json(silent=True) or {}).get("key")
    return key == CONTROL_KEY

@flask_app.route("/health")
def health():
    return jsonify({"status": "running", "bot": _bot_brand()})

@flask_app.route("/webhook/camrapid", methods=["POST"])
def camrapid_webhook():
    """ទទួល Webhook ពី CamRapidPay ពេល Payment ចូល — ធ្វើឲ្យ Confirm លឿនជាង Poll ។
    ចំណាំ: Bot នៅតែ Poll ជា Backup ដដែល (_watch_deposit) ដូច្នេះ Route នេះជា Bonus
    មិនមែនជា Dependency តឹងរឹងទេ — បើមិនមាន Webhook ក៏ដំណើរការធម្មតា។"""
    try:
        data = flask_request.get_json(silent=True) or {}
        reference = data.get("reference") or data.get("bill_number") or ""
        logger.info(f"[camrapid_webhook] received: {data}")
        if reference:
            for dep_id, dep in list(smm_deps.items()):
                if dep.get("reference") == reference and dep.get("status") == "pending":
                    # _watch_deposit នឹងបន្ត Detect នៅ Poll ជុំបន្ទាប់ដោយស្វ័យប្រវត្តិ —
                    # Route នេះគ្រាន់តែ Log ទុកសម្រាប់ Debug, មិន Mutate State ដោយផ្ទាល់ទេ
                    # ដើម្បីជៀសវាង Race Condition ជាមួយ Thread _watch_deposit ដែលកំពុង Poll ស្រាប់។
                    break
        return jsonify({"received": True}), 200
    except Exception as e:
        logger.error(f"[camrapid_webhook] error: {e}")
        return jsonify({"received": False}), 200

@flask_app.route("/status")
def status():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({
        "status": "running",
        "users": len(users_db),
        "smm_orders": len(smm_orders),
        "smm_services": len(smm_services),
        "wallets": len(wallets),
    })

@flask_app.route("/shutdown", methods=["GET", "POST"])
def shutdown():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    logger.warning("🛑 Shutdown requested!")
    try:
        bot.send_message(ADMIN_ID, "🛑 <b>Bot កំពុងបិទ...</b>", parse_mode="HTML")
        time.sleep(1)
    except Exception as _e: logger.debug(f"[silent] {_e}")
    def _stop():
        time.sleep(0.5)
        bot.stop_polling()
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({"status": "shutting_down"})

@flask_app.route("/restart", methods=["GET", "POST"])
def restart():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    logger.warning("🔄 Restart requested!")
    try:
        bot.send_message(ADMIN_ID, "🔄 <b>Bot កំពុង Restart...</b>", parse_mode="HTML")
        time.sleep(1)
    except Exception as _e: logger.debug(f"[silent] {_e}")
    def _restart():
        time.sleep(0.5)
        bot.stop_polling()
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=_restart, daemon=True).start()
    return jsonify({"status": "restarting"})

@flask_app.route("/broadcast_web", methods=["POST"])
def broadcast_web():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    data = flask_request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    sent = failed = 0
    for u_id in list(users_db.keys()):
        try:
            bot.send_message(int(u_id), text, parse_mode="HTML")
            sent += 1
        except: failed += 1
        time.sleep(0.05)
    return jsonify({"sent": sent, "failed": failed})

def run_flask():
    logger.info(f"🌐 Control Server running on port {CONTROL_PORT}")
    flask_app.run(host="0.0.0.0", port=CONTROL_PORT, debug=False, use_reloader=False)

def _self_ping():
    """Ping self every 5 min to prevent Render free tier spin down"""
    import urllib.request
    while True:
        try:
            time.sleep(300)  # 5 minutes
            render_url = os.getenv("RENDER_EXTERNAL_URL", "")
            if render_url:
                urllib.request.urlopen(f"{render_url}/health", timeout=10)
                logger.info("✅ Self-ping OK")
        except Exception as e:
            logger.warning(f"⚠️ Self-ping failed: {e}")

def _bot_polling_with_retry():
    """Polling with auto-reconnect on network error"""
    while True:
        try:
            logger.info("🤖 Bot polling ចាប់ផ្ដើម...")
            bot.infinity_polling(timeout=20, long_polling_timeout=15)
        except Exception as e:
            logger.warning(f"⚠️ Polling error: {e} — Retry in 10s...")
            time.sleep(10)

# ═══════════════════════════════════════════════════════════
#  DAILY AUTO-REPORT — ផ្ញើ Profit + Top report ដល់ Admin ស្វ័យប្រវត្តិ
#  រៀងរាល់ថ្ងៃម្តង តាមម៉ោងកំណត់ (default 08:00 ម៉ោងកម្ពុជា UTC+7)
# ═══════════════════════════════════════════════════════════
def _daily_report_scheduler():
    """រត់ជា background thread — ពិនិត្យរាល់នាទី ថាដល់ម៉ោងផ្ញើ report ថ្ងៃនេះ
    ឬនៅ។ ប្រើ _dpath persistence ដើម្បីកុំឲ្យផ្ញើ 2 ដងក្នុងថ្ងៃតែមួយ ទោះបី bot
    restart ក៏ដោយ (ចងចាំ 'last_sent_date')។"""
    while True:
        try:
            time.sleep(60)
            if not daily_report_cfg.get("enabled", True):
                continue
            now_kh = datetime.datetime.now(_KH_TZ)
            today  = now_kh.strftime("%Y-%m-%d")
            if now_kh.hour != int(daily_report_cfg.get("hour", 8)):
                continue
            if daily_report_cfg.get("last_sent_date") == today:
                continue
            daily_report_cfg["last_sent_date"] = today
            _save(DAILY_REPORT_FILE, daily_report_cfg)
            txt = (f"⏰ <b>របាយការណ៍ប្រចាំថ្ងៃ</b> — {today}\n"
                   f"━━━━━━━━━━━━━━━━━━\n\n" + _profit_report_text() +
                   "\n\n" + _top_report_text(7))
            bot.send_message(ADMIN_ID, txt, parse_mode="HTML")
            logger.info(f"📤 Daily report sent for {today}")
        except Exception as e:
            logger.warning(f"⚠️ Daily report scheduler error: {e}")

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info(f"🚀 Kaijaklike Bot [{INSTANCE_NAME or 'MASTER'}] កំពុងចាប់ផ្ដើម...")
    logger.info(f"🔑 Control Key: {CONTROL_KEY}  ← ដូរនៅ CONTROL_KEY!")
    logger.info(f"📊 Services loaded: {len(smm_services)}")
    _warm_stripped_text_map()
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=_self_ping, daemon=True).start()
    threading.Thread(target=_smm_order_watcher, daemon=True).start()
    threading.Thread(target=_daily_report_scheduler, daemon=True).start()
    if IS_MASTER:
        for _cln_name, _cln_cfg in clone_registry.items():
            try:
                _spawn_clone(_cln_name, _cln_cfg)
                logger.info(f"🤖 Autostart clone '{_cln_name}' on port {_cln_cfg['port']}")
            except Exception as _e:
                logger.error(f"Autostart clone '{_cln_name}' failed: {_e}")
        threading.Thread(target=_clone_watchdog, daemon=True).start()
    _bot_polling_with_retry()
