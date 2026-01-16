from mongo import get_user, add_file, get_file_count

MAX_FILES = 30

def register_upload(bot):

    @bot.message_handler(content_types=["document", "video"])
    def upload_handler(message):
        user_id = message.from_user.id

        user = get_user(user_id)
        if not user:
            return  # must /start first

        count = user.get("file_count", 0)
        if count >= MAX_FILES:
            bot.reply_to(
                message,
                f"❌ Batch limit reached ({MAX_FILES} files).",
                parse_mode="HTML"
            )
            return

        # Detect file type
        if message.content_type == "document":
            file = message.document
            file_name = file.file_name
            file_type = "document"
        else:
            file = message.video
            file_name = file.file_name or "video.mp4"
            file_type = "video"

        # 🔥 ATOMIC INSERT
        add_file(user_id, {
            "file_id": file.file_id,
            "file_name": file_name,
            "type": file_type
        })

        # 🔥 SAFE COUNT (NO RACE CONDITIONS)
        total = get_file_count(user_id)

        bot.reply_to(
            message,
            f"📂 <b>Added:</b> {file_name}\n"
            f"📊 <b>Total files:</b> {total}/{MAX_FILES}",
            parse_mode="HTML"
        )
