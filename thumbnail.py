# thumbnail.py
import os
import time
import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import get_thumbnail, set_thumbnail

# ==========================
# CONFIG
# ==========================
THUMB_TIMEOUT = 300  # 5 minutes
DOWNLOAD_DIR = "thumb_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==========================
# STATE (SESSION BASED)
# ==========================
THUMB_MODE = {}          # user_id -> last_active_time
THUMB_QUEUE = {}         # user_id -> list of queued files
ACTIVE_THUMB = {}        # user_id -> running flag
THUMB_STATS = {}         # user_id -> stats
SPEED_CACHE = {}         # progress cache

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
        f"{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA {eta}s"
    )


def reset_stats(uid):
    THUMB_STATS[uid] = {
        "files": 0,
        "size": 0,
        "start": time.time()
    }


def finish_stats(uid):
    stats = THUMB_STATS.pop(uid, None)
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


async def exit_thumb_mode(msg, uid, auto=False):
    THUMB_MODE.pop(uid, None)
    THUMB_QUEUE.pop(uid, None)
    ACTIVE_THUMB.pop(uid, None)
    SPEED_CACHE.clear()

    summary = finish_stats(uid)
    if not summary:
        return await msg.reply("❌ Thumbnail session ended")

    await msg.reply(
        "🖼 **Thumbnail Summary**\n\n"
        f"📦 Files: {summary['files']}\n"
        f"💾 Size: {summary['size_mb']:.2f} MB\n"
        f"⏱ Time: {summary['time']}s\n"
        f"⚡ Avg speed: {summary['speed']:.2f} MB/s\n"
        f"{'⏰ Auto-timeout' if auto else ''}"
    )

# ==========================
# REGISTER
# ==========================
def register_thumbnail(app: Client):

    # -------- START SESSION --------
    @app.on_message(filters.command("thumbstart"))
    async def thumbstart(_, msg):
        uid = msg.from_user.id
        THUMB_MODE[uid] = time.time()
        THUMB_QUEUE[uid] = []
        reset_stats(uid)

        await msg.reply(
            "🖼 **Thumbnail Session Started**\n\n"
            "• Send files → they will be queued\n"
            "• /thumbset → set or replace thumbnail\n"
            "• /thumbapply → apply thumbnail to ALL queued files\n"
            "• /thumbstop → exit session\n"
        )

    # -------- SET / REPLACE THUMB --------
    @app.on_message(filters.command("thumbset"))
    async def thumbset(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return await msg.reply("⚠️ Thumbnail session not active")

        await msg.reply("🖼 Send thumbnail image now")

    @app.on_message(filters.photo)
    async def save_thumb(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return

        set_thumbnail(uid, msg.photo.file_id)
        THUMB_MODE[uid] = time.time()
        await msg.reply("✅ Thumbnail saved")

    # -------- QUEUE FILES --------
    @app.on_message(filters.document | filters.video)
    async def queue_files(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return

        media = msg.document or msg.video
        THUMB_QUEUE.setdefault(uid, []).append({
            "chat_id": msg.chat.id,
            "message_id": msg.id,
            "file_name": media.file_name or "file"
        })

        THUMB_MODE[uid] = time.time()
        await msg.reply("📦 File queued")

    # -------- APPLY (EXECUTOR) --------
    @app.on_message(filters.command("thumbapply"))
    async def thumbapply(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return await msg.reply("⚠️ Thumbnail session not active")

        queue = THUMB_QUEUE.get(uid, [])
        if not queue:
            return await msg.reply("⚠️ No files queued")

        thumb = get_thumbnail(uid)
        if not thumb:
            return await msg.reply("❌ No thumbnail set")

        ACTIVE_THUMB[uid] = True
        status = await msg.reply("🚀 Applying thumbnail...")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        for f in queue:
            if not ACTIVE_THUMB.get(uid):
                break

            original = await app.get_messages(f["chat_id"], f["message_id"])
            filename = f["file_name"]
            path = os.path.join(DOWNLOAD_DIR, filename)

            path = await app.download_media(
                original,
                file_name=path,
                progress=progress_bar,
                progress_args=(status, time.time(), "Downloading")
            )

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

        THUMB_QUEUE[uid].clear()
        ACTIVE_THUMB.pop(uid, None)
        await status.edit_text("✅ Thumbnail applied to all files")

    # -------- STOP SESSION --------
    @app.on_message(filters.command("thumbstop"))
    async def thumbstop(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return await msg.reply("⚠️ Thumbnail session not active")

        await exit_thumb_mode(msg, uid)

    # -------- CANCEL RUNNING --------
    @app.on_message(filters.command("cancel"))
    async def cancel(_, msg):
        uid = msg.from_user.id
        ACTIVE_THUMB[uid] = False
        await msg.reply("🛑 Thumbnail process cancelled")
