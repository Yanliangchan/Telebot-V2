import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in environment variables")
