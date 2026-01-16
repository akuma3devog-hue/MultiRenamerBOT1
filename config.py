# config.py
import os

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Render / UptimeRobot
PORT = int(os.getenv("PORT", 10000))

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("❌ Missing environment variables")
