import os

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

if not all([API_ID, API_HASH, BOT_TOKEN, MONGO_URI]):
    raise RuntimeError("Missing environment variables")
