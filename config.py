import os

# ==================================================
# ENVIRONMENT CONFIGURATION
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
PORT = int(os.getenv("PORT", 10000))

# ==================================================
# VALIDATION
# ==================================================

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN is missing")

if not MONGO_URI:
    raise RuntimeError("❌ MONGO_URI is missing")
