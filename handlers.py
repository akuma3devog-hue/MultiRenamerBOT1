# handlers.py
import re
import time
import asyncio
import os

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import (
    reset_user, create_user, add_file, get_user
)

# ⚠️ ONLY USED TO BLOCK RENAME DURING THUMB SESSION
from thumbnail import THUMB_MODE

# =========================================================
# PROCESS + SPEED
# =========================================================
ACTIVE_PROCESSES = {}
SPEED_CACHE = {}

# =========================================================
# RENAME MODE SYSTEM (UNCHANGED + SAFE)
# =========================================================
RENAMEMODE = set()
RENAME_TYPE = {}
MANUAL_NAME = {}

# ---------------- PROGRESS BAR ----------------
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

    try:
        await message.edit_text(
            f"🚀 {label}\n{bar}\n{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA {eta}s"
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except:
        pass


# ---------------- EPISODE DETECTION (IMPROVED) ----------------
def extract_episode(name: str) -> int:
    patterns = [
        r"[Ss]\d+[Ee](\d+)",      # S01E05
        r"[Ee](\d+)",             # E05
        r"[Ee]pisode\s*(\d+)",    # Episode 5
        r"\b(\d{1,3})\b"          # fallback
    ]
    for p in patterns:
        m = re.search(p, name, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0


# ================= REGISTER =================
def register_handlers(app: Client):

    # ---------- START ----------
    @app.on_message(filters.command("start"))
    async def start(_, msg):
        reset_user(msg.from_user.id)
        create_user(msg.from_user.id)
        await msg.reply(
            "✅ Bot Ready\n\n"
            "✏️ Rename:\n"
            "/renamestart\n"
            "/manual <name>\n"
            "/automatic\n"
            "/renamestop\n\n"
            "⚙️ Execute:\n"
            "/process\n"
            "/cancel\n\n"
            "🖼 Thumbnail handled separately"
        )

    # ---------- RENAME MODE ----------
    @app.on_message(filters.command("renamestart"))
    async def renamestart(_, msg):
        RENAMEMODE.add(msg.from_user.id)
        await msg.reply("✏️ Rename mode enabled")

    @app.on_message(filters.command("renamestop"))
    async def renamestop(_, msg):
        uid = msg.from_user.id
        RENAMEMODE.discard(uid)
        RENAME_TYPE.pop(uid, None)
        MANUAL_NAME.pop(uid, None)
        await msg.reply("❌ Rename mode disabled")

    @app.on_message(filters.command("manual"))
    async def manual(_, msg):
        uid = msg.from_user.id
        if uid not in RENAMEMODE:
            return await msg.reply("⚠️ Use /renamestart first")
        text = msg.text.split(" ", 1)
        if len(text) < 2:
            return await msg.reply("❌ Usage: /manual <name>")
        RENAME_TYPE[uid] = "manual"
        MANUAL_NAME[uid] = text[1]
        await msg.reply("✍️ Manual rename set")

    @app.on_message(filters.command("automatic"))
    async def automatic(_, msg):
        uid = msg.from_user.id
        if uid not in RENAMEMODE:
            return await msg.reply("⚠️ Use /renamestart first")
        RENAME_TYPE[uid] = "auto"
        await msg.reply("🤖 Automatic rename enabled")

    # ---------- CANCEL ----------
    @app.on_message(filters.command("cancel"))
    async def cancel(_, msg):
        ACTIVE_PROCESSES[msg.from_user.id] = False
        await msg.reply("🛑 Cancel requested")

    # ---------- FILE QUEUE (NO EXECUTION) ----------
    @app.on_message(filters.document | filters.video)
    async def queue_files(_, msg):
        uid = msg.from_user.id

        # 🚫 HARD BLOCK during thumbnail session
        if uid in THUMB_MODE:
            return

        media = msg.document or msg.video
        add_file(uid, {
            "chat_id": msg.chat.id,
            "message_id": msg.id,
            "file_name": media.file_name or "file.mkv",
            "size": media.file_size or 0
        })

        await msg.reply("📦 File queued")

    # ---------- PROCESS ----------
    @app.on_message(filters.command("process"))
    async def process(_, msg):
        uid = msg.from_user.id

        if uid not in RENAMEMODE:
            return await msg.reply("⚠️ Rename mode not active")

        user = get_user(uid)
        files = user.get("files", [])
        if not files:
            return await msg.reply("⚠️ No files queued")

        ACTIVE_PROCESSES[uid] = True
        status = await msg.reply("🚀 Processing...")
        os.makedirs("downloads", exist_ok=True)

        for i, f in enumerate(files, 1):
            if not ACTIVE_PROCESSES.get(uid):
                break

            ep = extract_episode(f["file_name"])

            if RENAME_TYPE.get(uid) == "manual":
                filename = MANUAL_NAME[uid]
            else:
                base = MANUAL_NAME.get(uid, "Episode")
                filename = f"{base} E{ep or i:02d}"

            original = await app.get_messages(f["chat_id"], f["message_id"])

            path = await app.download_media(
                original,
                file_name=f"downloads/{filename}.mkv",
                progress=progress_bar,
                progress_args=(status, time.time(), "Downloading")
            )

            await app.send_document(
                msg.chat.id,
                path,
                file_name=f"{filename}.mkv",
                progress=progress_bar,
                progress_args=(status, time.time(), "Uploading")
            )

            os.remove(path)

        ACTIVE_PROCESSES.pop(uid, None)
        SPEED_CACHE.clear()
        reset_user(uid)
        create_user(uid)

        await status.edit_text("✅ Rename completed")
