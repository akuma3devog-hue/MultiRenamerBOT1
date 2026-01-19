# thumbnail.py
import os
import time
import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import set_thumbnail, get_thumbnail

# ==========================
# CONFIG
# ==========================
THUMB_TIMEOUT = 300  # 5 minutes
DOWNLOAD_DIR = "thumb_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==========================
# STATE
# ==========================
THUMB_MODE = {}          # user_id -> last_active_time
THUMB_STATS = {}         # user_id -> stats dict
SPEED_CACHE = {}         # message_id -> (bytes, time)

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


async def progress_bar(current, total, message, start, label):
    if total == 0:
        return

    now = time.time()
    percent = int(current * 100 / total)

    last = SPEED_CACHE.get(message.id)
    speed = 0
    if last:
        lb, lt = last
        dt = now - lt
        if dt > 0:
            speed = (current - lb) / dt

    SPEED_CACHE[message.id] = (current, now)

    if not hasattr(progress_bar, "last"):
        progress_bar.last = 0
    if now - progress_bar.last < 5 and percent != 100:
        return
    progress_bar.last = now

    speed_mb = speed / (1024 * 1024)
    eta = int((total - current) / speed) if speed > 0 else 0

    bar = "█" * (percent // 5) + "░" * (20 - percent // 5)

    await safe_edit(
        message,
        f"🚀 {label}\n"
        f"{bar}\n"
        f"{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA: {eta}s"
    )


def reset_stats(user_id):
    THUMB_STATS[user_id] = {
        "files": 0,
        "size": 0,
        "start": time.time()
    }


def finish_stats(user_id):
    stats = THUMB_STATS.get(user_id)
    if not stats:
        return None

    elapsed = time.time() - stats["start"]
    avg_speed = (stats["size"] / elapsed) if elapsed > 0 else 0

    return {
        "files": stats["files"],
        "size_mb": stats["size"] / (1024 * 1024),
        "time": int(elapsed),
        "speed": avg_speed / (1024 * 1024)
    }


# ==========================
# REGISTER
# ==========================
def register_thumbnail(app: Client):

    # -------- ENTER MODE --------
    @app.on_message(filters.command("thumbmode"))
    async def thumbmode(_, msg):
        uid = msg.from_user.id
        THUMB_MODE[uid] = time.time()
        reset_stats(uid)

        await msg.reply(
            "🖼 **Thumbnail Mode Enabled**\n\n"
            "• Send a thumbnail image\n"
            "• Then send / forward files\n"
            "• Auto exits after 5 minutes inactivity\n\n"
            "/thumbstop to exit manually"
        )

    # -------- EXIT MODE --------
    async def exit_thumb_mode(msg, uid, auto=False):
        THUMB_MODE.pop(uid, None)
        SPEED_CACHE.clear()

        summary = finish_stats(uid)
        if not summary:
            return await msg.reply("❌ Thumbnail mode ended")

        await msg.reply(
            "🖼 **Thumbnail Summary**\n\n"
            f"📦 Files: {summary['files']}\n"
            f"💾 Size: {summary['size_mb']:.2f} MB\n"
            f"⏱ Time: {summary['time']}s\n"
            f"⚡ Avg speed: {summary['speed']:.2f} MB/s\n"
            f"{'⏰ Auto-timeout' if auto else ''}"
        )

    @app.on_message(filters.command("thumbstop"))
    async def thumbstop(_, msg):
        await exit_thumb_mode(msg, msg.from_user.id)

    # -------- SAVE / REPLACE THUMB --------
    @app.on_message(filters.photo)
    async def save_thumb(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return

        set_thumbnail(uid, msg.photo.file_id)
        THUMB_MODE[uid] = time.time()

        await msg.reply("✅ Thumbnail saved / replaced")

    # -------- HANDLE FILES --------
    @app.on_message(filters.document | filters.video)
    async def handle_files(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return

        # ⏰ AUTO TIMEOUT
        if time.time() - THUMB_MODE[uid] > THUMB_TIMEOUT:
            return await exit_thumb_mode(msg, uid, auto=True)

        THUMB_MODE[uid] = time.time()
        thumb = get_thumbnail(uid)

        if not thumb:
            return await msg.reply("⚠️ Send thumbnail image first")

        media = msg.document or msg.video
        filename = media.file_name or "file"

        status = await msg.reply("⬇️ Downloading...")
        file_path = os.path.join(DOWNLOAD_DIR, filename)

        path = await app.download_media(
            msg,
            file_name=file_path,
            progress=progress_bar,
            progress_args=(status, time.time(), "Downloading")
        )

        if not path:
            return await safe_edit(status, "❌ Download failed")

        await safe_edit(status, "⬆️ Uploading...")

        await app.send_document(
            msg.chat.id,
            document=path,
            thumb=thumb,
            file_name=filename,
            progress=progress_bar,
            progress_args=(status, time.time(), "Uploading")
        )

        size = os.path.getsize(path)
        THUMB_STATS[uid]["files"] += 1
        THUMB_STATS[uid]["size"] += size

        os.remove(path)
        await safe_edit(status, "✅ Done")
