from mongo import (
    get_user,
    get_files,
    get_rename,
    cleanup_user
)

def register_process(bot):

    @bot.message_handler(commands=["process"])
    def process_handler(message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        user = get_user(user_id)
        if not user:
            bot.reply_to(message, "❌ Use /start first.")
            return

        files = sorted(
    get_files(user_id),
    key=lambda f: f.get("message_id", 0)
        )
        if not files:
            bot.reply_to(message, "❌ No files to process.")
            return

        rename = get_rename(user_id)
        if not rename:
            bot.reply_to(message, "❌ Use /rename before /process.")
            return

        base = rename["base"]
        season = rename["season"]
        episode = rename["episode"]
        zero_pad = rename["zero_pad"]

        bot.reply_to(message, "⚙️ Processing files…")

        for file in files:
            ep_num = str(episode).zfill(2) if zero_pad else str(episode)
            new_name = f"{base} S{season}E{ep_num}"

            if file["file_name"].lower().endswith(".mkv"):
                new_name += ".mkv"
            elif file["file_name"].lower().endswith(".mp4"):
                new_name += ".mp4"
            else:
                new_name += ""

            if file["type"] == "document":
                bot.send_document(
                    chat_id,
                    file["file_id"],
                    caption=new_name,
                    visible_file_name=new_name
                )
            else:
                bot.send_video(
                    chat_id,
                    file["file_id"],
                    caption=new_name,
                    supports_streaming=True
                )

            episode += 1

        cleanup_user(user_id)

        bot.send_message(
            chat_id,
            "✅ <b>Batch completed!</b>\n\n"
            "You can start a new batch with /start",
            parse_mode="HTML"
          )
