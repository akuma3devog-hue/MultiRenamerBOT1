import re
import time
import asyncio
import os

from pyrogram import Client, filters
from pyrogram.errors import FloodWait

from mongo import reset_user, create_user, add_file, get_user

# =========================================================
# PROCESS CONTROL
# =========================================================
ACTIVE_PROCESSES = {}          # user_id -> bool
SPEED_CACHE = {}               # message_id -> (bytes, time)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================================================
# RENAME SESSION STATE
# =========================================================
RENAMEMODE = set()
MODE = {}                      # user_id -> "manual" | "auto"
MANUAL_NAMES = {}              # user_id -> [names]
AUTO_CONF = {}                 # user_id -> config

# =========================================================
# AUTO CLEAN SYSTEM
# =========================================================
AUTO_CLEAN_SECONDS = 12 * 60 * 60        # 12 hours
WARNING_BEFORE = 10 * 60                 # 10 minutes before cleanup
LAST_ACTIVITY = {}                       # user_id -> timestamp
WARNED = set()                           # users warned already

def touch(uid: int):
    LAST_ACTIVITY[uid] = time.time()
    WARNED.discard(uid)

# =========================================================
# PROGRESS BAR
# =========================================================
async def progress_bar(current, total, message, start, label):
    if total == 0:
        return

    now = time.time()
    percent = int(current * 100 / total)

    last_edit = getattr(progress_bar, "last", 0)
    if now - last_edit < 4 and percent != 100:
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
            f"🚀 {label}\n{bar}\n{percent}% | ⚡ {speed_mb:.2f} MB/s | ETA {eta}s"
        )
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except:
        pass

# =========================================================
# EPISODE DETECTION (OPTIMIZED)
# =========================================================
def extract_episode(name: str) -> int | None:
    patterns = [
        r"[Ss](\d+)[Ee](\d+)",      # S01E05
        r"[Ee](\d+)",               # E05
        r"[Ee]pisode\s*(\d+)",      # Episode 5
    ]
    for p in patterns:
        m = re.search(p, name, re.IGNORECASE)
        if m:
            return int(m.group(m.lastindex))
    return None

