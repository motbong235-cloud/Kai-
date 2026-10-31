# -*- coding: utf-8 -*-
"""
Kai JakLike SMM Bot v1
--------------------
Telegram SMM (Social Media Marketing) Panel bot.

Features:
- Modern UI: Reply keyboard (main menu) + Inline keyboard (navigation/actions)
- Admin can add UNLIMITED SMM panels (any provider using the standard
  "api_url + api_key" style API: action=add / status / balance / services)
- For each panel, admin can:
    * Sync services directly from the panel's API (action=services)
    * Search/browse synced services and map them into the bot with a
      custom Khmer label, selling price and min/max order
    * Or add a service manually by typing its Service ID
- Users can browse panels -> services -> place an order (link + quantity)
- Simple internal wallet system (admin tops up users manually) so orders
  can be charged/deducted automatically
- Order history + live status refresh (calls panel action=status)

Stack matches Kairozen's usual pattern: pyTelegramBotAPI (telebot),
JSON file persistence, deployable on Render (DATA_DIR env for persistent
disk) or locally via Termux.

ENV VARS:
  BOT_TOKEN   -> Telegram bot token from BotFather (required)
  DATA_DIR    -> folder to store JSON data (default: current folder)
  ADMIN_IDS   -> comma separated telegram user ids allowed as admin
                 (defaults to the Kairozen admin id below)
"""

import os
import json
import time
import base64
import threading
from io import BytesIO
from datetime import datetime

import requests
import qrcode
from PIL import Image, ImageDraw, ImageFont
import telebot
from telebot import types
from flask import Flask

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

DATA_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)

_default_admins = "8266854899"
ADMIN_IDS = set(
    int(x) for x in os.environ.get("ADMIN_IDS", _default_admins).split(",") if x.strip()
)

