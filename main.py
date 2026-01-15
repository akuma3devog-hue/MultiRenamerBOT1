import threading
import telebot

from config import BOT_TOKEN, PORT
from server import app
from start import register_start

# Create bot instance
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Register all handlers
register_start(bot)

def run_web():
    # Flask server for UptimeRobot
    app.run(host="0.0.0.0", port=PORT)

def run_bot():
    print("🤖 Bot started polling...")
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    # Run Flask and bot together
    threading.Thread(target=run_web, daemon=True).start()
    run_bot()
