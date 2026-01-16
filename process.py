# process.py
import re
import os
import time
import tempfile
from mongo import get_files, get_rename, cleanup_user

BAR_LENGTH = 20  # number of blocks in bar

def extract_episode(filename):
    m = re.search(r"[Ee](\d+)", filename)
    return int(m.group(1)) if m else None


def make_bar(done, total):
    filled = int((done / total) * BAR_LENGTH)
    return "█" * filled + "░" * (BAR_LENGTH - filled)


def format_eta(seconds):
    if seconds < 60:
        return f"{int(seconds)}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s}s"


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

        # ✅ FINAL SAFE SORT
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
            f"🚀 Processing files…\n"
            f"{make_bar(0, total)}\n"
            f"0 / {total} (0%)\n"
            f"ETA: calculating…"
        )

        for idx, file in enumerate(files, start=1):
            ep_no = episode + (idx - 1)
            ep_str = f"{ep_no:02d}" if zero_pad else str(ep_no)
            new_name = f"{base} S{season}E{ep_str}"
            new_filename = f"{new_name}.mkv"

            # 🔽 DOWNLOAD (SERVER SIDE)
            info = bot.get_file(file["file_id"])
            data = bot.download_file(info.file_path)

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            # 🔼 REUPLOAD WITH REAL FILENAME
            with open(tmp_path, "rb") as f:
                bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    visible_file_name=new_filename
                )

            os.remove(tmp_path)

            # 📊 UPDATE PROGRESS BAR
            elapsed = time.time() - start_time
            avg = elapsed / idx
            remaining = avg * (total - idx)
            percent = int((idx / total) * 100)

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.message_id,
                text=(
                    f"🚀 Processing files…\n"
                    f"{make_bar(idx, total)}\n"
                    f"{idx} / {total} ({percent}%)\n"
                    f"ETA: {format_eta(remaining)}"
                )
            )

            time.sleep(0.8)  # flood-safe

        cleanup_user(user_id)

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_msg.message_id,
            text=(
                f"✅ Completed!\n"
                f"{make_bar(total, total)}\n"
                f"{total} / {total} (100%)"
            )
        )
