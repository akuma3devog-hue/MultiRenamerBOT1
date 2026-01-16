# main.py
import threading
import telebot
import time
import os

from config import BOT_TOKEN, PORT
from server import app
from start import register_start
from rename import register_rename
from process import register_process
from upload import register_upload


# ==================================================
# TELEGRAM BOT INSTANCE (ONLY ONE)
# ==================================================
bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML",
    threaded=True
)


# ==================================================
# REGISTER HANDLERS (ORDER MATTERS)
# ==================================================
register_start(bot)
register_rename(bot)
register_upload(bot)
register_process(bot)


# ==================================================
# FLASK WEB SERVER (UPTIMEROBOT / RENDER)
# ==================================================
def run_web():
    app.run(host="0.0.0.0", port=PORT)


# ==================================================
# TELEGRAM POLLING (SAFE LOOP)
# ==================================================
def run_bot():
    print("🤖 Bot started polling...")

    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=60,
                long_polling_timeout=60
            )
        except Exception as e:
            print("⚠️ Polling error:", e)
            time.sleep(5)  # prevent crash loop


# ==================================================
# MAIN ENTRY POINT
# ==================================================
if __name__ == "__main__":
    # Start Flask in background
    threading.Thread(target=run_web, daemon=True).start()

    # Start Telegram bot
    run_bot()