PANELS_FILE = os.path.join(DATA_DIR, "panels.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
DEPOSITS_FILE = os.path.join(DATA_DIR, "deposits.json")

# --- CamRapidPay KHQR auto-payment config ---
# Set these in Render Environment Variables. Field names (QR_FIELD / MD5_FIELD)
# can be adjusted if your CamRapidPay account returns different JSON keys.
CAMRAPIDPAY_BASE_URL = os.environ.get("CAMRAPIDPAY_BASE_URL", "https://api.camrapidpay.com")
CAMRAPIDPAY_API_KEY = os.environ.get("CAMRAPIDPAY_API_KEY", "")
CAMRAPIDPAY_QR_FIELD = os.environ.get("CAMRAPIDPAY_QR_FIELD", "qr")
CAMRAPIDPAY_MD5_FIELD = os.environ.get("CAMRAPIDPAY_MD5_FIELD", "md5")
TOPUP_POLL_SECONDS = int(os.environ.get("TOPUP_POLL_SECONDS", "5"))
TOPUP_TIMEOUT_SECONDS = int(os.environ.get("TOPUP_TIMEOUT_SECONDS", "600"))  # 10 min

# --- Brand assets: fonts used to render the QR payment card ---
# Fonts are downloaded once (best-effort) into ./assets/fonts on first boot,
# since Render's Python image doesn't ship with these by default. If a font
# fails to download (no internet at build time, etc.) the card silently
# falls back to a plain default font instead of crashing.
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")
os.makedirs(ASSETS_DIR, exist_ok=True)

FONT_SOURCES = {
    "Poppins-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf",
    "Poppins-SemiBold.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-SemiBold.ttf",
    "Poppins-Medium.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf",
    "Poppins-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
    "Battambang-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/battambang/Battambang-Bold.ttf",
    "Battambang-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/battambang/Battambang-Regular.ttf",
}


def ensure_fonts():
    """Best-effort download of brand fonts (Poppins for Latin, Battambang
    for Khmer) so the QR card renders with real typography instead of the
    default bitmap font. Safe to call every boot — skips files already on
    disk and never raises."""
    for fname, url in FONT_SOURCES.items():
        path = os.path.join(ASSETS_DIR, fname)
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            continue
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(path, "wb") as f:
                    f.write(r.content)
        except Exception:
            pass


def brand_font(name, size):
    path = os.path.join(ASSETS_DIR, name)
    try:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def khmer_font_available():
    p = os.path.join(ASSETS_DIR, "Battambang-Regular.ttf")
    return os.path.exists(p) and os.path.getsize(p) > 1000

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# in-memory conversation state per chat_id
# state = {"step": "...", "data": {...}}
user_states = {}

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# PERSISTENCE HELPERS
# ---------------------------------------------------------------------------


def _load(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, data):
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_panels():
    return _load(PANELS_FILE, {})


def save_panels(data):
    _save(PANELS_FILE, data)


def load_users():
    return _load(USERS_FILE, {})


def save_users(data):
    _save(USERS_FILE, data)


def load_orders():
    return _load(ORDERS_FILE, {})


def save_orders(data):
    _save(ORDERS_FILE, data)


def load_deposits():
    return _load(DEPOSITS_FILE, {})


def save_deposits(data):
    _save(DEPOSITS_FILE, data)


def get_user(chat_id):
    users = load_users()
    key = str(chat_id)
    if key not in users:
        users[key] = {"balance": 0, "joined": datetime.utcnow().isoformat()}
        save_users(users)
    return users[key]


def update_user(chat_id, **kwargs):
    users = load_users()
    key = str(chat_id)
    if key not in users:
        users[key] = {"balance": 0, "joined": datetime.utcnow().isoformat()}
    users[key].update(kwargs)
    save_users(users)
    return users[key]


def is_admin(chat_id):
    return chat_id in ADMIN_IDS


# ---------------------------------------------------------------------------
# SMM PANEL API CLIENT (generic — works with most standard SMM panel APIs)
# ---------------------------------------------------------------------------


def panel_call(panel, params, timeout=20):
    """POST to a panel's API with key + params merged in."""
    api_url = panel["api_url"]
    api_key = panel["api_key"]
    payload = {"key": api_key}
    payload.update(params)
    try:
        r = requests.post(api_url, data=payload, timeout=timeout)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, str(e)


def panel_get_services(panel):
    return panel_call(panel, {"action": "services"})


def panel_get_balance(panel):
    return panel_call(panel, {"action": "balance"})


def panel_add_order(panel, service_id, link, quantity):
    return panel_call(
        panel, {"action": "add", "service": service_id, "link": link, "quantity": quantity}
    )


def panel_order_status(panel, order_id):
    return panel_call(panel, {"action": "status", "order": order_id})


# ---------------------------------------------------------------------------
# AUTO PAYMENT — CamRapidPay KHQR (Bakong)
# ---------------------------------------------------------------------------


def camrapidpay_create_payment(amount, currency="USD"):
    """Create a KHQR payment request. Returns (ok, data_or_error)."""
    url = f"{CAMRAPIDPAY_BASE_URL}/api/v1/khqr/create-payments"
    headers = {"Authorization": f"Bearer {CAMRAPIDPAY_API_KEY}", "Content-Type": "application/json"}
    payload = {"amount": amount, "currency": currency}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, str(e)


def camrapidpay_check_transaction(md5):
    """Check if a KHQR payment has been paid. Returns (ok, data_or_error)."""
    url = f"{CAMRAPIDPAY_BASE_URL}/check-transaction-api"
    headers = {"Authorization": f"Bearer {CAMRAPIDPAY_API_KEY}"}
    try:
        r = requests.get(url, params={"md5": md5}, headers=headers, timeout=20)
        r.raise_for_status()
        return True, r.json()
    except Exception as e:
        return False, str(e)


def render_qr_image(qr_value):
    """Turn either a raw base64 PNG, a data-URI, or a KHQR EMV string into
    a PIL Image (RGB) ready to be composited onto the brand card."""
    if not qr_value:
        return None
    if isinstance(qr_value, str) and qr_value.startswith("data:image"):
        qr_value = qr_value.split(",", 1)[1]
    # try treating it as base64-encoded image data first
    try:
        raw = base64.b64decode(qr_value, validate=True)
        if raw[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1"):
            return Image.open(BytesIO(raw)).convert("RGB")
    except Exception:
        pass
    # otherwise treat it as a raw KHQR / EMV string and render a QR code
    qr = qrcode.QRCode(border=1, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(qr_value)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


# ---------------------------------------------------------------------------
# BRANDED QR PAYMENT CARD
# ---------------------------------------------------------------------------
#
# Design tokens for the "Kai JakLike" brand:
#   ink        #0B0B10  — page background, near-black with a cool undertone
#   panel      #16151D  — card surface
#   panel-2    #1E1D27  — inner chip / status pill surface
#   paper      #FAF7F2  — warm-white QR mounting panel
#   flame      #FF4D6D  — primary accent (energy / "like")
#   gold       #FFB13D  — secondary accent, paired with flame in gradients
#   mint       #34D399  — success/paid state only
#   text       #F5F3EF  — primary text on dark
#   muted      #8B8996  — secondary/caption text
#
# Signature element: a ticket-style perforation (torn-stub look) between the
# QR panel and the payment details, echoing a paid "top-up voucher" rather
# than a generic card. The header uses a small dot grid that echoes a QR
# module pattern instead of a decorative flourish.

C_INK = (11, 11, 16)
C_PANEL = (22, 21, 29)
C_PANEL2 = (30, 29, 39)
C_PAPER = (250, 247, 242)
C_FLAME = (255, 77, 109)
C_GOLD = (255, 177, 61)
C_MINT = (52, 211, 153)
C_TEXT = (245, 243, 239)
C_MUTED = (139, 137, 150)
C_DOT = (40, 39, 50)


def _hgrad(size, c1, c2):
    """Horizontal linear gradient image, c1 -> c2."""
    w, h = size
    grad = Image.new("RGB", (w, 1))
    for x in range(w):
        t = x / max(w - 1, 1)
        px = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
        grad.putpixel((x, 0), px)
    return grad.resize((w, h))


def _text_w(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _center_text(draw, cx, y, text, font, fill, letter_spacing=0):
    if letter_spacing:
        total_w = sum(_text_w(draw, ch, font) + letter_spacing for ch in text) - letter_spacing
        x = cx - total_w / 2
        for ch in text:
            draw.text((x, y), ch, font=font, fill=fill)
            x += _text_w(draw, ch, font) + letter_spacing
    else:
        w = _text_w(draw, text, font)
        draw.text((cx - w / 2, y), text, font=font, fill=fill)


def build_branded_qr_card(amount, qr_value, depid, status_label="PENDING"):
    """Compose the full 'Kai JakLike' branded KHQR payment card and return
    PNG bytes ready for bot.send_photo."""
    qr_img = render_qr_image(qr_value)

    W, H = 800, 1250
    card = Image.new("RGB", (W, H), C_INK)
    draw = ImageDraw.Draw(card)

    margin = 28
    panel_box = [margin, margin, W - margin, H - margin]
    draw.rounded_rectangle(panel_box, radius=36, fill=C_PANEL)

    # ---- header: dot-grid (QR module motif) + wordmark ----
    for gy in range(margin + 34, margin + 70, 14):
        for gx in range(margin + 34, W - margin - 34, 14):
            draw.ellipse([gx, gy, gx + 3, gy + 3], fill=C_DOT)

    f_word = brand_font("Poppins-Bold.ttf", 46)
    f_tag = brand_font("Poppins-Medium.ttf", 16)
    _center_text(draw, W / 2, margin + 92, "KAI JAKLIKE", f_word, C_TEXT, letter_spacing=3)
    _center_text(draw, W / 2, margin + 150, "SMM AUTO TOP-UP  •  KHQR PAYMENT", f_tag, C_MUTED, letter_spacing=1)

    # ---- gradient "SCAN TO PAY" pill ----
    pill_w, pill_h = 260, 52
    pill_x = (W - pill_w) / 2
    pill_y = margin + 196
    grad = _hgrad((pill_w, pill_h), C_FLAME, C_GOLD)
    mask = Image.new("L", (pill_w, pill_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pill_w, pill_h], radius=pill_h // 2, fill=255)
    card.paste(grad, (int(pill_x), int(pill_y)), mask)
    f_pill = brand_font("Poppins-SemiBold.ttf", 20)
    _center_text(draw, W / 2, pill_y + 14, "SCAN TO PAY", f_pill, (20, 12, 14), letter_spacing=2)

    # ---- QR mounting panel ----
    qr_panel_size = 480
    qr_panel_x = (W - qr_panel_size) / 2
    qr_panel_y = pill_y + pill_h + 34
    draw.rounded_rectangle(
        [qr_panel_x, qr_panel_y, qr_panel_x + qr_panel_size, qr_panel_y + qr_panel_size],
        radius=28,
        fill=C_PAPER,
    )
    if qr_img:
        pad = 36
        target = qr_panel_size - pad * 2
        qr_resized = qr_img.resize((target, target), Image.NEAREST)
        card.paste(qr_resized, (int(qr_panel_x + pad), int(qr_panel_y + pad)))

    f_caption = brand_font("Poppins-Medium.ttf", 16)
    _center_text(
        draw, W / 2, qr_panel_y + qr_panel_size + 20,
        "KHQR  •  Powered by Bakong", f_caption, C_MUTED, letter_spacing=1,
    )

    # ---- signature: ticket perforation (torn-stub) divider ----
    perf_y = qr_panel_y + qr_panel_size + 74
    # side notches so the panel reads like a torn ticket
    notch_r = 18
    draw.ellipse([margin - notch_r, perf_y - notch_r, margin + notch_r, perf_y + notch_r], fill=C_INK)
    draw.ellipse([W - margin - notch_r, perf_y - notch_r, W - margin + notch_r, perf_y + notch_r], fill=C_INK)
    dot_x = margin + 40
    while dot_x < W - margin - 40:
        draw.ellipse([dot_x, perf_y - 4, dot_x + 8, perf_y + 4], fill=C_PANEL2)
        dot_x += 20

    # ---- amount block ----
    f_label = brand_font("Poppins-Medium.ttf", 16)
    f_amount = brand_font("Poppins-Bold.ttf", 64)
    ay = perf_y + 36
    _center_text(draw, W / 2, ay, "AMOUNT TO PAY", f_label, C_MUTED, letter_spacing=2)
    amount_text = f"${amount:,.2f}"
    aw = _text_w(draw, amount_text, f_amount)
    ax = (W - aw) / 2
    ay2 = ay + 30
    grad2 = _hgrad((int(aw) + 4, 80), C_FLAME, C_GOLD)
    amount_mask = Image.new("L", (int(aw) + 4, 80), 0)
    ImageDraw.Draw(amount_mask).text((2, 0), amount_text, font=f_amount, fill=255)
    card.paste(grad2, (int(ax) - 2, int(ay2)), amount_mask)

    if khmer_font_available():
        f_km = brand_font("Battambang-Regular.ttf", 20)
        _center_text(draw, W / 2, ay2 + 88, "សូមស្កេន QR ដើម្បីទូទាត់ប្រាក់", f_km, C_MUTED)
        ref_label_y = ay2 + 122
    else:
        ref_label_y = ay2 + 100

    # ---- reference + status row ----
    f_row_label = brand_font("Poppins-Medium.ttf", 15)
    f_row_val = brand_font("Poppins-SemiBold.ttf", 17)
    row_x1 = margin + 46
    row_x2 = W - margin - 46
    draw.text((row_x1, ref_label_y), "REFERENCE", font=f_row_label, fill=C_MUTED)
    ref_text = f"#{depid[-8:]}"
    rw = _text_w(draw, ref_text, f_row_val)
    draw.text((row_x2 - rw, ref_label_y - 3), ref_text, font=f_row_val, fill=C_TEXT)

    status_y = ref_label_y + 36
    draw.text((row_x1, status_y), "STATUS", font=f_row_label, fill=C_MUTED)
    status_color = C_MINT if status_label.upper() == "PAID" else C_GOLD
    dot_cx = row_x2 - 118
    draw.ellipse([dot_cx, status_y + 4, dot_cx + 10, status_y + 14], fill=status_color)
    draw.text((dot_cx + 18, status_y - 3), status_label.upper(), font=f_row_val, fill=status_color)

    # ---- footer ----
    f_footer = brand_font("Poppins-Regular.ttf", 14)
    _center_text(
        draw, W / 2, H - margin - 46,
        "Valid for 10 minutes  •  Balance is credited automatically",
        f_footer, C_MUTED,
    )
    _center_text(draw, W / 2, H - margin - 24, "@KaiJakLikeBot", f_footer, C_MUTED)

    buf = BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# KEYBOARDS
# ---------------------------------------------------------------------------

BTN_ORDER = "🛒 កម្មង់សេវា"
BTN_MYORDERS = "📦 ការកម្មង់របស់ខ្ញុំ"
BTN_BALANCE = "💰 សមតុល្យខ្ញុំ"
BTN_HELP = "ℹ️ ជំនួយ"
BTN_ADMIN = "⚙️ គ្រប់គ្រង Admin"


def main_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton(BTN_ORDER), types.KeyboardButton(BTN_MYORDERS))
    kb.add(types.KeyboardButton(BTN_BALANCE), types.KeyboardButton(BTN_HELP))
    if is_admin(chat_id):
        kb.add(types.KeyboardButton(BTN_ADMIN))
    return kb


def admin_home_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("➕ បន្ថែម Panel ថ្មី", callback_data="adm_add_panel"),
        types.InlineKeyboardButton("📋 បញ្ជី Panel ទាំងអស់", callback_data="adm_list_panels"),
        types.InlineKeyboardButton("📊 ស្ថិតិទូទៅ", callback_data="adm_stats"),
    )
    return kb


def panels_list_kb(prefix, panels):
    kb = types.InlineKeyboardMarkup(row_width=1)
    for pid, p in panels.items():
        kb.add(types.InlineKeyboardButton(f"🌐 {p['name']}", callback_data=f"{prefix}:{pid}"))
    kb.add(types.InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data="back_main"))
    return kb


def panel_manage_kb(pid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Sync Services ពី Panel", callback_data=f"sync:{pid}"),
        types.InlineKeyboardButton("🔍 ស្វែងរក Service", callback_data=f"search:{pid}"),
    )
    kb.add(
        types.InlineKeyboardButton("➕ បន្ថែម Service ដោយដៃ (ID)", callback_data=f"manual_svc:{pid}"),
        types.InlineKeyboardButton("📋 Services ដែលកំណត់រួច", callback_data=f"svc_list:{pid}"),
    )
    kb.add(
        types.InlineKeyboardButton("💵 សមតុល្យ Panel", callback_data=f"panel_bal:{pid}"),
        types.InlineKeyboardButton("🗑 លុប Panel", callback_data=f"del_panel:{pid}"),
    )
    kb.add(types.InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data="adm_list_panels"))
    return kb


def confirm_cancel_kb(yes_cb, no_cb="cancel_flow"):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ បញ្ជាក់", callback_data=yes_cb),
        types.InlineKeyboardButton("❌ បោះបង់", callback_data=no_cb),
    )
    return kb


