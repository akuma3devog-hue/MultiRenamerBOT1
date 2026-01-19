# thumbnail.py
import os
import time
import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import get_thumbnail, set_thumbnail, add_file, get_user, reset_user, create_user

# ==========================
# CONFIG
# ==========================
THUMB_TIMEOUT = 300
DOWNLOAD_DIR = "thumb_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==========================
# STATE
# ==========================
THUMB_MODE = set()          # user_id in thumb session
ACTIVE_THUMB = {}           # user_id -> running bool
SPEED_CACHE = {}            # progress cache
THUMB_STATS = {}            # stats

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
        if now - lt > 0:
            speed = (current - lb) / (now - lt)

    SPEED_CACHE[message.id] = (current, now)

    if not hasattr(progress_bar, "last"):
        progress_bar.last = 0
    if now - progress_bar.last < 5 and percent != 100:
        return
    progress_bar.last = now

    bar = "█" * (percent // 5) + "░" * (20 - percent // 5)
    speed_mb = speed / (1024 * 1024)
    eta = int((total - current) / speed) if speed > 0 else 0

    await safe_edit(
        message,
        f"🖼 {label}\n{bar}\n{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA {eta}s"
    )


def reset_stats(uid):
    THUMB_STATS[uid] = {"files": 0, "size": 0, "start": time.time()}


def finish_stats(uid):
    s = THUMB_STATS.pop(uid, None)
    if not s:
        return None
    t = time.time() - s["start"]
    return {
        "files": s["files"],
        "size": s["size"] / (1024 * 1024),
        "time": int(t),
        "speed": (s["size"] / t) / (1024 * 1024) if t > 0 else 0
    }

# ==========================
# REGISTER
# ==========================
def register_thumbnail(app: Client):

    # -------- START SESSION --------
    @app.on_message(filters.command("thumbstart"))
    async def thumbstart(_, msg):
        uid = msg.from_user.id
        THUMB_MODE.add(uid)
        reset_stats(uid)

        await msg.reply(
            "🖼 **Thumbnail Session Started**\n\n"
            "📦 Send / forward files (they will be queued)\n"
            "🖼 Use /thumbset to set or replace thumbnail\n"
            "▶️ Use /thumbapply to apply thumbnail\n"
            "❌ /thumbstop to exit"
        )

    # -------- SET / REPLACE THUMB --------
    @app.on_message(filters.command("thumbset"))
    async def thumbset(_, msg):
        await msg.reply("🖼 Send the thumbnail image")

    @app.on_message(filters.photo)
    async def save_thumb(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return

        set_thumbnail(uid, msg.photo.file_id)
        await msg.reply("✅ Thumbnail saved (persistent)")

    # -------- QUEUE FILES ONLY --------
    @app.on_message(filters.document | filters.video)
    async def queue_files(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return

        media = msg.document or msg.video
        add_file(uid, {
            "chat_id": msg.chat.id,
            "message_id": msg.id,
            "file_name": media.file_name or "file",
            "size": media.file_size or 0
        })

        await msg.reply("📦 File queued for thumbnail")

    # -------- APPLY THUMB (EXECUTOR) --------
    @app.on_message(filters.command("thumbapply"))
    async def thumbapply(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return await msg.reply("⚠️ Thumbnail session not active")

        thumb = get_thumbnail(uid)
        if not thumb:
            return await msg.reply("❌ No thumbnail set")

        user = get_user(uid)
        files = user.get("files", [])
        if not files:
            return await msg.reply("⚠️ No files queued")

        ACTIVE_THUMB[uid] = True
        status = await msg.reply("🖼 Applying thumbnail...")
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        for f in files:
            if not ACTIVE_THUMB.get(uid):
                break

            original = await app.get_messages(f["chat_id"], f["message_id"])
            path = await app.download_media(
                original,
                file_name=os.path.join(DOWNLOAD_DIR, f["file_name"]),
                progress=progress_bar,
                progress_args=(status, time.time(), "Downloading")
            )

            await app.send_document(
                msg.chat.id,
                document=path,
                thumb=thumb,
                file_name=f["file_name"],
                progress=progress_bar,
                progress_args=(status, time.time(), "Uploading")
            )

            THUMB_STATS[uid]["files"] += 1
            THUMB_STATS[uid]["size"] += os.path.getsize(path)
            os.remove(path)

        summary = finish_stats(uid)
        reset_user(uid)
        create_user(uid)
        ACTIVE_THUMB.pop(uid, None)

        await status.edit_text(
            "✅ **Thumbnail Applied**\n\n"
            f"📦 Files: {summary['files']}\n"
            f"💾 Size: {summary['size']:.2f} MB\n"
            f"⏱ Time: {summary['time']}s\n"
            f"⚡ Avg speed: {summary['speed']:.2f} MB/s"
        )

    # -------- STOP SESSION --------
    @app.on_message(filters.command("thumbstop"))
    async def thumbstop(_, msg):
        uid = msg.from_user.id
        THUMB_MODE.discard(uid)
        ACTIVE_THUMB.pop(uid, None)
        SPEED_CACHE.clear()
        await msg.reply("❌ Thumbnail session ended")
