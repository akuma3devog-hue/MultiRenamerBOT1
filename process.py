# process.py
import os
import time
from pyrogram import Client, filters

from mongo import get_user, reset_user, create_user
from handlers import (
    ACTIVE_PROCESSES,
    SPEED_CACHE,
    MODE,
    MANUAL_NAMES,
    AUTO_CONF,
    DOWNLOAD_DIR,
    extract_episode,
    progress_bar,
    touch
)


def register_process(app: Client):

    @app.on_message(filters.command("process"))
    async def process(_, msg):
        uid = msg.from_user.id
        touch(uid)

        user = get_user(uid)
        files = user.get("files", [])

        if not files:
            return await msg.reply("No files")

        if MODE.get(uid) == "manual" and len(MANUAL_NAMES[uid]) != len(files):
            return await msg.reply("Names mismatch")

        ACTIVE_PROCESSES[uid] = True
        status = await msg.reply("🚀 Processing")

        try:
            for i, f in enumerate(files):
                if not ACTIVE_PROCESSES.get(uid):
                    break

                # ---------- filename ----------
                if MODE[uid] == "manual":
                    filename = MANUAL_NAMES[uid][i]
                else:
                    conf = AUTO_CONF[uid]
                    ep = extract_episode(f["file_name"])
                    ep = ep if ep is not None else conf["start_ep"] + i

                    filename = (
                        f"{conf['base']} "
                        f"S{conf['season']}E{ep:02d} "
                        f"{conf['quality'].group(1) if conf['quality'] else ''} "
                        f"{conf['tag'].group(0) if conf['tag'] else ''}"
                    ).strip()

                original = await app.get_messages(f["chat_id"], f["message_id"])

                part = f"{DOWNLOAD_DIR}/{filename}.mkv.part"
                final = f"{DOWNLOAD_DIR}/{filename}.mkv"
                expected_size = f.get("size", 0)

                # 🔥 delete broken partial file if size mismatch
                if os.path.exists(part):
                    os.remove(part)

                progress_bar.last = 0

                # ---------- DOWNLOAD ----------
                await app.download_media(
                    original,
                    file_name=part,
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Downloading")
                )

                # ❌ verify download integrity
                if not os.path.exists(part):
                    await status.edit_text("❌ Download failed")
                    return

                if expected_size and os.path.getsize(part) < expected_size * 0.98:
                    os.remove(part)
                    await status.edit_text("❌ Incomplete download. Retrying /process")
                    return

                os.replace(part, final)  # atomic rename

                # 🔥 reset progress throttle BEFORE upload
                progress_bar.last = 0

                # ---------- UPLOAD ----------
                await app.send_document(
                    chat_id=msg.chat.id,
                    document=final,
                    file_name=os.path.basename(final),
                    force_document=True,
                    supports_streaming=False,
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Uploading")
                )

                os.remove(final)

        finally:
            ACTIVE_PROCESSES.pop(uid, None)
            SPEED_CACHE.clear()
            reset_user(uid)
            create_user(uid)

        await status.edit_text("✅ Completed")