# ---------------------------------------------------------------------------
# START / MAIN MENU HANDLERS
# ---------------------------------------------------------------------------


@bot.message_handler(commands=["start"])
def cmd_start(message):
    chat_id = message.chat.id
    get_user(chat_id)
    user_states.pop(chat_id, None)
    text = (
        "👋 <b>សូមស្វាគមន៍មកកាន់ Kai JakLike!</b>\n\n"
        "🛒 កម្មង់សេវា SMM (Facebook, TikTok, Instagram, YouTube ...)\n"
        "⚡️ បញ្ជាទិញលឿន និងតាមដានស្ថានភាពបានភ្លាមៗ\n\n"
        "សូមជ្រើសរើសម៉ឺនុយខាងក្រោម 👇"
    )
    bot.send_message(chat_id, text, reply_markup=main_menu(chat_id))


@bot.message_handler(func=lambda m: m.text == BTN_HELP)
def help_msg(message):
    bot.send_message(
        message.chat.id,
        "ℹ️ <b>របៀបប្រើប្រាស់</b>\n\n"
        "1️⃣ ចុច 🛒 កម្មង់សេវា ដើម្បីជ្រើសរើស Panel និង Service\n"
        "2️⃣ បញ្ចូល Link និងចំនួន Quantity\n"
        "3️⃣ បញ្ជាក់ការកម្មង់ — ប្រព័ន្ធនឹងកាត់សមតុល្យស្វ័យប្រវត្តិ\n"
        "4️⃣ ពិនិត្យស្ថានភាពការកម្មង់នៅ 📦 ការកម្មង់របស់ខ្ញុំ\n\n"
        f"សំណួរ/បញ្ហា? ទាក់ទង @smos_sne1",
    )


