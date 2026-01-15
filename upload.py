from mongo import get_user, add_file, get_files

MAX_FILES = 30

def register_upload(bot):

    @bot.message_handler(content_types=["document", "video"])
    def upload_handler(message):
        user_id = message.from_user.id

        user = get_user(user_id)
        if not user:
            bot.reply_to(message, "❌ Use /start first.")
            return

        files = user.get("files", [])
        if len(files) >= MAX_FILES:
            bot.reply_to(
                message,
                f"❌ Batch limit reached ({MAX_FILES} files).\n"
                "Use <code>/process</code> or <code>/start</code>.",
                parse_mode="HTML"
            )
            return

        # Detect file type
        if message.content_type == "document":
            file = message.document
            file_type = "document"
            file_name = file.file_name
        else:
            file = message.video
            file_type = "video"
            file_name = file.file_name or "video.mp4"

        # Store file info (order preserved)
        add_file(user_id, {
            "file_id": file.file_id,
            "file_name": file_name,
            "type": file_type
        })

        total = len(files) + 1

        bot.reply_to(
            message,
            f"📂 <b>Added:</b> {file_name}\n"
            f"📊 <b>Total files:</b> {total}/{MAX_FILES}",
            parse_mode="HTML"
        )
