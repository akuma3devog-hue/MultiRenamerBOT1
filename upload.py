# upload.py
from mongo import get_user, add_file_and_get_count

MAX_FILES = 30

def register_upload(bot):

    @bot.message_handler(content_types=["document", "video"])
    def upload_handler(message):
        user_id = message.from_user.id

        user = get_user(user_id)
        if not user:
            return  # must /start first

        current_count = user.get("file_count", 0)
        if current_count >= MAX_FILES:
            bot.reply_to(
                message,
                f"❌ Batch limit reached ({MAX_FILES} files).",
                parse_mode="HTML"
            )
            return

        # Detect file
        if message.content_type == "document":
            file = message.document
            file_name = file.file_name
            file_type = "document"
        else:
            file = message.video
            file_name = file.file_name or "video.mp4"
            file_type = "video"

        # ✅ ATOMIC INSERT + COUNT
        new_count = add_file_and_get_count(
            user_id,
            {
                "file_id": file.file_id,
                "file_name": file_name,
                "type": file_type,
                "upload_index": current_count  # safe now
            }
        )

        bot.reply_to(
            message,
            f"📂 <b>Added:</b> {file_name}\n"
            f"📊 <b>Total files:</b> {new_count}/{MAX_FILES}",
            parse_mode="HTML"
        )
