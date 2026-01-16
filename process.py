# process.py
import re
import time
from mongo import (
    get_files,
    get_rename,
    cleanup_user
)

def extract_episode(filename):
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

        # 🔥 KEEP YOUR SORT LOGIC
        files.sort(
            key=lambda f: (
                extract_episode(f["file_name"]) is None,
                extract_episode(f["file_name"]) or 0,
                f["upload_index"]
            )
        )

        total = len(files)
        start_time = time.time()

        progress_msg = bot.send_message(
            chat_id,
            f"🚀 Processing files...\n"
            f"0 / {total} (0%)\n"
            f"ETA: calculating..."
        )

        for idx, file in enumerate(files, start=1):
            ep_no = episode + (idx - 1)
            ep_str = f"{ep_no:02d}" if zero_pad else str(ep_no)
            new_name = f"{base} S{season}E{ep_str}"

            # ✅ TELEBOT-CORRECT SENDING
            if file["type"] == "document":
                bot.send_document(
                    chat_id,
                    file["file_id"],
                    caption=f"{new_name}.mkv"
                )
            else:
                bot.send_video(
                    chat_id,
                    file["file_id"],
                    caption=new_name,
                    supports_streaming=True
                )

            # ⏱ ETA calculation
            elapsed = time.time() - start_time
            avg_time = elapsed / idx
            remaining = int(avg_time * (total - idx))

            percent = int((idx / total) * 100)

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.message_id,
                text=(
                    f"🚀 Processing files...\n"
                    f"{idx} / {total} ({percent}%)\n"
                    f"ETA: {remaining}s"
                )
            )

            # Flood protection
            time.sleep(1.2)

        cleanup_user(user_id)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_msg.message_id,
            text="✅ Batch completed successfully! 🎉"
        )
