import re
import time
import asyncio
import os

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import (
    reset_user, create_user, add_file, get_user,
    set_thumbnail, get_thumbnail, delete_thumbnail,
    set_awaiting_thumb, is_awaiting_thumb
)

# =========================================================
# 🔧 ADDED: PROCESS CONTROL + SPEED CACHE (SAFE)
# =========================================================
ACTIVE_PROCESSES = {}        # user_id -> True/False
SPEED_CACHE = {}             # message_id -> (last_bytes, last_time)

# ---------------- PROGRESS BAR ----------------
async def progress_bar(current, total, message, start, label):
    if total == 0:
        return

    percent = int(current * 100 / total)
    now = time.time()

    if not hasattr(progress_bar, "last"):
        progress_bar.last = 0

    # 🔥 FAST BOT STYLE: update every ~5 seconds
    if now - progress_bar.last < 5 and percent != 100:
        return
    progress_bar.last = now

    # ---------------- SPEED CALC ----------------
    last = SPEED_CACHE.get(message.id)
    speed = 0
    if last:
        last_bytes, last_time = last
        diff_bytes = current - last_bytes
        diff_time = now - last_time
        if diff_time > 0:
            speed = diff_bytes / diff_time

    SPEED_CACHE[message.id] = (current, now)

    speed_mb = speed / (1024 * 1024)
    total_mb = total / (1024 * 1024)
    current_mb = current / (1024 * 1024)

    blocks = int(percent / 5)
    bar = "█" * blocks + "░" * (20 - blocks)

    eta = int((total - current) / speed) if speed > 0 else 0

    try:
        await message.edit_text(
            f"🚀 {label}\n"
            f"{bar}\n"
            f"{percent}% | {current_mb:.1f}/{total_mb:.1f} MB\n"
            f"⚡ {speed_mb:.2f} MB/s | ETA: {eta}s"
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except:
        pass


# ---------------- HELPERS ----------------
def extract_episode(name):
    m = re.search(r"[Ee](\d+)", name)
    return int(m.group(1)) if m else 0


# =========================================================
# ================= REGISTER HANDLERS =====================
# =========================================================
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
            "/process\n"
            "/cancel\n\n"
            "/setthumb • /changethumb • /viewthumb • /deletethumb"
        )

    # ---------- CANCEL ----------
    @app.on_message(filters.command("cancel"))
    async def cancel(_, msg):
        user_id = msg.from_user.id
        if not ACTIVE_PROCESSES.get(user_id):
            return await msg.reply("⚠️ No active process to cancel")

        ACTIVE_PROCESSES[user_id] = False
        await msg.reply("🛑 Process cancelled")

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
        await msg.reply("🖼 Send thumbnail image")

    # 🔧 ADDED: CHANGE THUMBNAIL
    @app.on_message(filters.command("changethumb"))
    async def changethumb(_, msg):
        set_awaiting_thumb(msg.from_user.id, True)
        await msg.reply("🖼 Send new thumbnail image (will replace old one)")

    @app.on_message(filters.photo | filters.document)
    async def save_thumb(_, msg):
        if not is_awaiting_thumb(msg.from_user.id):
            return

        if msg.photo:
            file_id = msg.photo.file_id
        elif msg.document and msg.document.mime_type.startswith("image/"):
            file_id = msg.document.file_id
        else:
            return await msg.reply("❌ Send an image")

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
        user_id = msg.from_user.id
        ACTIVE_PROCESSES[user_id] = True

        user = get_user(user_id)
        if not user or not user.get("files"):
            ACTIVE_PROCESSES.pop(user_id, None)
            return await msg.reply("❌ No files")

        if not user.get("rename"):
            ACTIVE_PROCESSES.pop(user_id, None)
            return await msg.reply("❌ Use /rename first")

        rename = user["rename"]
        thumb_id = get_thumbnail(user_id)

        files = sorted(user["files"], key=lambda f: extract_episode(f["file_name"]))
        total_files = len(files)
        total_size = sum(f.get("size", 0) for f in files)

        batch_start = time.time()
        status = await msg.reply("🚀 Starting process...")

        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)

        # 🔧 ADDED: DOWNLOAD THUMB ONCE (CRITICAL FIX)
        thumb_path = None
        if thumb_id:
            thumb_path = os.path.join(download_dir, "thumb.jpg")
            await app.download_media(thumb_id, file_name=thumb_path)

        try:
            for i, f in enumerate(files, start=1):

                if not ACTIVE_PROCESSES.get(user_id):
                    await status.edit_text("🛑 Process cancelled by user")
                    break

                filename = (
                    f"{rename['base']} "
                    f"S{rename['season']}E{rename['episode'] + i - 1:02d}.mkv"
                )

                file_path = os.path.join(download_dir, filename)
                original_msg = await app.get_messages(f["chat_id"], f["message_id"])

                await status.edit_text(
                    f"🚀 Processing {i}/{total_files}\n"
                    f"⬇️ Downloading\n"
                    f"📄 {filename}"
                )

                path = await app.download_media(
                    original_msg,
                    file_name=file_path,
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Downloading")
                )

                if not path or not os.path.exists(path):
                    continue

                await status.edit_text(
                    f"🚀 Processing {i}/{total_files}\n"
                    f"⬆️ Uploading\n"
                    f"📄 {filename}"
                )

                try:
                    await app.send_document(
                        msg.chat.id,
                        document=path,
                        thumb=thumb_path,
                        file_name=filename,
                        progress=progress_bar,
                        progress_args=(status, time.time(), "Uploading")
                    )
                except Exception:
                    await app.send_document(
                        msg.chat.id,
                        document=path,
                        file_name=filename,
                        progress=progress_bar,
                        progress_args=(status, time.time(), "Uploading")
                    )

                if os.path.exists(path):
                    os.remove(path)

        finally:
            ACTIVE_PROCESSES.pop(user_id, None)
            SPEED_CACHE.clear()

            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)

            if os.path.exists(download_dir):
                for f in os.listdir(download_dir):
                    try:
                        os.remove(os.path.join(download_dir, f))
                    except:
                        pass

        elapsed = int(time.time() - batch_start)
        total_mb = round(total_size / (1024 * 1024), 2)

        reset_user(user_id)
        create_user(user_id)

        await status.edit_text(
            f"✅ Completed\n\n"
            f"📦 Files: {total_files}\n"
            f"💾 Size: {total_mb} MB\n"
            f"⏱ Time: {elapsed}s"
    )
