# main.py
import threading
from flask import Flask
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, PORT
from handlers import register_handlers

web = Flask(__name__)

@web.route("/", methods=["GET", "HEAD"])
def health():
    return "OK", 200

def run_web():
    web.run(host="0.0.0.0", port=PORT)

app = Client(
    "renamer_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1,
    sleep_threshold=30
)

register_handlers(app)

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    print("🤖 Bot running...")
    app.run()
