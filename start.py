from mongo import reset_user, create_user

def register_start(bot):
    @bot.message_handler(commands=["start"])
    def start_cmd(message):
        user = message.from_user
        user_id = user.id

        # Reset any previous batch
        reset_user(user_id)

        # Create fresh batch state
        create_user(user_id)

        bot.reply_to(
            message,
            "✅ <b>Batch started!</b>\n\n"
            "📂 Send up to <b>30 files</b>\n"
            "🎥 Videos or 📄 Documents\n\n"
            "When ready, use <code>/process</code>",
            parse_mode="HTML"
        )
