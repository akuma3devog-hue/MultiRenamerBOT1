import threading
import telebot

from config import BOT_TOKEN, PORT
from server import app
from start import register_start
from upload import register_upload
from process import register_process
from rename import register_rename
# Create bot instance
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Register handlers (more will be added later)
register_start(bot)
register_upload(bot)
register_process(bot)
register_rename(bot)
def run_web():
    """
    Flask server for UptimeRobot / Render health check
    """
    app.run(host="0.0.0.0", port=PORT)

def run_bot():
    print("🤖 Bot started polling...")
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print("❌ Polling stopped:", e)
if __name__ == "__main__":
    # Run Flask server in background thread
    threading.Thread(target=run_web, daemon=True).start()

    # Run Telegram bot
    run_bot()
