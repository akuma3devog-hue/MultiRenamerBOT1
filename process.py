# process.py
import re
import time
from mongo import get_files, get_rename, cleanup_user

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

        # 🔥 SORT (KEEP ORDER + EP LOGIC)
        files.sort(
            key=lambda f: (
                extract_episode(f["file_name"]) is None,
                extract_episode(f["file_name"]) or 0,
                f["upload_index"]
            )
        )

        total = len(files)

        progress = bot.send_message(
            chat_id,
            f"🚀 Processing files...\n0 / {total} (0%)"
        )

        for idx, file in enumerate(files, start=1):
            ep_no = episode + (idx - 1)
            ep_str = f"{ep_no:02d}" if zero_pad else str(ep_no)

            new_name = f"{base} S{season}E{ep_str}.mkv"

            # ✅ ALWAYS SEND AS DOCUMENT (THIS FIXES BLUE TITLE)
            bot.send_document(
                chat_id=chat_id,
                document=file["file_id"],
                caption=new_name,
                file_name=new_name
            )

            percent = int((idx / total) * 100)

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress.message_id,
                text=f"🚀 Processing files...\n{idx} / {total} ({percent}%)"
            )

            time.sleep(1.2)  # flood safe

        cleanup_user(user_id)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress.message_id,
            text=f"✅ Batch completed!\n{total}/{total} (100%)"
        )
