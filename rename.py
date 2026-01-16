import re
from mongo import set_rename

def register_rename(bot):

    @bot.message_handler(commands=["rename"])
    def rename_cmd(message):
        user_id = message.from_user.id
        args = message.text.replace("/rename", "").strip()

        if not args:
            bot.reply_to(
                message,
                "❌ Usage:\n"
                "<code>/rename Naruto S1E</code>\n"
                "<code>/rename Naruto | S2E15</code>",
                parse_mode="HTML"
            )
            return

        # Custom start support
        if "|" in args:
            base, ep = map(str.strip, args.split("|", 1))
        else:
            base, ep = args, "S1E1"

        match = re.search(r"S(\d+)E(\d+)", ep, re.I)
        if not match:
            bot.reply_to(message, "❌ Invalid format. Use S1E or S1E12")
            return

        season = int(match.group(1))
        episode = int(match.group(2))
        zero_pad = episode < 10

        set_rename(user_id, {
            "base": base,
            "season": season,
            "episode": episode,
            "zero_pad": zero_pad
        })

        bot.reply_to(
            message,
            f"✅ Rename set:\n"
            f"<b>{base}</b>\n"
            f"S{season}E{episode}",
            parse_mode="HTML"
        )
