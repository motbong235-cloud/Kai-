"""
TopUpFox Reseller integration — MASTER bot only.
API: https://reseller.topupfoxbot.com/api-docs
Base: https://api.topupfoxbot.com/v1
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

FOX_CFG_DEFAULT = {
    "uid": "",
    "api_key": "",
    "api_secret": "",
    "markup_pct": 15.0,
    "enabled": True,
}


def fox_cfg_path(data_dir: str) -> str:
    return os.path.join(data_dir, "fox_reseller.json")


def load_fox_cfg(data_dir: str, load_fn) -> dict:
    cfg = load_fn(fox_cfg_path(data_dir), dict(FOX_CFG_DEFAULT))
    if not isinstance(cfg, dict):
        cfg = dict(FOX_CFG_DEFAULT)
    for k, v in FOX_CFG_DEFAULT.items():
        cfg.setdefault(k, v)
    if os.getenv("FOX_UID"):
        cfg["uid"] = os.getenv("FOX_UID", "").strip()
    if os.getenv("FOX_API_KEY"):
        cfg["api_key"] = os.getenv("FOX_API_KEY", "").strip()
    if os.getenv("FOX_API_SECRET"):
        cfg["api_secret"] = os.getenv("FOX_API_SECRET", "").strip()
    return cfg


def save_fox_cfg(data_dir: str, cfg: dict, save_fn) -> None:
    save_fn(fox_cfg_path(data_dir), cfg)


def fox_ready(cfg: dict) -> bool:
    try:
        uid = str(cfg.get("uid") or "").strip()
        key = str(cfg.get("api_key") or "").strip()
        sec = str(cfg.get("api_secret") or "").strip()
        return bool(uid and key and sec and uid.isdigit())
    except Exception:
        return False


def fox_client(cfg: dict):
    from reseller_client import ResellerClient

    return ResellerClient(
        uid=int(cfg["uid"]),
        api_key=str(cfg["api_key"]).strip(),
        api_secret=str(cfg["api_secret"]).strip(),
    )


def fox_balance(cfg: dict) -> float:
    return float(fox_client(cfg).balance())


def fox_list_games(cfg: dict) -> list:
    return fox_client(cfg).games() or []


def fox_game_detail(cfg: dict, code: str) -> dict:
    return fox_client(cfg).game(code) or {}


def sell_price(reseller_price: float, markup_pct: float) -> float:
    try:
        p = float(reseller_price)
        m = float(markup_pct or 0)
        return round(p * (1.0 + m / 100.0), 4)
    except Exception:
        return float(reseller_price or 0)


def slug_for_item(game_code: str, item_code: str) -> str:
    raw = f"fox_{game_code}_{item_code}".lower()
    out = []
    for ch in raw:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    return s[:48]  # Telegram callback_data max 64 bytes


def service_from_item(
    game: dict,
    item: dict,
    markup_pct: float,
) -> dict:
    """Build an smm_services-style entry for a Fox package."""
    gcode = str(game.get("code") or game.get("game_code") or "")
    icode = str(item.get("code") or item.get("item_code") or "")
    name = item.get("name") or item.get("label") or icode
    gname = game.get("name") or game.get("title") or gcode
    rprice = item.get("reseller_price")
    if rprice is None:
        rprice = item.get("price") or item.get("cost") or 0
    price = sell_price(float(rprice), markup_pct)
    # Plain game name — smm_cat_kb adds a single icon (avoid emoji x2)
    cat = str(gname or gcode or "Game").strip()
    if cat.startswith("🎮"):
        cat = cat[1:].lstrip()
    return {
        "label": str(name),
        "description": f"{gname} · {gcode} · {icode}",
        "category": cat or gcode or "Game",
        "price": price,
        "flat_price": price,   # fixed $ per order (same path as manual packages)
        "cost_rate": 0,        # required by smm_qty_kb / cb_smmsvc
        "min": 1,
        "max": 1,
        "manual": False,
        "fox": True,
        "fox_game_code": gcode,
        "fox_item_code": icode,
        "fox_cost": float(rprice),
        "api_id": 0,
        "provider_id": "fox",
        "open": True,
        "rate": price,
    }


def place_fox_order(
    cfg: dict,
    *,
    game_code: str,
    item_code: str,
    player_id: str,
    server_id: str = "",
    reference: str = "",
) -> dict:
    api = fox_client(cfg)
    kwargs: dict[str, Any] = {"player_id": str(player_id).strip()}
    if server_id:
        kwargs["server_id"] = str(server_id).strip()
    if reference:
        kwargs["reference"] = reference
    return api.order(game_code, item_code, **kwargs)


def poll_fox_status(cfg: dict, order_id) -> dict:
    return fox_client(cfg).order_status(order_id)
