from telebot import types
from bot.database.mongo import save_user, delete_user

def register_start(bot):

    @bot.message_handler(commands=["start"])
    def start_handler(message):
        user_id = message.from_user.id

        # Reset any old batch
        delete_user(user_id)

        # Create new batch
        save_user({
            "user_id": user_id,
            "files": [],
            "rename": None,
            "thumbnail": None,
            "change_file_id": False
        })

        bot.reply_to(
            message,
            "✅ <b>Batch started!</b>\n\n"
            "📂 Send up to <b>30 files</b>\n"
            "🎥 Videos or 📄 Documents\n\n"
            "When ready, use:\n"
            "<code>/rename</code> → set format\n"
            "<code>/process</code> → apply changes",
            parse_mode="HTML"
        )
