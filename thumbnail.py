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
DOWNLOAD_DIR = "thumb_downloads"
THUMB_TIMEOUT = 300  # 5 minutes
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==========================
# STATE
# ==========================
THUMB_MODE = set()                 # user_ids in thumb session
THUMB_QUEUE = {}                   # user_id -> list of files
ACTIVE_THUMB = {}                  # user_id -> bool
LAST_ACTIVE = {}                   # user_id -> last activity time
SPEED_CACHE = {}                   # message_id -> speed calc

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

    speed_mb = speed / (1024 * 1024)
    eta = int((total - current) / speed) if speed > 0 else 0
    bar = "█" * (percent // 5) + "░" * (20 - percent // 5)

    await safe_edit(
        message,
        f"🚀 {label}\n{bar}\n{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA {eta}s"
    )


def reset_thumb(uid):
    THUMB_QUEUE.pop(uid, None)
    ACTIVE_THUMB.pop(uid, None)
    LAST_ACTIVE.pop(uid, None)
    SPEED_CACHE.clear()


# ==========================
# REGISTER
# ==========================
def register_thumbnail(app: Client):

    # -------- START SESSION --------
    @app.on_message(filters.command("thumbstart"))
    async def thumbstart(_, msg):
        uid = msg.from_user.id
        THUMB_MODE.add(uid)
        THUMB_QUEUE[uid] = []
        LAST_ACTIVE[uid] = time.time()

        await msg.reply(
            "🖼 **Thumbnail Session Started**\n\n"
            "• Send / forward files (they will be queued)\n"
            "• Use /thumbset to set or change thumbnail\n"
            "• Use /thumbapply to apply thumbnail\n"
            "• /thumbstop to exit"
        )

    # -------- SET / REPLACE THUMB --------
    @app.on_message(filters.command("thumbset"))
    async def thumbset(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return await msg.reply("⚠️ Thumbnail session not active")

        LAST_ACTIVE[uid] = time.time()
        await msg.reply("📸 Send thumbnail image now")

    @app.on_message(filters.photo)
    async def save_thumb(_, msg):
        uid = msg.from_user.id
        if uid not in THUMB_MODE:
            return

        set_thumbnail(uid, msg.photo.file_id)
        LAST_ACTIVE[uid] = time.time()
        await msg.reply("✅ Thumbnail saved (will be reused)")

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
            "file_name": media.file_name or "file.mkv",
            "size": media.file_size or 0
        })

        LAST_ACTIVE[uid] = time.time()
        await msg.reply("📦 File queued for thumbnail")

    # -------- APPLY THUMB --------
    @app.on_message(filters.command("thumbapply"))
    async def thumbapply(_, msg):
        uid = msg.from_user.id

        if uid not in THUMB_MODE:
            return await msg.reply("⚠️ Thumbnail session not active")

        files = THUMB_QUEUE.get(uid, [])
        if not files:
            return await msg.reply("⚠️ No files queued")

        thumb = get_thumbnail(uid)
        if not thumb:
            return await msg.reply("❌ No thumbnail set")

        ACTIVE_THUMB[uid] = True
        LAST_ACTIVE[uid] = time.time()

        status = await msg.reply("🚀 Applying thumbnails...")
        total = len(files)

        for i, f in enumerate(files, 1):
            if not ACTIVE_THUMB.get(uid):
                break

            # auto-timeout protection
            if time.time() - LAST_ACTIVE.get(uid, 0) > THUMB_TIMEOUT:
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

            os.remove(path)

        reset_thumb(uid)
        await status.edit_text("✅ Thumbnail applied to all queued files")

    # -------- STOP SESSION --------
    @app.on_message(filters.command("thumbstop"))
    async def thumbstop(_, msg):
        uid = msg.from_user.id
        THUMB_MODE.discard(uid)
        reset_thumb(uid)
        await msg.reply("❌ Thumbnail session ended")

    # -------- CANCEL --------
    @app.on_message(filters.command("cancel"))
    async def cancel(_, msg):
        uid = msg.from_user.id
        ACTIVE_THUMB[uid] = False
        await msg.reply("🛑 Thumbnail process cancelled")
