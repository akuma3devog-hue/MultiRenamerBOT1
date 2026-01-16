import re
from mongo import (
    get_files,
    get_rename,
    cleanup_user
)

def extract_episode(filename):
    import re
    m = re.search(r"[Ee](\d+)", filename)
    return int(m.group(1)) if m else None


def register_process(bot):

    @bot.message_handler(commands=["process"])
    def process_cmd(message):
        user_id = message.from_user.id
        chat_id = message.chat.id

        files = get_files(user_id)
        if not files:
            bot.reply_to(message, "❌ No files to process.")
            return

        rename = get_rename(user_id)
        if not rename:
            bot.reply_to(message, "❌ Use /rename first.")
            return

        base = rename["base"]
        season = rename["season"]
        episode = rename["episode"]
        zero_pad = rename["zero_pad"]

        # 🔥 SORT FILES BY EPISODE NUMBER
        files.sort(
    key=lambda f: (
        extract_episode(f["file_name"]) is None,
        extract_episode(f["file_name"]) or 0,
        f["upload_index"]
    )
        )

        bot.send_message(chat_id, f"🚀 Processing {len(files)} files...")

        for idx, file in enumerate(files):
            ep_no = episode + idx

            ep_str = f"{ep_no:02d}" if zero_pad else str(ep_no)
            new_name = f"{base} S{season}E{ep_str}"

            if file["type"] == "document":
                bot.send_document(
                    chat_id,
                    file["file_id"],
                    caption=new_name,
                    file_name=f"{new_name}.mkv"
                )
            else:
                bot.send_video(
                    chat_id,
                    file["file_id"],
                    caption=new_name,
                    supports_streaming=True
                )

        # 🧹 CLEANUP AFTER SUCCESS
        cleanup_user(user_id)

        bot.send_message(chat_id, "✅ Batch completed successfully!")
