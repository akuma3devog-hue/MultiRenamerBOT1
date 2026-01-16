from mongo import get_user, add_file_and_get_count

MAX_FILES = 30

def register_upload(bot):

    @bot.message_handler(content_types=["document", "video"])
    def upload_handler(message):
        user_id = message.from_user.id

        user = get_user(user_id)
        if not user:
            return  # must /start first

        if user.get("file_count", 0) >= MAX_FILES:
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

        # 🔥 ONE DB CALL — NO RACE CONDITIONS
        total = add_file_and_get_count(user_id, {
    "file_id": file.file_id,
    "file_name": file_name,
    "type": file_type,
    "message_id": message.message_id  # 🔥 ADD THIS
})

        bot.reply_to(
            message,
            f"📂 <b>Added:</b> {file_name}\n"
            f"📊 <b>Total files:</b> {total}/{MAX_FILES}",
            parse_mode="HTML"
        )