@bot.message_handler(func=lambda m: m.text == BTN_BALANCE)
def show_balance(message):
    chat_id = message.chat.id
    u = get_user(chat_id)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("💵 $1", callback_data="topup_quick:1"),
        types.InlineKeyboardButton("💵 $5", callback_data="topup_quick:5"),
        types.InlineKeyboardButton("💵 $10", callback_data="topup_quick:10"),
        types.InlineKeyboardButton("✏️ ចំនួនផ្សេង", callback_data="topup_custom"),
    )
    bot.send_message(
        chat_id,
        f"💰 សមតុល្យបច្ចុប្បន្នរបស់អ្នក: <b>${u['balance']:.2f}</b>\n\n"
        "➕ ចុចខាងក្រោមដើម្បីបញ្ចូលលុយ (KHQR) — ប្រព័ន្ធនឹងបញ្ចូលសមតុល្យស្វ័យប្រវត្តិភ្លាមៗ ពេលទូទាត់ចប់:",
        reply_markup=kb,
    )


@bot.message_handler(func=lambda m: m.text == BTN_ADMIN and is_admin(m.chat.id))
def admin_home(message):
    bot.send_message(message.chat.id, "⚙️ <b>ផ្ទាំងគ្រប់គ្រង Admin</b>", reply_markup=admin_home_kb())


@bot.message_handler(func=lambda m: m.text == BTN_MYORDERS)
def my_orders(message):
    chat_id = message.chat.id
    orders = load_orders()
    mine = {oid: o for oid, o in orders.items() if o["user_id"] == chat_id}
    if not mine:
        bot.send_message(chat_id, "📦 អ្នកមិនទាន់មានការកម្មង់ណាមួយនៅឡើយទេ។")
        return
    last_items = list(mine.items())[-10:]
    kb = types.InlineKeyboardMarkup(row_width=1)
    for oid, o in reversed(last_items):
        kb.add(
            types.InlineKeyboardButton(
                f"#{oid} • {o['service_name']} • {o['status']}",
                callback_data=f"order_status:{oid}",
            )
        )
    bot.send_message(chat_id, "📦 <b>ការកម្មង់ចុងក្រោយរបស់អ្នក</b> (ចុចដើម្បីមើលស្ថានភាព)", reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == BTN_ORDER)
def order_start(message):
    chat_id = message.chat.id
    panels = load_panels()
    if not panels:
        bot.send_message(chat_id, "😔 សូមអភ័យទោស Panel មិនទាន់ត្រូវបានកំណត់ដោយ Admin ទេ។")
        return
    bot.send_message(
        chat_id, "🌐 សូមជ្រើសរើស Panel:", reply_markup=panels_list_kb("panel_order", panels)
    )


# ---------------------------------------------------------------------------
# CALLBACK ROUTER
# ---------------------------------------------------------------------------


