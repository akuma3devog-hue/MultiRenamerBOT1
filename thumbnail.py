# thumbnail.py
import os
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import (
    set_thumbnail,
    get_thumbnail,
    delete_thumbnail
)

# ==========================
# STATE (runtime only)
# ==========================
THUMB_MODE = set()          # user_ids in thumb mode
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

        await msg.reply(
            "🖼 **Thumbnail Mode Enabled**\n\n"
            "• Send a thumbnail image (once)\n"
            "• Then send / forward files\n"
            "• I will re-upload them with thumbnail\n\n"
            "Use /thumbstop to exit"
        )

    # -------- EXIT THUMB MODE --------
    @app.on_message(filters.command("thumbstop"))
    async def thumbstop(_, msg):
        user_id = msg.from_user.id
        THUMB_MODE.discard(user_id)
        await msg.reply("❌ Thumbnail mode disabled")

    # -------- SAVE / REPLACE THUMB --------
    @app.on_message(filters.photo)
    async def save_thumb(_, msg):
        user_id = msg.from_user.id
        if user_id not in THUMB_MODE:
            return

        file_id = msg.photo.file_id
        set_thumbnail(user_id, file_id)

        await msg.reply(
            "✅ Thumbnail saved\n"
            "📎 Now send files (or send another image to replace thumb)"
        )

    # -------- APPLY THUMB TO FILES --------
    @app.on_message(filters.document | filters.video)
    async def apply_thumb(_, msg):
        user_id = msg.from_user.id
        if user_id not in THUMB_MODE:
            return

        thumb = get_thumbnail(user_id)
        if not thumb:
            return await msg.reply("⚠️ Send a thumbnail image first")

        media = msg.document or msg.video
        filename = media.file_name or "file"

        status = await msg.reply("⬇️ Downloading...")
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        # ---- DOWNLOAD ----
        path = await app.download_media(msg, file_name=file_path)
        if not path or not os.path.exists(path):
            return await safe_edit(status, "❌ Download failed")

        # ---- UPLOAD ----
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
