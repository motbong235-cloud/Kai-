"""
Fox Store Reseller API client (official).
Docs: https://reseller.topupfoxbot.com/api-docs
Base: https://api.topupfoxbot.com/v1
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any
from urllib.parse import urlsplit

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE = "https://api.topupfoxbot.com/v1"


def _aes_key(api_secret: str) -> bytes:
    return hashlib.sha256(f"fox-transport-v1:{api_secret}".encode()).digest()


class ResellerClient:
    def __init__(self, uid: int, api_key: str, api_secret: str, base: str = BASE):
        self.uid = int(uid)
        self.base = base.rstrip("/")
        self._base_path = urlsplit(self.base).path.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self._aes = AESGCM(_aes_key(api_secret))

    def me(self) -> dict:
        return self.get("/users/me")

    def balance(self) -> float:
        return float(self.me()["balance"])

    def games(self) -> list:
        return self.get("/games")

    def game(self, code: str) -> dict:
        return self.get(f"/games/{code}")

    def lookup(self, game_code: str, **input_values) -> dict:
        return self.post(f"/games/{game_code}/lookup", {"input_values": input_values})

    def order(
        self,
        game_code: str | None = None,
        item_code: str | None = None,
        *,
        game_item_id: int | None = None,
        reference: str | None = None,
        **input_values: Any,
    ) -> dict:
        body: dict[str, Any] = {**input_values, "reference": reference or str(uuid.uuid4())}
        if game_item_id is not None:
            body["game_item_id"] = game_item_id
        else:
            if not game_code or not item_code:
                raise ValueError("Pass game_code + item_code, or game_item_id=")
            body["game_code"] = game_code
            body["item_code"] = item_code
        return self.post("/orders", body, signed=True)

    def order_status(self, order_id) -> dict:
        return self.get(f"/orders/{order_id}", signed=True)

    def orders(self) -> list:
        return self.get("/orders", signed=True)

    def _enc(self, obj):
        nonce = os.urandom(12)
        raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
        data = base64.urlsafe_b64encode(nonce + self._aes.encrypt(nonce, raw, None)).decode()
        return {"_enc": 1, "token": self.api_key, "data": data}

    def _dec(self, obj):
        if not (isinstance(obj, dict) and obj.get("_enc") == 1):
            return obj
        raw = base64.urlsafe_b64decode(obj["data"])
        return json.loads(self._aes.decrypt(raw[:12], raw[12:], None).decode())

    def _sign(self, method: str, path: str, business: dict) -> dict:
        body = "" if method == "GET" else json.dumps(business, sort_keys=True, separators=(",", ":"))
        body_hash = hashlib.sha256(body.encode()).hexdigest()
        req_time = str(int(time.time() * 1000))
        nonce = str(uuid.uuid4())
        msg = f"{method}\n{self._base_path}{path}\n{body_hash}\n{req_time}\n{nonce}\n{self.api_key}"
        signature = hmac.new(self.api_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return {
            **business,
            "req_time": req_time,
            "nonce": nonce,
            "hash": body_hash,
            "token": self.api_key,
            "signature": signature,
        }

    def get(self, path: str, *, signed: bool = False):
        headers = {"X-Uid": str(self.uid)}
        if signed:
            params = self._sign("GET", path, {})
            params = {k: params[k] for k in ("req_time", "nonce", "hash", "token", "signature")}
            r = requests.get(f"{self.base}{path}", params=params, headers=headers, timeout=30)
        else:
            headers["X-Api-Key"] = self.api_key
            r = requests.get(f"{self.base}{path}", headers=headers, timeout=30)
        r.raise_for_status()
        return self._dec(r.json()) if r.content else None

    def post(self, path: str, business: dict | None = None, *, signed: bool = False):
        business = business or {}
        headers = {"X-Uid": str(self.uid), "Content-Type": "application/json"}
        if signed:
            body = self._enc(self._sign("POST", path, business))
            r = requests.post(f"{self.base}{path}", json=body, headers=headers, timeout=30)
        else:
            headers["X-Api-Key"] = self.api_key
            r = requests.post(f"{self.base}{path}", json=self._enc(business), headers=headers, timeout=30)
        r.raise_for_status()
        return self._dec(r.json()) if r.content else None


G2PinClient = ResellerClient