@bot.callback_query_handler(func=lambda c: True)
def callback_router(c):
    chat_id = c.message.chat.id
    data = c.data

    try:
        if data == "back_main":
            bot.edit_message_text(
                "🏠 ត្រឡប់ទៅម៉ឺនុយដើម។ សូមប្រើប៊ូតុងខាងក្រោម 👇",
                chat_id,
                c.message.message_id,
            )
            return

        if data == "cancel_flow":
            user_states.pop(chat_id, None)
            bot.edit_message_text("❌ បានបោះបង់។", chat_id, c.message.message_id)
            return

        if data == "adm_add_panel":
            if not is_admin(chat_id):
                return
            user_states[chat_id] = {"step": "panel_name", "data": {}}
            bot.send_message(chat_id, "📝 សូមវាយ <b>ឈ្មោះ Panel</b> (ឧ. MyProvider):")
            return

        if data == "adm_list_panels":
            panels = load_panels()
            if not panels:
                bot.edit_message_text(
                    "📋 មិនទាន់មាន Panel ណាមួយត្រូវបានបន្ថែមទេ។\nចុច ➕ ដើម្បីបន្ថែម Panel ថ្មី។",
                    chat_id,
                    c.message.message_id,
                    reply_markup=admin_home_kb(),
                )
                return
            bot.edit_message_text(
                "📋 <b>បញ្ជី Panel</b> — ចុចដើម្បីគ្រប់គ្រង:",
                chat_id,
                c.message.message_id,
                reply_markup=panels_list_kb("panel_manage", panels),
            )
            return

        if data == "adm_stats":
            panels = load_panels()
            users = load_users()
            orders = load_orders()
            bot.edit_message_text(
                "📊 <b>ស្ថិតិទូទៅ</b>\n\n"
                f"🌐 Panel សរុប: {len(panels)}\n"
                f"👤 អ្នកប្រើប្រាស់: {len(users)}\n"
                f"🧾 ការកម្មង់សរុប: {len(orders)}",
                chat_id,
                c.message.message_id,
                reply_markup=admin_home_kb(),
            )
            return

        if data.startswith("panel_manage:"):
            pid = data.split(":", 1)[1]
            panels = load_panels()
            p = panels.get(pid)
            if not p:
                bot.answer_callback_query(c.id, "Panel មិនត្រូវបានរកឃើញ")
                return
            svc_count = len(p.get("services", {}))
            bot.edit_message_text(
                f"🌐 <b>{p['name']}</b>\n"
                f"🔗 API: <code>{p['api_url']}</code>\n"
                f"🔑 Key: <code>{p['api_key'][:4]}****</code>\n"
                f"📦 Services ដែលកំណត់ក្នុងបូត: {svc_count}",
                chat_id,
                c.message.message_id,
                reply_markup=panel_manage_kb(pid),
            )
            return

        if data.startswith("del_panel:"):
            pid = data.split(":", 1)[1]
            kb = confirm_cancel_kb(f"confirm_del:{pid}")
            bot.edit_message_text(
                "⚠️ តើអ្នកប្រាកដទេថាចង់លុប Panel នេះ? សេវាទាំងអស់ក្នុង Panel នេះនឹងបាត់ផងដែរ។",
                chat_id,
                c.message.message_id,
                reply_markup=kb,
            )
            return

        if data.startswith("confirm_del:"):
            pid = data.split(":", 1)[1]
            panels = load_panels()
            panels.pop(pid, None)
            save_panels(panels)
            bot.edit_message_text("🗑 Panel ត្រូវបានលុបរួចរាល់។", chat_id, c.message.message_id)
            return

        if data.startswith("panel_bal:"):
            pid = data.split(":", 1)[1]
            panels = load_panels()
            p = panels.get(pid)
            ok, res = panel_get_balance(p)
            if ok and isinstance(res, dict):
                bal = res.get("balance", "N/A")
                cur = res.get("currency", "")
                bot.send_message(chat_id, f"💵 សមតុល្យ Panel <b>{p['name']}</b>: {bal} {cur}")
            else:
                bot.send_message(chat_id, f"❌ មិនអាចទាញយកសមតុល្យបានទេ: {res}")
            return

        if data.startswith("sync:"):
            pid = data.split(":", 1)[1]
            panels = load_panels()
            p = panels.get(pid)
            bot.send_message(chat_id, "🔄 កំពុងទាញយក Services ពី Panel... សូមរង់ចាំ")
            ok, res = panel_get_services(p)
            if not ok or not isinstance(res, list):
                bot.send_message(chat_id, f"❌ បរាជ័យ៖ {res}")
                return
            p["raw_services"] = res[:500]
            panels[pid] = p
            save_panels(panels)
            bot.send_message(
                chat_id,
                f"✅ បានទាញយក {len(res)} services ជោគជ័យ (រក្សាទុក {len(p['raw_services'])} ដំបូង)។\n"
                f"ឥឡូវប្រើ 🔍 ស្វែងរក Service ដើម្បីជ្រើសរើស និងបន្ថែមចូល Bot។",
            )
            return

        if data.startswith("search:"):
            pid = data.split(":", 1)[1]
            user_states[chat_id] = {"step": "search_svc_query", "data": {"pid": pid}}
            bot.send_message(chat_id, "🔍 សូមវាយពាក្យគន្លឹះស្វែងរក Service (ឧ. facebook likes):")
            return

        if data.startswith("pick_svc:"):
            _, pid, idx = data.split(":", 2)
            panels = load_panels()
            p = panels.get(pid)
            raw = p.get("raw_services", [])
            idx = int(idx)
            if idx >= len(raw):
                bot.answer_callback_query(c.id, "Service មិនត្រូវបានរកឃើញ")
                return
            svc = raw[idx]
            user_states[chat_id] = {
                "step": "new_service_label",
                "data": {
                    "pid": pid,
                    "service_id": str(svc.get("service")),
                    "orig_name": svc.get("name", ""),
                    "orig_rate": svc.get("rate", ""),
                },
            }
            bot.send_message(
                chat_id,
                f"✅ បានជ្រើសរើស: <b>{svc.get('name')}</b> (ID: {svc.get('service')}, Rate: {svc.get('rate')}/1000)\n\n"
                "📝 សូមវាយ <b>ឈ្មោះសម្រាប់បង្ហាញ</b> ដល់អតិថិជន (ខ្មែរឬអង់គ្លេស):",
            )
            return

        if data.startswith("manual_svc:"):
            pid = data.split(":", 1)[1]
            user_states[chat_id] = {"step": "manual_service_id", "data": {"pid": pid}}
            bot.send_message(chat_id, "📝 សូមវាយ <b>Service ID</b> ពី Panel (លេខ ID):")
            return

        if data.startswith("svc_list:"):
            pid = data.split(":", 1)[1]
            panels = load_panels()
            p = panels.get(pid)
            services = p.get("services", {})
            if not services:
                bot.edit_message_text(
                    "📋 មិនទាន់មាន Service ណាមួយត្រូវបានកំណត់ក្នុង Panel នេះទេ។",
                    chat_id,
                    c.message.message_id,
                    reply_markup=panel_manage_kb(pid),
                )
                return
            kb = types.InlineKeyboardMarkup(row_width=1)
            for skey, s in services.items():
                kb.add(
                    types.InlineKeyboardButton(
                        f"{s['label']} • ${s['price']}/1000",
                        callback_data=f"svc_detail:{pid}:{skey}",
                    )
                )
            kb.add(types.InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data=f"panel_manage:{pid}"))
            bot.edit_message_text("📋 <b>Services ដែលកំណត់រួច</b>:", chat_id, c.message.message_id, reply_markup=kb)
            return

        if data.startswith("svc_detail:"):
            _, pid, skey = data.split(":", 2)
            panels = load_panels()
            p = panels.get(pid)
            s = p.get("services", {}).get(skey)
            if not s:
                bot.answer_callback_query(c.id, "រកមិនឃើញ")
                return
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton("🗑 លុប Service នេះ", callback_data=f"del_svc:{pid}:{skey}"))
            kb.add(types.InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data=f"svc_list:{pid}"))
            bot.edit_message_text(
                f"🏷 <b>{s['label']}</b>\n"
                f"🆔 Panel Service ID: <code>{s['service_id']}</code>\n"
                f"💵 តម្លៃលក់: ${s['price']}/1000\n"
                f"📉 Min: {s.get('min', '-')}  📈 Max: {s.get('max', '-')}",
                chat_id,
                c.message.message_id,
                reply_markup=kb,
            )
            return

        if data.startswith("del_svc:"):
            _, pid, skey = data.split(":", 2)
            panels = load_panels()
            p = panels.get(pid)
            p.get("services", {}).pop(skey, None)
            panels[pid] = p
            save_panels(panels)
            bot.edit_message_text("🗑 Service ត្រូវបានលុបរួចរាល់។", chat_id, c.message.message_id)
            return

        # ---------------- USER ORDER FLOW ----------------

        if data.startswith("panel_order:"):
            pid = data.split(":", 1)[1]
            panels = load_panels()
            p = panels.get(pid)
            services = p.get("services", {})
            if not services:
                bot.edit_message_text(
                    "😔 Panel នេះមិនទាន់មាន Service បញ្ចូលទេ។", chat_id, c.message.message_id
                )
                return
            kb = types.InlineKeyboardMarkup(row_width=1)
            for skey, s in services.items():
                kb.add(
                    types.InlineKeyboardButton(
                        f"{s['label']} — ${s['price']}/1000",
                        callback_data=f"svc_order:{pid}:{skey}",
                    )
                )
            kb.add(types.InlineKeyboardButton("🔙 ត្រឡប់ក្រោយ", callback_data="back_main"))
            bot.edit_message_text(
                f"🌐 <b>{p['name']}</b>\nសូមជ្រើសរើស Service:", chat_id, c.message.message_id, reply_markup=kb
            )
            return

        if data.startswith("svc_order:"):
            _, pid, skey = data.split(":", 2)
            user_states[chat_id] = {"step": "order_link", "data": {"pid": pid, "skey": skey}}
            bot.send_message(chat_id, "🔗 សូមផ្ញើ <b>Link</b> ដែលអ្នកចង់កម្មង់ (ឧ. ចំណុះទំព័រ/URL):")
            return

        if data.startswith("order_status:"):
            oid = data.split(":", 1)[1]
            orders = load_orders()
            o = orders.get(oid)
            panels = load_panels()
            p = panels.get(o["pid"])
            ok, res = panel_order_status(p, o["panel_order_id"])
            if ok and isinstance(res, dict) and "status" in res:
                o["status"] = res.get("status", o["status"])
                orders[oid] = o
                save_orders(orders)
                bot.send_message(
                    chat_id,
                    f"📦 <b>ការកម្មង់ #{oid}</b>\n"
                    f"🏷 សេវា: {o['service_name']}\n"
                    f"📊 ស្ថានភាព: {o['status']}\n"
                    f"▶️ ចាប់ផ្តើម: {res.get('start_count', '-')}\n"
                    f"⏳ នៅសល់: {res.get('remains', '-')}",
                )
            else:
                bot.send_message(chat_id, f"📦 ការកម្មង់ #{oid} — ស្ថានភាព: {o['status']}")
            return

        if data.startswith("confirm_order:"):
            oid_key = data.split(":", 1)[1]
            st = user_states.get(chat_id)
            if not st or st.get("step") != "order_confirm":
                bot.answer_callback_query(c.id, "សូមចាប់ផ្តើមកម្មង់ម្តងទៀត")
                return
            place_order(chat_id, c.message.message_id)
            return

        # ---------------- AUTO PAYMENT (TOP UP) ----------------

        if data.startswith("topup_quick:"):
            amount = float(data.split(":", 1)[1])
            start_topup(chat_id, amount)
            return

        if data == "topup_custom":
            user_states[chat_id] = {"step": "topup_amount", "data": {}}
            bot.send_message(chat_id, "✏️ សូមវាយ <b>ចំនួនទឹកប្រាក់ (USD)</b> ដែលអ្នកចង់បញ្ចូល (ឧ. 7.5):")
            return

        if data.startswith("topup_check:"):
            depid = data.split(":", 1)[1]
            check_topup_once(chat_id, depid, c.message.message_id, manual=True, cq_id=c.id)
            return

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ មានបញ្ហា៖ {e}")


