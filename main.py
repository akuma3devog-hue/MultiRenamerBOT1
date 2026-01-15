import threading
import telebot

from config import BOT_TOKEN, PORT
from server import app
from start import register_start

# Create bot instance
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Register handlers (more will be added later)
register_start(bot)

def run_web():
    """
    Flask server for UptimeRobot / Render health check
    """
    app.run(host="0.0.0.0", port=PORT)

def run_bot():
    """
    Telegram bot polling loop
    """
    print("🤖 Bot started polling...")
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    # Run Flask server in background thread
    threading.Thread(target=run_web, daemon=True).start()

    # Run Telegram bot
    run_bot()
