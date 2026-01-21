import os
import time
import re
from pyrogram import filters

# ===== IMPORTS FROM YOUR PROJECT =====
from main import app, DOWNLOAD_DIR
from database import get_user, reset_user, create_user, touch
from progress import progress_bar

# ===== GLOBAL RUNTIME STORES =====
ACTIVE_PROCESSES = {}
MODE = {}            # uid -> "manual" | "auto"
MANUAL_NAMES = {}   # uid -> [list of names]
AUTO_CONF = {}      # uid -> config dict
SPEED_CACHE = {}    # used by progress_bar


# ===== HELPER FUNCTIONS =====

def extract_episode(filename: str):
    """
    Try to extract episode number from filename like:
    S01E02, E02, Ep02, Episode 02, etc.
    """
    patterns = [
        r"[Ss]\d{1,2}[Ee](\d{1,3})",
        r"\b[Ee][Pp]?\s?(\d{1,3})",
        r"\bEpisode\s?(\d{1,3})",
        r"\b(\d{1,3})\b"
    ]

    for pat in patterns:
        m = re.search(pat, filename)
        if m:
            try:
                return int(m.group(1))
            except:
                pass

    return None


# ---------- PROCESS ----------

@app.on_message(filters.command("process"))
async def process(_, msg):
    uid = msg.from_user.id
    touch(uid)

    user = get_user(uid)
    files = user.get("files", [])

    if not files:
        return await msg.reply("No files")

    if MODE.get(uid) == "manual" and len(MANUAL_NAMES.get(uid, [])) != len(files):
        return await msg.reply("Names mismatch")

    ACTIVE_PROCESSES[uid] = True
    status = await msg.reply("🚀 Processing")

    try:
        for i, f in enumerate(files):
            if not ACTIVE_PROCESSES.get(uid):
                break

            if MODE.get(uid) == "manual":
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
