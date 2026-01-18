import re
import time
import asyncio
from pyrogram import Client, filters
from mongo import (
    reset_user, create_user, add_file, get_user,
    set_thumbnail, get_thumbnail, delete_thumbnail,
    set_awaiting_thumb, is_awaiting_thumb
)

# ---------------- PROGRESS BAR ----------------
async def progress_bar(current, total, message, start, label):
    if total == 0:
        return

    percent = int(current * 100 / total)

    # 🔒 STRONG FLOOD CONTROL
    if percent % 10 != 0 and percent != 100:
        return

    blocks = int(percent / 5)
    bar = "█" * blocks + "░" * (20 - blocks)

    elapsed = time.time() - start
    speed = current / elapsed if elapsed > 0 else 0
    eta = int((total - current) / speed) if speed > 0 else 0

    try:
        await message.edit_text(
            f"🚀 {label}\n"
            f"{bar}\n"
            f"{percent}% | ETA: {eta}s"
        )
    except:
        pass

    # 🔑 yield control to event loop
    await asyncio.sleep(0)


# ---------------- HELPERS ----------------
def extract_episode(name):
    m = re.search(r"[Ee](\d+)", name)
    return int(m.group(1)) if m else 0


def register_handlers(app: Client):

    # ---------- START ----------
    @app.on_message(filters.command("start"))
    async def start(_, msg):
        reset_user(msg.from_user.id)
        create_user(msg.from_user.id)
        await msg.reply(
            "✅ Batch started\n\n"
            "📂 Send files\n"
            "/rename Name S1E1\n"
            "/process\n\n"
            "/setthumb • /viewthumb • /deletethumb"
        )

    # ---------- FILE UPLOAD ----------
    @app.on_message(filters.document | filters.video)
    async def upload(_, msg):
        user = get_user(msg.from_user.id)
        if not user:
            return

        media = msg.document or msg.video

        add_file(msg.from_user.id, {
            "chat_id": msg.chat.id,
            "message_id": msg.id,
            "file_name": media.file_name or "video.mkv",
            "size": media.file_size or 0
        })

        await msg.reply(f"📂 Added: {media.file_name}")

    # ---------- RENAME ----------
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

# ---------- THUMBNAIL ----------
    @app.on_message(filters.command("setthumb"))
    async def setthumb(_, msg):
        set_awaiting_thumb(msg.from_user.id, True)
        await msg.reply("🖼 Send thumbnail image (photo only)")

    @app.on_message(filters.photo)
    async def save_thumb(_, msg):
        if not is_awaiting_thumb(msg.from_user.id):
            return

        file_id = msg.photo.file_id
        set_thumbnail(msg.from_user.id, file_id)
        set_awaiting_thumb(msg.from_user.id, False)
        await msg.reply("✅ Thumbnail saved")

    @app.on_message(filters.command("viewthumb"))
    async def viewthumb(_, msg):
        thumb = get_thumbnail(msg.from_user.id)
        if not thumb:
            return await msg.reply("❌ No thumbnail set")
        await app.send_photo(msg.chat.id, thumb, caption="🖼 Current thumbnail")

    @app.on_message(filters.command("deletethumb"))
    async def deletethumb(_, msg):
        delete_thumbnail(msg.from_user.id)
        await msg.reply("🗑 Thumbnail removed")

    # ---------- PROCESS ----------
    @app.on_message(filters.command("process"))
    async def process(_, msg):
        user = get_user(msg.from_user.id)
        if not user or not user.get("files"):
            return await msg.reply("❌ No files")

        if not user.get("rename"):
            return await msg.reply("❌ Use /rename first")

        rename = user["rename"]
        thumb = get_thumbnail(msg.from_user.id)

        files = sorted(
            user["files"],
            key=lambda f: extract_episode(f["file_name"])
        )

        total_files = len(files)
        total_size = sum(f.get("size", 0) for f in files)

        status = await msg.reply("🚀 Preparing...")
        start = time.time()

        for i, f in enumerate(files):
            ep = rename["episode"] + i
            filename = f"{rename['base']} S{rename['season']}E{ep:02d}.mkv"

            original_msg = await app.get_messages(
                chat_id=f["chat_id"],
                message_ids=f["message_id"]
            )

            path = await app.download_media(
                original_msg,
                progress=progress_bar,
                progress_args=(status, start, "Downloading")
            )

            await app.send_document(
                msg.chat.id,
                document=path,
                thumb=thumb,
                file_name=filename,
                progress=progress_bar,
                progress_args=(status, time.time(), "Uploading")
            )

        elapsed = int(time.time() - start)
        total_mb = round(total_size / (1024 * 1024), 2)

        await status.edit_text(
            f"✅ Completed\n\n"
            f"📦 Files: {total_files}\n"
            f"💾 Size: {total_mb} MB\n"
            f"⏱ Time: {elapsed}s"
    )
