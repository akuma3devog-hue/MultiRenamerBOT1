from mongo import reset_user, create_user

def register_start(bot):

    @bot.message_handler(commands=["start"])
    def start_cmd(message):
        uid = message.from_user.id

        reset_user(uid)
        create_user(uid)

        bot.reply_to(
            message,
            "✅ <b>Batch started!</b>\n\n"
            "📂 Send up to <b>30 files</b>\n"
            "🎥 Videos or 📄 Documents",
            parse_mode="HTML"
        )
