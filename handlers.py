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

    # ---------- PROCESS ----------
    @app.on_message(filters.command("process"))
    async def process(_, msg):
        user = get_user(msg.from_user.id)
        if not user or not user["files"]:
            return await msg.reply("❌ No files")

        rename = user["rename"]
        status = await msg.reply("🚀 Starting...")

        for i, f in enumerate(user["files"]):
            name = f"{rename['base']} S{rename['season']}E{rename['episode']+i:02d}.mkv"
            path = await app.download_media(f["file_id"])
            await app.send_document(msg.chat.id, document=path, file_name=name)

        await status.edit_text("✅ Completed")
