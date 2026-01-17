import re
import time
from pyrogram import Client, filters
from mongo import (
    reset_user, create_user, add_file, get_user, get_files,
    set_thumbnail, get_thumbnail, delete_thumbnail,
    set_awaiting_thumb, is_awaiting_thumb
)

# ---------------- PROGRESS BAR (THROTTLED) ----------------
async def progress_bar(current, total, status_msg, start_time, label):
    now = time.time()

    # throttle edits (very important)
    if hasattr(status_msg, "_last_edit"):
        if now - status_msg._last_edit < 1.2:
            return

    status_msg._last_edit = now

    if total == 0:
        return

    percent = int(current * 100 / total)
    filled = percent // 5
    bar = "█" * filled + "░" * (20 - filled)

    elapsed = now - start_time
    speed = current / elapsed if elapsed > 0 else 0
    eta = int((total - current) / speed) if speed > 0 else 0

    text = (
        f"🚀 {label}\n\n"
        f"{bar}\n"
        f"{percent}%\n"
        f"⏳ ETA: {eta}s"
    )

    try:
        await status_msg.edit_text(text)
    except:
        pass


# ---------------- HELPERS ----------------
def extract_episode(name):
    m = re.search(r"[Ee](\d+)", name)
    return int(m.group(1)) if m else 0


def register_handlers(app: Client):

    # ---------- START ----------
    @app.on_message(filters.command("start"))
    async def start(_, msg):
        reset_user(msg.from_user.id)
        create_user(msg.from_user.id)
        await msg.reply(
            "✅ Batch started\n\n"
            "📂 Send files\n"
            "/rename Name S1E1\n"
            "/process\n\n"
            "/setthumb • /viewthumb • /deletethumb"
        )

    # ---------- FILE UPLOAD ----------
    @app.on_message(filters.document | filters.video)
    async def upload(_, msg):
        user = get_user(msg.from_user.id)
        if not user:
            return

        media = msg.document or msg.video
        add_file(msg.from_user.id, {
            "file_id": media.file_id,
            "file_name": media.file_name or "video.mkv",
            "type": "document" if msg.document else "video"
        })

        await msg.reply(f"📂 Added: {media.file_name}")

    # ---------- RENAME ----------
    @app.on_message(filters.command("rename"))
    async def rename(_, msg):
        try:
            _, name, ep = msg.text.split(" ", 2)
            s = int(re.search(r"S(\d+)", ep).group(1))
            e = int(re.search(r"E(\d+)", ep).group(1))
        except:
            return await msg.reply("❌ Usage: /rename Name S1E1")

        from mongo import users
        users.update_one(
            {"user_id": msg.from_user.id},
            {"$set": {"rename": {"base": name, "season": s, "episode": e}}}
        )
        await msg.reply("✏️ Rename saved")

    # ---------- THUMB ----------
    @app.on_message(filters.command("setthumb"))
    async def setthumb(_, msg):
        set_awaiting_thumb(msg.from_user.id, True)
        await msg.reply("🖼 Send thumbnail image now")

    @app.on_message(filters.photo | filters.document)
    async def save_thumb(_, msg):
        if not is_awaiting_thumb(msg.from_user.id):
            return

        if msg.photo:
            file_id = msg.photo.file_id
        elif msg.document and msg.document.mime_type.startswith("image/"):
            file_id = msg.document.file_id
        else:
            return await msg.reply("❌ Send a valid image")

        set_thumbnail(msg.from_user.id, file_id)
        set_awaiting_thumb(msg.from_user.id, False)
        await msg.reply("✅ Thumbnail saved")

    @app.on_message(filters.command("viewthumb"))
    async def viewthumb(_, msg):
        thumb = get_thumbnail(msg.from_user.id)
        if not thumb:
            return await msg.reply("❌ No thumbnail set")
        await app.send_photo(msg.chat.id, thumb, caption="🖼 Current thumbnail")

    @app.on_message(filters.command("deletethumb"))
    async def deletethumb(_, msg):
        delete_thumbnail(msg.from_user.id)
        await msg.reply("🗑 Thumbnail removed")

    # ---------- PROCESS ----------
    @app.on_message(filters.command("process"))
    async def process(_, msg):
        user = get_user(msg.from_user.id)
        if not user or not user["files"]:
            return await msg.reply("❌ No files")

        rename = user["rename"]
        thumb = get_thumbnail(msg.from_user.id)

        files = sorted(
            user["files"],
            key=lambda f: extract_episode(f["file_name"])
        )

        status = await msg.reply("📥 Starting download…")

        for i, f in enumerate(files):
            ep_no = rename["episode"] + i
            name = f"{rename['base']} S{rename['season']}E{ep_no:02d}.mkv"

            # show immediate activity (prevents “stuck” feeling)
            await status.edit_text(f"📥 Downloading:\n{f['file_name']}")

            path = await app.download_media(
                f["file_id"],
                progress=progress_bar,
                progress_args=(status, time.time(), "Downloading")
            )

            await status.edit_text(f"📤 Uploading:\n{name}")

            await app.send_document(
                msg.chat.id,
                document=path,
                thumb=thumb,
                file_name=name,
                progress=progress_bar,
                progress_args=(status, time.time(), "Uploading")
            )

        await status.edit_text("✅ Completed")
