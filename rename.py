import re
from mongo import get_user, set_rename

def register_rename(bot):

    @bot.message_handler(commands=["rename"])
    def rename_handler(message):
        user_id = message.from_user.id
        user = get_user(user_id)

        if not user:
            bot.reply_to(message, "❌ Use /start first.")
            return

        if not user.get("files"):
            bot.reply_to(message, "❌ No files uploaded.")
            return

        # Remove command part
        text = message.text.replace("/rename", "").strip()

        if not text:
            bot.reply_to(
                message,
                "❌ Usage:\n"
                "<code>/rename Naruto S1E</code>\n"
                "<code>/rename Naruto | S2E15</code>",
                parse_mode="HTML"
            )
            return

        # Split base name and episode pattern
        if "|" in text:
            base, ep_part = map(str.strip, text.split("|", 1))
        else:
            base = text
            ep_part = "S1E1"

        # Parse SxEy
        match = re.search(r"S(\d+)E(\d*)", ep_part, re.IGNORECASE)
if not match:
    bot.reply_to(
        message,
        "❌ Invalid format.\nUse: S1E, S1E1, S2E15",
        parse_mode="HTML"
    )
    return

season = int(match.group(1))
episode = int(match.group(2)) if match.group(2) else 1

        rename_data = {
            "base": base.strip(),
            "season": season,
            "episode": episode,
            "zero_pad": True
        }

        set_rename(user_id, rename_data)

        bot.reply_to(
            message,
            f"✅ <b>Rename pattern set</b>\n\n"
            f"<b>Base:</b> {base}\n"
            f"<b>Season:</b> {season}\n"
            f"<b>Starting Episode:</b> {str(episode).zfill(2)}\n\n"
            f"Use <code>/process</code> to apply",
            parse_mode="HTML"
        )