# =========================================================
# REGISTER HANDLERS
# =========================================================
def register_handlers(app: Client):

    # ---------- START ----------
    @app.on_message(filters.command("start"))
    async def start(_, msg):
        uid = msg.from_user.id
        touch(uid)
        reset_user(uid)
        create_user(uid)
        await msg.reply(
            "👋 Welcome\n\n"
            "/renamestart – start rename\n"
            "/help – all commands"
        )

    # ---------- HELP ----------
    @app.on_message(filters.command("help"))
    async def help_cmd(_, msg):
        uid = msg.from_user.id
        touch(uid)
        await msg.reply(
            "📘 Commands\n\n"
            "/renamestart\n"
            "/manual\n"
            "/automatic\n"
            "/rename\n"
            "/process\n"
            "/status\n"
            "/cancel\n"
            "/renamestop"
        )

    # ---------- STATUS ----------
    @app.on_message(filters.command("status"))
    async def status(_, msg):
        uid = msg.from_user.id
        touch(uid)
        user = get_user(uid)
        files = len(user.get("files", [])) if user else 0

        await msg.reply(
            f"📊 Status\n\n"
            f"Rename: {'ON' if uid in RENAMEMODE else 'OFF'}\n"
            f"Mode: {MODE.get(uid, 'N/A')}\n"
            f"Files: {files}\n"
            f"Processing: {'YES' if ACTIVE_PROCESSES.get(uid) else 'NO'}"
        )

    # ---------- RENAME START ----------
    @app.on_message(filters.command("renamestart"))
    async def renamestart(_, msg):
        uid = msg.from_user.id
        touch(uid)

        RENAMEMODE.add(uid)
        MODE.pop(uid, None)
        MANUAL_NAMES.pop(uid, None)
        AUTO_CONF.pop(uid, None)

        reset_user(uid)
        create_user(uid)

        await msg.reply(
            "✏️ Rename enabled\n\n"
            "/manual or /automatic"
        )

    # ---------- RENAME STOP ----------
    @app.on_message(filters.command("renamestop"))
    async def renamestop(_, msg):
        uid = msg.from_user.id
        touch(uid)

        RENAMEMODE.discard(uid)
        MODE.pop(uid, None)
        MANUAL_NAMES.pop(uid, None)
        AUTO_CONF.pop(uid, None)

        reset_user(uid)
        create_user(uid)

        await msg.reply("❌ Rename stopped")

    # ---------- MANUAL ----------
    @app.on_message(filters.command("manual"))
    async def manual(_, msg):
        uid = msg.from_user.id
        touch(uid)

        if uid not in RENAMEMODE:
            return await msg.reply("Use /renamestart")

        MODE[uid] = "manual"
        MANUAL_NAMES[uid] = []

        await msg.reply("✍️ Manual mode\nSend files then names")

    # ---------- AUTOMATIC ----------
    @app.on_message(filters.command("automatic"))
    async def automatic(_, msg):
        uid = msg.from_user.id
        touch(uid)

        if uid not in RENAMEMODE:
            return await msg.reply("Use /renamestart")

        MODE[uid] = "auto"
        await msg.reply("🤖 Automatic mode\nUse /rename")

    # ---------- AUTO CONFIG ----------
    @app.on_message(filters.command("rename"))
    async def set_auto(_, msg):
        uid = msg.from_user.id
        touch(uid)

        if MODE.get(uid) != "auto":
            return

        text = msg.text.split(" ", 1)[1]
        se = re.search(r"S(\d+)E(\d+)", text)
        if not se:
            return await msg.reply("Format: Name S1E1")

        AUTO_CONF[uid] = {
            "base": re.split(r"S\d+E\d+", text, 1)[0].strip(),
            "season": int(se.group(1)),
            "start_ep": int(se.group(2)),
            "quality": re.search(r"(480p|720p|1080p)", text),
            "tag": re.search(r"@\S+", text)
        }

        await msg.reply("✅ Pattern saved")

    # ---------- CANCEL ----------
    @app.on_message(filters.command("cancel"))
    async def cancel(_, msg):
        uid = msg.from_user.id
        touch(uid)
        ACTIVE_PROCESSES[uid] = False
        await msg.reply("🛑 Cancelled")

    # ---------- FILE QUEUE ----------
    @app.on_message(filters.document | filters.video)
    async def queue(_, msg):
        uid = msg.from_user.id
        if uid not in RENAMEMODE:
            return

        touch(uid)

        media = msg.document or msg.video
        add_file(uid, {
            "chat_id": msg.chat.id,
            "message_id": msg.id,
            "file_name": media.file_name,
            "size": media.file_size or 0
        })

        await msg.reply("📂 File added")

    # ---------- MANUAL NAME ----------
    @app.on_message(filters.text & ~filters.regex(r"^/"))
    async def manual_name(_, msg):
        uid = msg.from_user.id
        if MODE.get(uid) == "manual":
            touch(uid)
            MANUAL_NAMES[uid].append(msg.text)
            await msg.reply("✅ Name saved")

    # ---------- PROCESS ----------
    @app.on_message(filters.command("process"))
    async def process(_, msg):
        uid = msg.from_user.id
        touch(uid)

        user = get_user(uid)
        files = user.get("files", [])

        if not files:
            return await msg.reply("No files")

        if MODE.get(uid) == "manual" and len(MANUAL_NAMES[uid]) != len(files):
            return await msg.reply("Names mismatch")

        ACTIVE_PROCESSES[uid] = True
        status = await msg.reply("🚀 Processing")

        try:
            for i, f in enumerate(files):
                if not ACTIVE_PROCESSES.get(uid):
                    break

                if MODE[uid] == "manual":
                    filename = MANUAL_NAMES[uid][i]
                else:
                    conf = AUTO_CONF[uid]
                    ep = extract_episode(f["file_name"])
                    ep = ep if ep is not None else conf["start_ep"] + i

                    filename = (
                        f"{conf['base']} "
                        f"S{conf['season']}E{ep:02d} "
                        f"{conf['quality'].group(1) if conf['quality'] else ''} "
                        f"{conf['tag'].group(0) if conf['tag'] else ''}"
                    ).strip()

                original = await app.get_messages(f["chat_id"], f["message_id"])
                part = f"{DOWNLOAD_DIR}/{filename}.mkv.part"
                final = part.replace(".part", "")

                await app.download_media(
                    original,
                    file_name=part,
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Downloading")
                )

                os.rename(part, final)

                await app.send_document(
                    msg.chat.id,
                    final,
                    file_name=os.path.basename(final),
                    progress=progress_bar,
                    progress_args=(status, time.time(), "Uploading")
                )

                os.remove(final)

        finally:
            ACTIVE_PROCESSES.pop(uid, None)
            SPEED_CACHE.clear()
            reset_user(uid)
            create_user(uid)

        await status.edit_text("✅ Completed")

# =========================================================
# AUTO CLEAN BACKGROUND TASK
# =========================================================
async def auto_cleanup_task(app: Client):
    while True:
        now = time.time()

        for uid, last in list(LAST_ACTIVITY.items()):
            idle = now - last

            if idle >= AUTO_CLEAN_SECONDS - WARNING_BEFORE and uid not in WARNED:
                try:
                    await app.send_message(
                        uid,
                        "⚠️ Session inactive.\nWill auto-clear in 10 minutes."
                    )
                except:
                    pass
                WARNED.add(uid)

            if idle >= AUTO_CLEAN_SECONDS:
                try:
                    await app.send_message(
                        uid,
                        "🧾 Session cleared due to inactivity.\nStart again with /renamestart"
                    )
                except:
                    pass

                ACTIVE_PROCESSES.pop(uid, None)
                RENAMEMODE.discard(uid)
                MODE.pop(uid, None)
                MANUAL_NAMES.pop(uid, None)
                AUTO_CONF.pop(uid, None)

                reset_user(uid)
                create_user(uid)

                LAST_ACTIVITY.pop(uid, None)
                WARNED.discard(uid)

        await asyncio.sleep(300)
