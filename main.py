import threading
import telebot

from bot.config import BOT_TOKEN, PORT
from web.server import app
from bot.handlers.start import register_start

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Register handlers
register_start(bot)

def run_web():
    app.run(host="0.0.0.0", port=PORT)

def run_bot():
    print("🤖 Bot started polling...")
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    run_bot()
