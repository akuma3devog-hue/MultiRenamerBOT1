# rename.py
from mongo import set_rename

def register_rename(bot):

    @bot.message_handler(commands=["rename"])
    def rename_cmd(message):
        """
        Usage:
        /rename Naruto S1E
        /rename Naruto S01E
        """
        user_id = message.from_user.id
        parts = message.text.split(maxsplit=2)

        if len(parts) < 3:
            bot.reply_to(
                message,
                "❌ Usage:\n<code>/rename Naruto S1E</code>",
                parse_mode="HTML"
            )
            return

        title = parts[1]
        pattern = parts[2].upper()

        # Detect season & episode pattern
        if "S" not in pattern or "E" not in pattern:
            bot.reply_to(
                message,
                "❌ Invalid format. Use S1E or S01E",
                parse_mode="HTML"
            )
            return

        zero_pad = "01" in pattern

        rename_data = {
            "title": title,
            "pattern": pattern,
            "zero_pad": zero_pad
        }

        set_rename(user_id, rename_data)

        bot.reply_to(
            message,
            "✅ <b>Rename pattern saved!</b>\n\n"
            f"📛 Title: <b>{title}</b>\n"
            f"📐 Pattern: <b>{pattern}</b>",
            parse_mode="HTML"
        )
