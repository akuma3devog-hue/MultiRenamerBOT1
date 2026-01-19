# thumbnail.py
import os
import time
import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import get_thumbnail

# ==========================
# CONFIG
# ==========================
THUMB_TIMEOUT = 300
DOWNLOAD_DIR = "thumb_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==========================
# STATE
# ==========================
THUMB_MODE = set()       # active session users
THUMB_QUEUE = {}         # user_id -> queued files
THUMB_STATS = {}
ACTIVE_PROCESSES = {}
SPEED_CACHE = {}

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

    if not hasattr(progress_bar, "last"):
        progress_bar.last = 0
    if now - progress_bar.last < 5 and percent != 100:
        return
    progress_bar.last = now

    last = SPEED_CACHE.get(message.id)
    speed = 0
    if last:
        lb, lt = last
        if now - lt > 0:
            speed = (current - lb) / (now - lt)

    SPEED_CACHE[message.id] = (current, now)

    bar = "█" * (percent // 5) + "░" * (20 - percent // 5)
    speed_mb = speed / (1024 * 1024)
    eta = int((total - current) / speed) if speed > 0 else 0

    await safe_edit(
        message,
        f"🚀 {label}\n{bar}\n{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA {eta}s"
    )


def reset_stats(uid):
    THUMB_STATS[uid] = {"files": 0, "size": 0, "start": time.time()}


def finish_stats(uid):
    stats = THUMB_STATS.pop(uid, None)
    if not stats:
        return None
    elapsed = time.time() - stats["start"]
    return (
        f"📦 Files: {stats['files']}\n"
        f"💾 Size: {stats['size']/(1024*1024):.2f} MB\n"
        f"⏱ Time: {int(elapsed)}s\n"
        f"⚡ Avg: {(stats['size']/elapsed)/(1024*1024):.2f} MB/s"
    )


# ==========================
# REGISTER
# ==========================
def register_thumbnail(app: Client):

    @app.on_message(filters.command("thumbstart"))
    async def thumbstart(_, msg):
        uid = msg.from_user.id
        THUMB_MODE.add(uid)
        THUMB_QUEUE[uid] = []
        reset_stats(uid)
        await msg.reply(
            "🖼 Thumbnail session started\n\n"
            "📦 Send files to queue\n"
            "🖼 Use /thumbset to set thumbnail\n"
            "🔥 Use /thumbapply to apply\n"
            "/thumbstop to exit"
        )

    @app.on_message(filters.command("thumbset"))
    async def thumbset(_, msg):
        await msg.reply("📸 Send thumbnail image")

    @app.on_message(filters.photo)
    async def save_thumb(_, msg):
        from mongo import set_thumbnail
        set_thumbnail(msg.from_user.id, msg.photo.file_id)
        await msg.reply("✅ Thumbnail saved")

    @app.on_message(filters.document | filters.video)
    async def queue_files(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return
        THUMB_QUEUE[uid].append(msg)
        await msg.reply("📦 File queued")

    @app.on_message(filters.command("thumbapply"))
    async def apply(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return await msg.reply("⚠️ Thumbnail session not active")

        thumb = get_thumbnail(uid)
        if not thumb:
            return await msg.reply("❌ No thumbnail set")

        files = THUMB_QUEUE.get(uid, [])
        if not files:
            return await msg.reply("⚠️ No files queued")

        ACTIVE_PROCESSES[uid] = True
        status = await msg.reply("🚀 Applying thumbnail...")

        for m in files:
            if not ACTIVE_PROCESSES.get(uid):
                break

            media = m.document or m.video
            filename = media.file_name or "file"

            path = await app.download_media(
                m,
                file_name=os.path.join(DOWNLOAD_DIR, filename),
                progress=progress_bar,
                progress_args=(status, time.time(), "Downloading")
            )

            await app.send_document(
                msg.chat.id,
                path,
                thumb=thumb,
                file_name=filename,
                progress=progress_bar,
                progress_args=(status, time.time(), "Uploading")
            )

            THUMB_STATS[uid]["files"] += 1
            THUMB_STATS[uid]["size"] += os.path.getsize(path)
            os.remove(path)

        summary = finish_stats(uid)
        THUMB_MODE.discard(uid)
        THUMB_QUEUE.pop(uid, None)
        ACTIVE_PROCESSES.pop(uid, None)

        await status.edit_text(f"✅ Thumbnail applied\n\n{summary}")

    @app.on_message(filters.command("thumbstop"))
    async def thumbstop(_, msg):
        uid = msg.from_user.id
        THUMB_MODE.discard(uid)
        THUMB_QUEUE.pop(uid, None)
        await msg.reply("❌ Thumbnail session ended")
