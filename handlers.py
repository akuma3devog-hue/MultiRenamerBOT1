import re
import time
import os
import asyncio

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import reset_user, create_user, add_file, get_user

# ==============================
# PROCESS CONTROL
# ==============================
ACTIVE_PROCESSES = {}
SPEED_CACHE = {}

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==============================
# RENAME MODES
# ==============================
RENAMEMODE = set()
MODE = {}                 # user_id -> manual | auto
MANUAL_NAMES = {}         # user_id -> list[str]
AUTO_CONF = {}            # user_id -> dict

# ==============================
# PROGRESS BAR (FAST + SAFE)
# ==============================
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
        dt = now - lt
        if dt > 0:
            speed = (current - lb) / dt

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

# ==============================
# EPISODE DETECTION (STRONG)
# ==============================
def extract_episode(name: str) -> int:
    patterns = [
        r"[Ss]\d+\s*[Ee](\d+)",        # S01E05
        r"\b[Ee]p?(\d{1,3})\b",        # E05 / EP5
        r"\bEpisode\s*(\d{1,3})\b",
        r"\b-\s*(\d{1,3})\b",          # - 12
    ]
    for p in patterns:
        m = re.search(p, name, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return 0

# ==============================
# REGISTER
# ==============================
def register_handlers(app: Client):

    # ---------- START ----------
    @app.on_message(filters.command("start"))
    async def start(_, msg):
        reset_user(msg.from_user.id)
        create_user(msg.from_user.id)
        await msg.reply(
            "✅ Bot Ready\n\n"
            "/renamestart\n"
            "/manual\n"
            "/automatic\n"
            "/name <pattern>\n"
            "/process\n"
            "/renamestop\n"
            "/cancel"
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
        await msg.reply("✏️ Rename mode started")

    # ---------- RENAME STOP ----------
    @app.on_message(filters.command("renamestop"))
    async def renamestop(_, msg):
        uid = msg.from_user.id
        RENAMEMODE.discard(uid)
        MODE.pop(uid, None)
        MANUAL_NAMES.pop(uid, None)
        AUTO_CONF.pop(uid, None)
        reset_user(uid)
        await msg.reply("❌ Rename mode stopped")

    # ---------- MANUAL ----------
    @app.on_message(filters.command("manual"))
    async def manual(_, msg):
        uid = msg.from_user.id
        if uid not in RENAMEMODE:
            return await msg.reply("Use /renamestart first")
        MODE[uid] = "manual"
        MANUAL_NAMES[uid] = []
        await msg.reply("✍️ Manual mode enabled\nSend file → send name")

    # ---------- AUTOMATIC ----------
    @app.on_message(filters.command("automatic"))
    async def automatic(_, msg):
        uid = msg.from_user.id
        if uid not in RENAMEMODE:
            return await msg.reply("Use /renamestart first")
        MODE[uid] = "auto"
        await msg.reply("🤖 Automatic mode enabled")

    # ---------- AUTO NAME ----------
    @app.on_message(filters.command("name"))
    async def set_name(_, msg):
        uid = msg.from_user.id
        if MODE.get(uid) != "auto":
            return
        text = msg.text.split(" ", 1)
        if len(text) < 2:
            return await msg.reply("Usage: /name Naruto S1 480p @tag")
        AUTO_CONF[uid] = {"base": text[1]}
        await msg.reply("✅ Auto naming pattern saved")

    # ---------- CANCEL ----------
    @app.on_message(filters.command("cancel"))
    async def cancel(_, msg):
        ACTIVE_PROCESSES[msg.from_user.id] = False
        await msg.reply("🛑 Cancel requested")

    # ---------- FILE QUEUE ----------
    @app.on_message(filters.document | filters.video)
    async def queue_files(_, msg):
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

        await msg.reply("📦 File queued")

    # ---------- MANUAL NAME ----------
@app.on_message(filters.text & ~filters.regex(r"^/"))
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
            return await msg.reply("❌ No files queued")

        if MODE.get(uid) == "manual":
            if len(MANUAL_NAMES.get(uid, [])) != len(files):
                return await msg.reply("❌ File count ≠ name count")

        if MODE.get(uid) == "auto" and uid not in AUTO_CONF:
            return await msg.reply("❌ Use /name first")

        ACTIVE_PROCESSES[uid] = True
        status = await msg.reply("🚀 Processing...")

        try:
            for i, f in enumerate(files):
                if not ACTIVE_PROCESSES.get(uid):
                    await status.edit_text("🛑 Process cancelled")
                    break

                if MODE.get(uid) == "manual":
                    filename = MANUAL_NAMES[uid][i]
                else:
                    ep = extract_episode(f["file_name"])
                    base = AUTO_CONF[uid]["base"]
                    filename = f"{base} E{ep or i+1:02d}"

                original = await app.get_messages(f["chat_id"], f["message_id"])
                path = await app.download_media(
                    original,
                    file_name=f"{DOWNLOAD_DIR}/{filename}.mkv",
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

        finally:
            ACTIVE_PROCESSES.pop(uid, None)
            SPEED_CACHE.clear()

            for f in os.listdir(DOWNLOAD_DIR):
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, f))
                except:
                    pass

            reset_user(uid)
            create_user(uid)

        await status.edit_text("✅ Done")
