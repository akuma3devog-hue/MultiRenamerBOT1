import os
import time
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import reset_user, create_user, get_user
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
            return await msg.reply("❌ No files to process")

        if MODE.get(uid) == "manual" and len(MANUAL_NAMES.get(uid, [])) != len(files):
            return await msg.reply("❌ Names count mismatch")

        ACTIVE_PROCESSES[uid] = True
        status = await msg.reply("🚀 Processing started")

        try:
            for i, f in enumerate(files):
                if not ACTIVE_PROCESSES.get(uid):
                    await status.edit_text("🛑 Cancelled")
                    return

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

                # 🔧 Ensure extension
                original_name = f["file_name"]
                ext = os.path.splitext(original_name)[1] or ".mkv"
                safe_name = filename + ext

                original = await app.get_messages(
                    f["chat_id"], f["message_id"]
                )

                temp_path = os.path.join(DOWNLOAD_DIR, safe_name + ".part")
                final_path = os.path.join(DOWNLOAD_DIR, safe_name)

                # ---------- DOWNLOAD ----------
                progress_bar.last = 0
                await app.download_media(
                    original,
                    file_name=temp_path,
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Downloading")
                )

                if not os.path.exists(temp_path):
                    await status.edit_text("❌ Download failed")
                    return

                os.replace(temp_path, final_path)

                # ---------- UPLOAD ----------
                progress_bar.last = 0
                SPEED_CACHE.pop(status.id, None)  # 🔥 clear stale speed cache

                await app.send_document(
                    chat_id=msg.chat.id,
                    document=final_path,  # PATH not file object
                    file_name=os.path.basename(final_path),
                    force_document=True,
                    supports_streaming=False,
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Uploading")
                )

                os.remove(final_path)
                await asyncio.sleep(1)  # Render stability

        finally:
            ACTIVE_PROCESSES.pop(uid, None)
            SPEED_CACHE.clear()
            reset_user(uid)
            create_user(uid)

        await status.edit_text("✅ All files processed successfully")
