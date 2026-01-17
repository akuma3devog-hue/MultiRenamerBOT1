import re
import time
import asyncio
from pyrogram import Client, filters
from mongo import (
    reset_user,
    create_user,
    add_file,
    get_user,
    get_files,
    set_thumbnail,
    get_thumbnail,
    delete_thumbnail
)

# -----------------------------
# PROGRESS CALLBACK
# -----------------------------

async def upload_progress(current, total, message, start_time, action):
    if total == 0:
        return

    percent = current * 100 / total
    elapsed = time.time() - start_time

    speed = current / elapsed if elapsed > 0 else 0
    eta = (total - current) / speed if speed > 0 else 0

    bar_len = 20
    filled = int(bar_len * percent / 100)
    bar = "█" * filled + "░" * (bar_len - filled)

    try:
        await message.edit_text(
            f"{action}\n"
            f"{bar}\n"
            f"{percent:.1f}% | ETA: {int(eta)}s"
        )
    except:
        pass


def register_handlers(app: Client):

    # -----------------------------
    # START
    # -----------------------------
    @app.on_message(filters.command("start"))
    async def start(_, msg):
        reset_user(msg.from_user.id)
        create_user(msg.from_user.id)
        await msg.reply(
            "✅ Batch started\n\n"
            "📂 Send files\n"
            "✏️ /rename Name S1E1\n"
            "🖼 /setthumb (optional)\n"
            "🚀 /process"
        )

    # -----------------------------
    # UPLOAD FILES
    # -----------------------------
    @app.on_message(filters.document | filters.video)
    async def upload(_, msg):
        user = get_user(msg.from_user.id)
        if not user:
            return

        media = msg.document or msg.video
        add_file(msg.from_user.id, {
            "file_id": media.file_id,
            "file_name": media.file_name or "video.mp4",
            "type": "document" if msg.document else "video"
        })

        await msg.reply(f"📂 Added: {media.file_name}")

    # -----------------------------
    # RENAME
    # -----------------------------
    @app.on_message(filters.command("rename"))
    async def rename(_, msg):
        try:
            _, base, ep = msg.text.split(" ", 2)
            s = int(re.search(r"S(\d+)", ep).group(1))
            e = int(re.search(r"E(\d+)", ep).group(1))
        except:
            return await msg.reply("❌ Usage: /rename Name S1E1")

        from mongo import users
        users.update_one(
            {"user_id": msg.from_user.id},
            {"$set": {"rename": {"base": base, "season": s, "episode": e}}}
        )
        await msg.reply("✏️ Rename saved")

    # -----------------------------
    # SET THUMBNAIL
    # -----------------------------
    @app.on_message(filters.command("setthumb"))
    async def setthumb(_, msg):
        await msg.reply("🖼 Send the thumbnail image now.")

    @app.on_message(filters.photo | filters.document)
    async def save_thumb(_, msg):
        if not msg.reply_to_message:
            return
        if "thumbnail" not in msg.reply_to_message.text.lower():
            return

        if msg.photo:
            file_id = msg.photo.file_id
        elif msg.document and msg.document.mime_type.startswith("image/"):
            file_id = msg.document.file_id
        else:
            return await msg.reply("❌ Send a valid image.")

        set_thumbnail(msg.from_user.id, file_id)
        await msg.reply("✅ Thumbnail saved")

    # -----------------------------
    # DELETE THUMBNAIL
    # -----------------------------
    @app.on_message(filters.command("deletethumb"))
    async def deletethumb(_, msg):
        delete_thumbnail(msg.from_user.id)
        await msg.reply("🗑 Thumbnail removed")

    # -----------------------------
    # PROCESS FILES
    # -----------------------------
    @app.on_message(filters.command("process"))
    async def process(_, msg):
        user = get_user(msg.from_user.id)
        if not user or not user["files"]:
            return await msg.reply("❌ No files")

        if not user.get("rename"):
            return await msg.reply("❌ Use /rename first")

        rename = user["rename"]
        thumb_id = get_thumbnail(msg.from_user.id)

        for i, f in enumerate(user["files"], start=1):
            new_name = (
                f"{rename['base']} "
                f"S{rename['season']}E{rename['episode'] + i - 1:02d}.mkv"
            )

            progress_msg = await msg.reply(f"📤 Uploading {new_name}...")
            start_time = time.time()

            # Download
            path = await app.download_media(f["file_id"])

            # Upload with thumbnail + progress
            await app.send_document(
                chat_id=msg.chat.id,
                document=path,
                file_name=new_name,
                thumb=thumb_id,
                progress=upload_progress,
                progress_args=(progress_msg, start_time, "📤 Uploading")
            )

        await msg.reply("✅ Batch completed")
