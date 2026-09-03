"""
ربات تلگرام - نسخه پیشرفته با منو و دکمه‌های شیشه‌ای (Inline Keyboard)
توکن از متغیر محیطی BOT_TOKEN خونده میشه
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("متغیر محیطی BOT_TOKEN تنظیم نشده! باید تو تنظیمات Railway اضافه‌ش کنی.")


# ---------- دستورها (Commands) ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋 به ربات خوش اومدی.\n"
        "برای دیدن منو بنویس /menu\n"
        "برای راهنما بنویس /help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 دستورهای موجود:\n\n"
        "/start - شروع کار با ربات\n"
        "/menu - نمایش منوی دکمه‌دار\n"
        "/help - نمایش همین راهنما\n\n"
        "همچنین می‌تونی هر پیامی بفرستی، من تکرارش می‌کنم."
    )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📌 گزینه یک", callback_data="option_1"),
            InlineKeyboardButton("📌 گزینه دو", callback_data="option_2"),
        ],
        [
            InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("یکی از گزینه‌ها رو انتخاب کن:", reply_markup=reply_markup)


# ---------- واکنش به کلیک روی دکمه‌ها ----------

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # به تلگرام میگه که کلیک دریافت شد

    if query.data == "option_1":
        await query.edit_message_text("گزینه یک رو انتخاب کردی ✅")
    elif query.data == "option_2":
        await query.edit_message_text("گزینه دو رو انتخاب کردی ✅")
    elif query.data == "about":
        await query.edit_message_text("این یه ربات نمونه‌ست که با پایتون ساخته شده 🤖")


# ---------- پیام‌های معمولی (تکرار پیام) ----------

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"گفتی: {update.message.text}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
