# thumbnail.py
import os
import time
import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

# ==========================
# STATE
# ==========================
THUMB_MODE = set()          # user_ids in thumb mode
USER_THUMB = {}             # user_id -> file_id

DOWNLOAD_DIR = "thumb_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==========================
# HELPERS
# ==========================
async def safe_edit(msg, text):
    try:
        await msg.edit_text(text)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except:
        pass


# ==========================
# REGISTER
# ==========================
def register_thumbnail(app: Client):

    # -------- ENTER THUMB MODE --------
    @app.on_message(filters.command("thumbmode"))
    async def thumbmode(_, msg):
        user_id = msg.from_user.id
        THUMB_MODE.add(user_id)
        USER_THUMB.pop(user_id, None)

        await msg.reply(
            "🖼 **Thumbnail mode enabled**\n\n"
            "1️⃣ Send ONE thumbnail image\n"
            "2️⃣ Then send / forward files\n"
            "3️⃣ I will re-upload with thumbnail\n\n"
            "/thumbstop to exit"
        )

    # -------- EXIT THUMB MODE --------
    @app.on_message(filters.command("thumbstop"))
    async def thumbstop(_, msg):
        user_id = msg.from_user.id
        THUMB_MODE.discard(user_id)
        USER_THUMB.pop(user_id, None)

        await msg.reply("❌ Thumbnail mode disabled")

    # -------- RECEIVE THUMB IMAGE --------
    @app.on_message(filters.photo)
    async def save_thumbnail(_, msg):
        user_id = msg.from_user.id
        if user_id not in THUMB_MODE:
            return

        USER_THUMB[user_id] = msg.photo.file_id
        await msg.reply("✅ Thumbnail saved. Now send files.")

    # -------- HANDLE FILES --------
    @app.on_message(filters.document | filters.video)
    async def apply_thumbnail(_, msg):
        user_id = msg.from_user.id
        if user_id not in THUMB_MODE:
            return

        thumb = USER_THUMB.get(user_id)
        if not thumb:
            return await msg.reply("⚠️ Send a thumbnail image first")

        media = msg.document or msg.video
        filename = media.file_name or "file"

        status = await msg.reply("⬇️ Downloading...")
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        # ---- DOWNLOAD ----
        path = await app.download_media(
            msg,
            file_name=file_path
        )

        if not path or not os.path.exists(path):
            return await safe_edit(status, "❌ Download failed")

        # ---- UPLOAD WITH THUMB ----
        await safe_edit(status, "⬆️ Uploading with thumbnail...")

        try:
            await app.send_document(
                chat_id=msg.chat.id,
                document=path,
                thumb=thumb,
                file_name=filename
            )
        except Exception:
            await app.send_document(
                chat_id=msg.chat.id,
                document=path,
                file_name=filename
            )

        # ---- CLEANUP ----
        try:
            os.remove(path)
        except:
            pass

        await safe_edit(status, "✅ Done")
