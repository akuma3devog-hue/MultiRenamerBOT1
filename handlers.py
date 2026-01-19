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
from thumbnail import THUMB_MODE

# =========================================================
# PROCESS + SPEED
# =========================================================
ACTIVE_PROCESSES = {}
SPEED_CACHE = {}

# =========================================================
# RENAME MODE SYSTEM (NEW)
# =========================================================
RENAMEMODE = set()              # user_id
RENAME_TYPE = {}                # user_id -> manual / auto
MANUAL_NAME = {}                # user_id -> str

# ---------------- PROGRESS BAR ----------------
async def progress_bar(current, total, message, start, label):
    if total == 0:
        return

    percent = int(current * 100 / total)
    now = time.time()

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

    speed_mb = speed / (1024 * 1024)
    bar = "█" * int(percent / 5) + "░" * (20 - int(percent / 5))
    eta = int((total - current) / speed) if speed > 0 else 0

    try:
        await message.edit_text(
            f"🚀 {label}\n{bar}\n{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA {eta}s"
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except:
        pass


# ---------------- HELPERS ----------------
def extract_episode(name):
    patterns = [
        r"[Ee](\d+)",
        r"[Ee]pisode\s*(\d+)",
        r"\b(\d{1,3})\b"
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
            "✅ Started\n\n"
            "/renamestart\n"
            "/manual <name>\n"
            "/automatic\n"
            "/renamestop\n"
            "/process\n"
            "/cancel"
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
            return await msg.reply("❌ Give a name")
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

    # ---------- FILE COLLECT ----------
    @app.on_message(filters.document | filters.video)
    async def upload(_, msg):

        # 🚫 BLOCK rename handler when thumbnail mode is active
        if msg.from_user.id in THUMB_MODE:
            return

        add_file(msg.from_user.id, {
            "chat_id": msg.chat.id,
            "message_id": msg.id,
            "file_name": (msg.document or msg.video).file_name or "file.mkv",
            "size": (msg.document or msg.video).file_size or 0
        })

        await msg.reply("📂 Added")

    # ---------- PROCESS ----------
    @app.on_message(filters.command("process"))
    async def process(_, msg):
        uid = msg.from_user.id

        if uid not in RENAMEMODE:
            return await msg.reply("⚠️ Rename mode not active")

        ACTIVE_PROCESSES[uid] = True
        user = get_user(uid)

        files = user.get("files", [])
        status = await msg.reply("🚀 Processing...")
        os.makedirs("downloads", exist_ok=True)

        for i, f in enumerate(files, 1):
            if not ACTIVE_PROCESSES.get(uid):
                break

            ep = extract_episode(f["file_name"])
            if RENAME_TYPE.get(uid) == "manual":
                filename = MANUAL_NAME[uid]
            else:
                filename = f"{MANUAL_NAME.get(uid, 'Episode')} E{ep or i:02d}"

            path = await app.download_media(
                await app.get_messages(f["chat_id"], f["message_id"]),
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

        reset_user(uid)
        create_user(uid)
        await status.edit_text("✅ Done")
