"""
ربات تلگرام - نسخه با منوی پشتیبانی و پنل ادمین
توکن از متغیر محیطی BOT_TOKEN خونده میشه
"""

import logging
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 7287316708  # آیدی عددی ادمین

if not BOT_TOKEN:
    raise ValueError("متغیر محیطی BOT_TOKEN تنظیم نشده! باید تو تنظیمات Railway اضافه‌ش کنی.")

# لیست کاربرانی که با ربات کار کردن (در حافظه - با ری‌استارت سرور پاک میشه)
known_users = set()

# دکمه‌های منوی اصلی
MAIN_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("📩 ارسال پیام به پشتیبانی")]],
    resize_keyboard=True,
)

# دکمه بازگشت (وقتی منتظر پیام کاربر هستیم)
BACK_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("⬅️ بازگشت")]],
    resize_keyboard=True,
)

# منوی پنل ادمین
ADMIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("👥 تعداد کاربران")],
        [KeyboardButton("⬅️ بازگشت")],
    ],
    resize_keyboard=True,
)


# ---------- دستورها ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    known_users.add(update.effective_user.id)
    context.user_data["state"] = None
    await update.message.reply_text(
        "سلام! 👋 خوش اومدی.\nاز منوی پایین یکی رو انتخاب کن:",
        reply_markup=MAIN_MENU,
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ دسترسی نداری.")
        return
    await update.message.reply_text("🔧 پنل ادمین:", reply_markup=ADMIN_MENU)


# ---------- مدیریت پیام‌های متنی (بر اساس دکمه‌ها) ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    known_users.add(user_id)

    state = context.user_data.get("state")

    # دکمه بازگشت
    if text == "⬅️ بازگشت":
        context.user_data["state"] = None
        if user_id == ADMIN_ID:
            await update.message.reply_text("برگشتی به منو.", reply_markup=MAIN_MENU)
        else:
            await update.message.reply_text("برگشتی به منو.", reply_markup=MAIN_MENU)
        return

    # دکمه ارسال پیام به پشتیبانی
    if text == "📩 ارسال پیام به پشتیبانی":
        context.user_data["state"] = "awaiting_support_message"
        await update.message.reply_text(
            "پیام، ایراد، باگ یا نظر خود را ارسال نمایید:",
            reply_markup=BACK_MENU,
        )
        return

    # دکمه تعداد کاربران (فقط ادمین)
    if text == "👥 تعداد کاربران" and user_id == ADMIN_ID:
        await update.message.reply_text(f"تعداد کاربران ربات: {len(known_users)} نفر")
        return

    # اگه کاربر منتظر ارسال پیام پشتیبانیه
    if state == "awaiting_support_message":
        username = update.effective_user.username or "بدون یوزرنیم"
        forward_text = (
            f"📩 پیام جدید از پشتیبانی\n"
            f"از طرف: {update.effective_user.first_name} (@{username})\n"
            f"آیدی عددی: {user_id}\n\n"
            f"متن پیام:\n{text}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=forward_text)
            await update.message.reply_text("✅ پیام شما ارسال شد. متشکریم!", reply_markup=MAIN_MENU)
        except Exception:
            await update.message.reply_text("مشکلی در ارسال پیام پیش اومد.", reply_markup=MAIN_MENU)
        context.user_data["state"] = None
        return

    # پیام عادی که تو هیچ حالتی نیست
    await update.message.reply_text(
        "از منوی پایین یکی رو انتخاب کن، یا /start رو بزن.",
        reply_markup=MAIN_MENU,
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