# ---------------------------------------------------------------------------
# TEXT / MULTI-STEP CONVERSATION HANDLER
# ---------------------------------------------------------------------------


@bot.message_handler(func=lambda m: m.chat.id in user_states)
def conversation_handler(message):
    chat_id = message.chat.id
    st = user_states[chat_id]
    step = st["step"]
    text = message.text.strip() if message.text else ""

    # ---- Admin: add panel flow ----
    if step == "panel_name":
        st["data"]["name"] = text
        st["step"] = "panel_url"
        bot.send_message(chat_id, "🔗 សូមវាយ <b>API URL</b> របស់ Panel (ឧ. https://panel.com/api/v2):")
        return

    if step == "panel_url":
        st["data"]["api_url"] = text
        st["step"] = "panel_key"
        bot.send_message(chat_id, "🔑 សូមវាយ <b>API Key</b> របស់ Panel:")
        return

    if step == "panel_key":
        st["data"]["api_key"] = text
        panels = load_panels()
        pid = str(int(time.time() * 1000))
        panels[pid] = {
            "name": st["data"]["name"],
            "api_url": st["data"]["api_url"],
            "api_key": st["data"]["api_key"],
            "services": {},
            "raw_services": [],
        }
        save_panels(panels)
        user_states.pop(chat_id, None)
        bot.send_message(
            chat_id,
            f"✅ Panel <b>{panels[pid]['name']}</b> ត្រូវបានបន្ថែមជោគជ័យ!\n"
            f"ឥឡូវអ្នកអាច Sync Services ឬបន្ថែម Service ដោយដៃបាន។",
            reply_markup=admin_home_kb(),
        )
        return

    # ---- Admin: search synced services ----
    if step == "search_svc_query":
        pid = st["data"]["pid"]
        panels = load_panels()
        p = panels.get(pid)
        raw = p.get("raw_services", [])
        q = text.lower()
        matches = [
            (i, s) for i, s in enumerate(raw) if q in str(s.get("name", "")).lower()
        ][:15]
        if not matches:
            bot.send_message(chat_id, "😔 មិនមាន Service ត្រូវនឹងពាក្យនេះទេ។ សូមសាកល្បងពាក្យផ្សេង។")
            return
        kb = types.InlineKeyboardMarkup(row_width=1)
        for i, s in matches:
            label = f"{s.get('name')[:45]} — ${s.get('rate')}/1000"
            kb.add(types.InlineKeyboardButton(label, callback_data=f"pick_svc:{pid}:{i}"))
        user_states.pop(chat_id, None)
        bot.send_message(chat_id, f"🔍 លទ្ធផលសម្រាប់ \"{text}\":", reply_markup=kb)
        return

    # ---- Admin: manual service id entry ----
    if step == "manual_service_id":
        st["data"]["service_id"] = text
        st["step"] = "new_service_label"
        bot.send_message(chat_id, "📝 សូមវាយ <b>ឈ្មោះសម្រាប់បង្ហាញ</b> ដល់អតិថិជន:")
        return

    if step == "new_service_label":
        st["data"]["label"] = text
        st["step"] = "new_service_price"
        bot.send_message(chat_id, "💵 សូមវាយ <b>តម្លៃលក់ក្នុង 1000</b> (ឧ. 1.50):")
        return

    if step == "new_service_price":
        try:
            price = float(text)
        except ValueError:
            bot.send_message(chat_id, "❌ សូមវាយជាលេខ ឧ. 1.50")
            return
        st["data"]["price"] = price
        st["step"] = "new_service_minmax"
        bot.send_message(chat_id, "📉📈 សូមវាយ Min និង Max ដោយឃ្លាចន្លោះ (ឧ. 100 10000):")
        return

    if step == "new_service_minmax":
        parts = text.split()
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            bot.send_message(chat_id, "❌ ទម្រង់មិនត្រឹមត្រូវ។ ឧ. 100 10000")
            return
        mn, mx = int(parts[0]), int(parts[1])
        pid = st["data"]["pid"]
        panels = load_panels()
        p = panels.get(pid)
        skey = str(int(time.time() * 1000))
        p.setdefault("services", {})[skey] = {
            "service_id": st["data"]["service_id"],
            "label": st["data"]["label"],
            "price": st["data"]["price"],
            "min": mn,
            "max": mx,
        }
        panels[pid] = p
        save_panels(panels)
        user_states.pop(chat_id, None)
        bot.send_message(
            chat_id,
            f"✅ Service <b>{st['data']['label']}</b> ត្រូវបានបន្ថែមចូល Panel <b>{p['name']}</b> ជោគជ័យ!",
        )
        return

    # ---- User: order flow ----
    if step == "order_link":
        st["data"]["link"] = text
        st["step"] = "order_qty"
        bot.send_message(chat_id, "🔢 សូមវាយ <b>ចំនួន (Quantity)</b> ដែលអ្នកចង់កម្មង់:")
        return

    if step == "order_qty":
        if not text.isdigit():
            bot.send_message(chat_id, "❌ សូមវាយជាលេខ ឧ. 1000")
            return
        qty = int(text)
        pid = st["data"]["pid"]
        skey = st["data"]["skey"]
        panels = load_panels()
        p = panels.get(pid)
        s = p["services"][skey]
        if qty < s["min"] or qty > s["max"]:
            bot.send_message(
                chat_id, f"❌ ចំនួនត្រូវនៅចន្លោះ {s['min']} និង {s['max']}។ សូមវាយម្តងទៀត:"
            )
            return
        cost = round((qty / 1000) * s["price"], 2)
        u = get_user(chat_id)
        st["data"]["qty"] = qty
        st["data"]["cost"] = cost
        st["step"] = "order_confirm"
        kb = confirm_cancel_kb("confirm_order:go")
        bot.send_message(
            chat_id,
            f"🧾 <b>សេចក្តីសង្ខេបការកម្មង់</b>\n\n"
            f"🏷 សេវា: {s['label']}\n"
            f"🔗 Link: {st['data']['link']}\n"
            f"🔢 ចំនួន: {qty}\n"
            f"💵 តម្លៃសរុប: ${cost}\n"
            f"💰 សមតុល្យបច្ចុប្បន្ន: ${u['balance']:.2f}\n\n"
            "តើអ្នកចង់បញ្ជាក់ការកម្មង់នេះទេ?",
            reply_markup=kb,
        )
        return

    # ---- User: top up (auto payment) custom amount ----
    if step == "topup_amount":
        try:
            amount = float(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(chat_id, "❌ សូមវាយជាលេខធំជាង 0 ឧ. 7.5")
            return
        user_states.pop(chat_id, None)
        start_topup(chat_id, amount)
        return


def start_topup(chat_id, amount):
    """Create a KHQR payment via CamRapidPay and send the QR to the user,
    then auto-poll for payment confirmation in the background."""
    if not CAMRAPIDPAY_API_KEY:
        bot.send_message(
            chat_id,
            "⚠️ ប្រព័ន្ធទូទាត់ស្វ័យប្រវត្តិមិនទាន់ត្រូវបានកំណត់ដោយ Admin ទេ "
            "(CAMRAPIDPAY_API_KEY ខ្វះ)។ សូមទាក់ទង Admin ដើម្បីបញ្ចូលសមតុល្យ។",
        )
        return

    ok, res = camrapidpay_create_payment(amount)
    if not ok or not isinstance(res, dict):
        bot.send_message(chat_id, f"❌ មិនអាចបង្កើត KHQR បានទេ៖ {res}")
        return

    qr_value = res.get(CAMRAPIDPAY_QR_FIELD)
    md5 = res.get(CAMRAPIDPAY_MD5_FIELD)
    if not qr_value or not md5:
        bot.send_message(
            chat_id,
            "❌ ចម្លើយពី payment gateway មិនត្រូវនឹងទម្រង់ដែលរំពឹងទុកទេ។ "
            "សូមពិនិត្យ CAMRAPIDPAY_QR_FIELD / CAMRAPIDPAY_MD5_FIELD ក្នុង Render env vars។",
        )
        return

    deposits = load_deposits()
    depid = str(int(time.time() * 1000))
    deposits[depid] = {
        "user_id": chat_id,
        "amount": amount,
        "md5": md5,
        "status": "pending",
        "created": datetime.utcnow().isoformat(),
    }
    save_deposits(deposits)

    card = build_branded_qr_card(amount, qr_value, depid, status_label="PENDING")
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔄 ខ្ញុំបានទូទាត់ហើយ / ពិនិត្យស្ថានភាព", callback_data=f"topup_check:{depid}"))
    caption = (
        "⏳ ប្រព័ន្ធនឹងបញ្ចូលសមតុល្យស្វ័យប្រវត្តិភ្លាមៗពេលអ្នកទូទាត់ចប់ "
        "(ឬចុចប៊ូតុងខាងក្រោមដើម្បីពិនិត្យផ្ទាល់)។"
    )
    if card:
        bot.send_photo(chat_id, card, caption=caption, reply_markup=kb)
    else:
        bot.send_message(chat_id, caption, reply_markup=kb)

    threading.Thread(target=poll_topup, args=(chat_id, depid), daemon=True).start()


def _credit_deposit(chat_id, depid):
    """Mark a deposit paid and credit the user's balance (idempotent)."""
    deposits = load_deposits()
    dep = deposits.get(depid)
    if not dep or dep["status"] == "paid":
        return False
    dep["status"] = "paid"
    dep["paid_at"] = datetime.utcnow().isoformat()
    deposits[depid] = dep
    save_deposits(deposits)
    u = get_user(chat_id)
    update_user(chat_id, balance=round(u["balance"] + dep["amount"], 2))
    return True


def poll_topup(chat_id, depid):
    """Background polling loop — checks CamRapidPay every few seconds until
    paid or the timeout is reached."""
    deposits = load_deposits()
    dep = deposits.get(depid)
    if not dep:
        return
    elapsed = 0
    while elapsed < TOPUP_TIMEOUT_SECONDS:
        time.sleep(TOPUP_POLL_SECONDS)
        elapsed += TOPUP_POLL_SECONDS
        deposits = load_deposits()
        dep = deposits.get(depid)
        if not dep or dep["status"] == "paid":
            return
        ok, res = camrapidpay_check_transaction(dep["md5"])
        if ok and isinstance(res, dict):
            status = str(res.get("status", "")).lower()
            if status in ("success", "paid", "completed", "1", "true"):
                if _credit_deposit(chat_id, depid):
                    u = get_user(chat_id)
                    bot.send_message(
                        chat_id,
                        f"✅ <b>ការទូទាត់ជោគជ័យ!</b>\n"
                        f"💵 បានបញ្ចូល: ${dep['amount']:.2f}\n"
                        f"💰 សមតុល្យថ្មី: ${u['balance']:.2f}",
                    )
                return
    # timed out — leave as pending, user or admin can still check manually


def check_topup_once(chat_id, depid, message_id=None, manual=False, cq_id=None):
    """Manual one-off check triggered by the user's inline button."""
    deposits = load_deposits()
    dep = deposits.get(depid)
    if not dep:
        if cq_id:
            bot.answer_callback_query(cq_id, "រកមិនឃើញការទូទាត់នេះទេ")
        return
    if dep["status"] == "paid":
        if cq_id:
            bot.answer_callback_query(cq_id, "✅ ការទូទាត់នេះបានបញ្ចប់រួចហើយ")
        return
    ok, res = camrapidpay_check_transaction(dep["md5"])
    if ok and isinstance(res, dict):
        status = str(res.get("status", "")).lower()
        if status in ("success", "paid", "completed", "1", "true"):
            if _credit_deposit(chat_id, depid):
                u = get_user(chat_id)
                bot.send_message(
                    chat_id,
                    f"✅ <b>ការទូទាត់ជោគជ័យ!</b>\n"
                    f"💵 បានបញ្ចូល: ${dep['amount']:.2f}\n"
                    f"💰 សមតុល្យថ្មី: ${u['balance']:.2f}",
                )
            if cq_id:
                bot.answer_callback_query(cq_id, "✅ ជោគជ័យ!")
            return
    if cq_id:
        bot.answer_callback_query(cq_id, "⏳ មិនទាន់ទូទាត់ទេ សូមរង់ចាំបន្តិច")


def place_order(chat_id, message_id):
    st = user_states.get(chat_id)
    d = st["data"]
    pid, skey, link, qty, cost = d["pid"], d["skey"], d["link"], d["qty"], d["cost"]
    panels = load_panels()
    p = panels.get(pid)
    s = p["services"][skey]

    u = get_user(chat_id)
    if u["balance"] < cost:
        bot.edit_message_text(
            f"❌ សមតុល្យរបស់អ្នកមិនគ្រប់គ្រាន់ទេ (តម្រូវការ ${cost}, មាន ${u['balance']:.2f})។\n"
            "សូមទាក់ទង Admin ដើម្បីបញ្ចូលសមតុល្យ។",
            chat_id,
            message_id,
        )
        user_states.pop(chat_id, None)
        return

    ok, res = panel_add_order(p, s["service_id"], link, qty)
    if not ok or not isinstance(res, dict) or "order" not in res:
        bot.edit_message_text(f"❌ ការកម្មង់បរាជ័យ៖ {res}", chat_id, message_id)
        user_states.pop(chat_id, None)
        return

    panel_order_id = res["order"]
    update_user(chat_id, balance=round(u["balance"] - cost, 2))

    orders = load_orders()
    oid = str(int(time.time() * 1000))
    orders[oid] = {
        "user_id": chat_id,
        "pid": pid,
        "skey": skey,
        "service_name": s["label"],
        "link": link,
        "qty": qty,
        "cost": cost,
        "panel_order_id": panel_order_id,
        "status": "Pending",
        "created": datetime.utcnow().isoformat(),
    }
    save_orders(orders)
    user_states.pop(chat_id, None)

    bot.edit_message_text(
        f"✅ <b>ការកម្មង់ជោគជ័យ!</b>\n\n"
        f"🆔 លេខកម្មង់: #{oid}\n"
        f"🏷 សេវា: {s['label']}\n"
        f"🔢 ចំនួន: {qty}\n"
        f"💵 កាត់ចេញ: ${cost}\n\n"
        f"ពិនិត្យស្ថានភាពនៅ 📦 ការកម្មង់របស់ខ្ញុំ",
        chat_id,
        message_id,
    )


# ---------------------------------------------------------------------------
# ADMIN: manual balance top-up command
# ---------------------------------------------------------------------------


@bot.message_handler(commands=["addbalance"])
def add_balance(message):
    chat_id = message.chat.id
    if not is_admin(chat_id):
        return
    try:
        _, target_id, amount = message.text.split()
        amount = float(amount)
        u = get_user(int(target_id))
        update_user(int(target_id), balance=round(u["balance"] + amount, 2))
        bot.reply_to(message, f"✅ បានបញ្ចូល ${amount} ទៅគណនី {target_id}")
    except Exception:
        bot.reply_to(message, "ប្រើទម្រង់៖ /addbalance <user_id> <amount>")


# ---------------------------------------------------------------------------
# KEEP-ALIVE WEB SERVER (needed for Render Free Web Service tier, which
# requires the app to bind to a port — polling bots don't do this on
# their own, so we run a tiny Flask app alongside the bot in a thread).
# ---------------------------------------------------------------------------

keep_alive_app = Flask(__name__)


@keep_alive_app.route("/")
def home():
    return "Kai JakLike SMM Bot is running."


def run_keep_alive():
    port = int(os.environ.get("PORT", 10000))
    keep_alive_app.run(host="0.0.0.0", port=port)


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    threading.Thread(target=ensure_fonts, daemon=True).start()
    threading.Thread(target=run_keep_alive, daemon=True).start()
    print("Kai JakLike SMM Bot v1 is running...")
    bot.infinity_polling(skip_pending=True)
