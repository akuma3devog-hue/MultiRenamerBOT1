import re
import time
import os
import asyncio
import uuid

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import reset_user, create_user, add_file, get_user

# =========================================================
# GLOBAL STATE
# =========================================================
ACTIVE_PROCESSES = {}          # user_id -> bool
SPEED_CACHE = {}               # message_id -> (bytes, time)

RENAMEMODE = set()             # active users
MODE = {}                      # user_id -> manual | auto

MANUAL_NAMES = {}              # user_id -> list of names (order based)
AUTO_CONF = {}                 # user_id -> rename config

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================================================
# PROGRESS BAR (SAFE)
# =========================================================
async def progress_bar(current, total, message, start, label):
    if total == 0:
        return

    now = time.time()
    percent = int(current * 100 / total)

    last_edit = getattr(progress_bar, "last", 0)
    if now - last_edit < 3 and percent != 100:
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
            f"🚀 {label}\n"
            f"{bar}\n"
            f"{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA {eta}s"
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except:
        pass

# =========================================================
# EPISODE DETECTION (ROBUST)
# =========================================================
def extract_episode(name: str) -> int:
    patterns = [
        r"[Ss]\d+[Ee](\d+)",
        r"[Ee](\d+)",
        r"[Ee]pisode\s*(\d+)",
        r"\b(\d{1,3})\b"
    ]
    for p in patterns:
        m = re.search(p, name, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0

# =========================================================
# REGISTER HANDLERS
# =========================================================
def register_handlers(app: Client):

    # ---------- START ----------
    @app.on_message(filters.command("start"))
    async def start(_, msg):
        reset_user(msg.from_user.id)
        create_user(msg.from_user.id)
        await msg.reply(
            "👋 Welcome\n\n"
            "/renamestart – start rename mode\n"
            "/manual – manual rename\n"
            "/automatic – automatic rename\n"
            "/process – execute\n"
            "/renamestop – stop\n"
            "/cancel – cancel process"
        )

    # ---------- RENAME START ----------
    @app.on_message(filters.command("renamestart"))
    async def renamestart(_, msg):
        uid = msg.from_user.id
        RENAMEMODE.add(uid)
        MODE.pop(uid, None)
        MANUAL_NAMES.pop(uid, None)
        AUTO_CONF.pop(uid, None)
        reset_user(uid)
        create_user(uid)
        await msg.reply("✏️ Rename mode enabled\nChoose /manual or /automatic")

    # ---------- RENAME STOP ----------
    @app.on_message(filters.command("renamestop"))
    async def renamestop(_, msg):
        uid = msg.from_user.id
        RENAMEMODE.discard(uid)
        MODE.pop(uid, None)
        MANUAL_NAMES.pop(uid, None)
        AUTO_CONF.pop(uid, None)
        await msg.reply("❌ Rename mode disabled")

    # ---------- MANUAL ----------
    @app.on_message(filters.command("manual"))
    async def manual(_, msg):
        uid = msg.from_user.id
        if uid not in RENAMEMODE:
            return await msg.reply("Use /renamestart first")

        MODE[uid] = "manual"
        MANUAL_NAMES[uid] = []
        await msg.reply(
            "✍️ Manual mode enabled\n"
            "Send file → then send name\n"
            "Repeat for multiple files"
        )

    # ---------- AUTOMATIC ----------
    @app.on_message(filters.command("automatic"))
    async def automatic(_, msg):
        uid = msg.from_user.id
        if uid not in RENAMEMODE:
            return await msg.reply("Use /renamestart first")

        MODE[uid] = "auto"
        await msg.reply(
            "🤖 Automatic mode enabled\n"
            "Send files, then use:\n"
            "/rename Name S1E1 720p @tag"
        )

    # ---------- AUTO CONFIG ----------
    @app.on_message(filters.command("rename"))
    async def set_auto(_, msg):
        uid = msg.from_user.id
        if MODE.get(uid) != "auto":
            return

        text = msg.text.split(" ", 1)[1]
        AUTO_CONF[uid] = {"base": text}
        await msg.reply("✅ Rename pattern saved\nUse /process")

    # ---------- CANCEL ----------
    @app.on_message(filters.command("cancel"))
    async def cancel(_, msg):
        ACTIVE_PROCESSES[msg.from_user.id] = False
        await msg.reply("🛑 Cancel requested")

    # ---------- FILE QUEUE ----------
    @app.on_message(filters.document | filters.video)
    async def queue(_, msg):
        uid = msg.from_user.id
        if uid not in RENAMEMODE:
            return

        media = msg.document or msg.video
        add_file(uid, {
            "chat_id": msg.chat.id,
            "message_id": msg.id,
            "file_name": media.file_name,
            "size": media.file_size or 0
        })

        if MODE.get(uid) == "manual":
            await msg.reply("📂 File added\nSend name now")
        else:
            await msg.reply(f"📂 Added: {media.file_name}")

    # ---------- MANUAL NAME INPUT ----------
    @app.on_message(filters.text & ~filters.command)
    async def manual_name(_, msg):
        uid = msg.from_user.id
        if MODE.get(uid) == "manual":
            MANUAL_NAMES.setdefault(uid, []).append(msg.text)
            await msg.reply("✅ Name saved")

    # ---------- PROCESS ----------
    @app.on_message(filters.command("process"))
    async def process(_, msg):
        uid = msg.from_user.id
        user = get_user(uid)
        files = user.get("files", [])

        if not files:
            return await msg.reply("❌ No files")

        ACTIVE_PROCESSES[uid] = True
        status = await msg.reply("🚀 Processing...")

        try:
            for i, f in enumerate(files):
                if not ACTIVE_PROCESSES.get(uid):
                    await status.edit_text("🛑 Cancelled")
                    break

                # SAFE unique temp filename
                tmp_name = f"tmp_{uid}_{uuid.uuid4().hex}.mkv"
                tmp_path = os.path.join(DOWNLOAD_DIR, tmp_name)

                if MODE.get(uid) == "manual":
                    filename = MANUAL_NAMES[uid][i]
                else:
                    ep = extract_episode(f["file_name"])
                    base = AUTO_CONF[uid]["base"]
                    filename = f"{base} E{ep or i+1:02d}"

                original = await app.get_messages(f["chat_id"], f["message_id"])

                path = await app.download_media(
                    original,
                    file_name=tmp_path,
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Downloading")
                )

                await app.send_document(
                    msg.chat.id,
                    document=path,
                    file_name=f"{filename}.mkv",
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Uploading")
                )

                os.remove(path)

        finally:
            ACTIVE_PROCESSES.pop(uid, None)
            SPEED_CACHE.clear()
            reset_user(uid)
            create_user(uid)

        await status.edit_text("✅ Completed")
