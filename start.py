from mongo import reset_user, create_user

def register_start(bot):
    @bot.message_handler(commands=["start"])
    def start_cmd(message):
        user_id = message.from_user.id

        # Reset any existing batch for this user
        reset_user(user_id)

        # Create a fresh batch state in MongoDB
        create_user(user_id)

        bot.reply_to(
            message,
            "✅ <b>Batch started!</b>\n\n"
            "📂 Send up to <b>30 files</b>\n"
            "🎥 Videos or 📄 Documents\n\n"
            "✏️ Then use <code>/rename</code>\n"
            "⚙️ Finally use <code>/process</code>",
            parse_mode="HTML"
        )
