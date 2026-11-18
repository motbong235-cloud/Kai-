# Fix: Master bot (Render PORT + Telegram 429)

## Changes required in `kaijaklike_bot.py`

### 1) `run_flask` — bind Render `$PORT`
```python
def run_flask():
    port = int(os.environ.get("PORT") or CONTROL_PORT or 5056)
    logger.info(f"Control Server running on port {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
```

### 2) Channel repair — slower + smaller batch
- Start: `_repair_channel_order_messages(40)` (not 250)
- Sleep between edits: `1.2` seconds (not 0.05)
- On 429: stop the repair loop

### 3) `_bot_brand` — prefer `BOT_DISPLAY_NAME`, back off 120s on fail

Deploy after full `kaijaklike_bot.py` update is pushed.
