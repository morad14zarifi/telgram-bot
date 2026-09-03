"""
ربات تلگرام - نسخه آماده برای Railway
توکن از متغیر محیطی BOT_TOKEN خونده میشه (نه هاردکد تو فایل)
"""

import logging
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("متغیر محیطی BOT_TOKEN تنظیم نشده! باید تو تنظیمات Railway اضافه‌ش کنی.")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! من روشنم و منتظر پیام تو هستم 🤖")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"گفتی: {update.message.text}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
