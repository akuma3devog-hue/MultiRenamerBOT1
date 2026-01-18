import os
from pyrogram import Client, filters
from mongo import (
    set_thumbnail,
    get_thumbnail,
    delete_thumbnail,
    set_awaiting_thumb,
    is_awaiting_thumb
)

# ===============================
# THUMBNAIL APPLY MODE (IN-MEMORY)
# ===============================
THUMB_APPLY_MODE = {}   # user_id -> True/False


def register_thumbnail_handlers(app: Client):

    # ---------- SET THUMB ----------
    @app.on_message(filters.command("setthumb"))
    async def setthumb(_, msg):
        set_awaiting_thumb(msg.from_user.id, True)
        await msg.reply("🖼 Send thumbnail image")

    @app.on_message(filters.photo | filters.document)
    async def save_thumb(_, msg):
        if not is_awaiting_thumb(msg.from_user.id):
            return

        if msg.photo:
            file_id = msg.photo.file_id
        elif msg.document and msg.document.mime_type.startswith("image/"):
            file_id = msg.document.file_id
        else:
            return await msg.reply("❌ Send a valid image")

        set_thumbnail(msg.from_user.id, file_id)
        set_awaiting_thumb(msg.from_user.id, False)
        await msg.reply("✅ Thumbnail saved")

    # ---------- VIEW / DELETE ----------
    @app.on_message(filters.command("viewthumb"))
    async def viewthumb(_, msg):
        thumb = get_thumbnail(msg.from_user.id)
        if not thumb:
            return await msg.reply("❌ No thumbnail set")
        await app.send_photo(msg.chat.id, thumb)

    @app.on_message(filters.command("deletethumb"))
    async def deletethumb(_, msg):
        delete_thumbnail(msg.from_user.id)
        await msg.reply("🗑 Thumbnail removed")

    # ---------- CHANGE THUMB MODE ----------
    @app.on_message(filters.command("changethumb"))
    async def changethumb(_, msg):
        thumb = get_thumbnail(msg.from_user.id)
        if not thumb:
            return await msg.reply("❌ Set a thumbnail first using /setthumb")

        THUMB_APPLY_MODE[msg.from_user.id] = True
        await msg.reply(
            "🖼 Thumbnail apply mode ON\n\n"
            "📂 Send or forward renamed files now\n"
            "⛔ /stopthumb to stop"
        )

    @app.on_message(filters.command("stopthumb"))
    async def stopthumb(_, msg):
        THUMB_APPLY_MODE.pop(msg.from_user.id, None)
        await msg.reply("✅ Thumbnail apply mode OFF")

    # ---------- APPLY THUMB ON FILE ----------
    @app.on_message(filters.document | filters.video)
    async def apply_thumb(_, msg):
        user_id = msg.from_user.id

        if not THUMB_APPLY_MODE.get(user_id):
            return

        thumb = get_thumbnail(user_id)
        if not thumb:
            return await msg.reply("❌ Thumbnail missing")

        status = await msg.reply("🖼 Applying thumbnail...")

        path = await msg.download()

        await app.send_document(
            msg.chat.id,
            document=path,
            thumb=thumb,
            file_name=msg.document.file_name if msg.document else None
        )

        try:
            os.remove(path)
        except:
            pass
