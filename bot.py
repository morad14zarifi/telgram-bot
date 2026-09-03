"""
ربات تلگرام - نسخه با کازینو، پوینت هر ۵ دقیقه، پشتیبانی و پنل ادمین
توکن از متغیر محیطی BOT_TOKEN خونده میشه

نکته: دیتابیس SQLite تو همین سرور ذخیره میشه. اگه Railway سرویس رو
از نو دیپلوی کنه (نه فقط ری‌استارت)، ممکنه این فایل پاک بشه.
برای نگهداری دائمی داده‌ها بعداً می‌تونیم یه دیتابیس ابری وصل کنیم.
"""

import logging
import os
import random
import sqlite3
import time
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
ADMIN_ID = 7287316708
CLAIM_INTERVAL = 5 * 60  # ۵ دقیقه به ثانیه
START_BALANCE = 1000

if not BOT_TOKEN:
    raise ValueError("متغیر محیطی BOT_TOKEN تنظیم نشده! باید تو تنظیمات Railway اضافه‌ش کنی.")

# ---------- دیتابیس ----------

DB_PATH = "bot.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            points INTEGER DEFAULT 1000,
            last_claim INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_user(user):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user.id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (user_id, first_name, username, points, last_claim) VALUES (?, ?, ?, ?, 0)",
            (user.id, user.first_name, user.username or "", START_BALANCE),
        )
        conn.commit()
    conn.close()


def get_points(user_id):
    conn = get_db()
    row = conn.execute("SELECT points FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["points"] if row else 0


def add_points(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def get_last_claim(user_id):
    conn = get_db()
    row = conn.execute("SELECT last_claim FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["last_claim"] if row else 0


def set_last_claim(user_id, ts):
    conn = get_db()
    conn.execute("UPDATE users SET last_claim = ? WHERE user_id = ?", (ts, user_id))
    conn.commit()
    conn.close()


def count_users():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
    conn.close()
    return row["c"]


# ---------- منوها ----------

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("💰 موجودی من"), KeyboardButton("🎁 دریافت پوینت")],
        [KeyboardButton("🎰 کازینو")],
        [KeyboardButton("📩 ارسال پیام به پشتیبانی")],
    ],
    resize_keyboard=True,
)

CASINO_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🪙 شیر یا خط"), KeyboardButton("🎰 اسلات")],
        [KeyboardButton("⬅️ بازگشت")],
    ],
    resize_keyboard=True,
)

COIN_CHOICE_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🪙 شیر"), KeyboardButton("🪙 خط")],
        [KeyboardButton("⬅️ بازگشت")],
    ],
    resize_keyboard=True,
)

BACK_MENU = ReplyKeyboardMarkup([[KeyboardButton("⬅️ بازگشت")]], resize_keyboard=True)

ADMIN_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("👥 تعداد کاربران")], [KeyboardButton("⬅️ بازگشت")]],
    resize_keyboard=True,
)


# ---------- دستورها ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    context.user_data["state"] = None
    await update.message.reply_text(
        f"سلام {update.effective_user.first_name}! 👋\nاز منوی پایین یکی رو انتخاب کن:",
        reply_markup=MAIN_MENU,
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ دسترسی نداری.")
        return
    context.user_data["state"] = "admin_menu"
    await update.message.reply_text("🔧 پنل ادمین:", reply_markup=ADMIN_MENU)


# ---------- توابع کمکی ----------

def format_seconds(sec):
    m, s = divmod(sec, 60)
    return f"{m} دقیقه و {s} ثانیه"


async def go_main(update, context):
    context.user_data["state"] = None
    await update.message.reply_text("برگشتی به منو 🏠", reply_markup=MAIN_MENU)


async def go_casino(update, context):
    context.user_data["state"] = "casino_menu"
    await update.message.reply_text("🎰 یکی از بازی‌ها رو انتخاب کن:", reply_markup=CASINO_MENU)


# ---------- مدیریت پیام‌های متنی ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    ensure_user(user)
    state = context.user_data.get("state")

    # ---- بازگشت ----
    if text == "⬅️ بازگشت":
        if state in ("awaiting_coin_bet", "awaiting_coin_choice", "awaiting_slot_bet", "casino_menu"):
            await go_casino(update, context)
        else:
            await go_main(update, context)
        return

    # ---- موجودی ----
    if text == "💰 موجودی من":
        await update.message.reply_text(f"💰 موجودی شما: {get_points(user.id)} پوینت")
        return

    # ---- دریافت پوینت هر ۵ دقیقه ----
    if text == "🎁 دریافت پوینت":
        now = int(time.time())
        last = get_last_claim(user.id)
        elapsed = now - last
        if elapsed >= CLAIM_INTERVAL:
            reward = random.randint(50, 150)
            add_points(user.id, reward)
            set_last_claim(user.id, now)
            await update.message.reply_text(
                f"🎉 تبریک! {reward} پوینت گرفتی.\nموجودی جدید: {get_points(user.id)}"
            )
        else:
            remaining = CLAIM_INTERVAL - elapsed
            await update.message.reply_text(f"⏳ باید {format_seconds(remaining)} دیگه صبر کنی.")
        return

    # ---- ورود به کازینو ----
    if text == "🎰 کازینو":
        await go_casino(update, context)
        return

    # ---- انتخاب بازی شیر یا خط ----
    if state == "casino_menu" and text == "🪙 شیر یا خط":
        context.user_data["state"] = "awaiting_coin_bet"
        await update.message.reply_text(
            f"چقدر شرط می‌بندی؟ (موجودی: {get_points(user.id)})\nعدد رو بنویس:",
            reply_markup=BACK_MENU,
        )
        return

    # ---- انتخاب بازی اسلات ----
    if state == "casino_menu" and text == "🎰 اسلات":
        context.user_data["state"] = "awaiting_slot_bet"
        await update.message.reply_text(
            f"چقدر شرط می‌بندی؟ (موجودی: {get_points(user.id)})\nعدد رو بنویس:",
            reply_markup=BACK_MENU,
        )
        return

    # ---- گرفتن مبلغ شرط شیر یا خط ----
    if state == "awaiting_coin_bet":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("لطفاً یه عدد معتبر بنویس.")
            return
        bet = int(text)
        if bet > get_points(user.id):
            await update.message.reply_text("موجودی کافی نداری!")
            return
        context.user_data["bet"] = bet
        context.user_data["state"] = "awaiting_coin_choice"
        await update.message.reply_text("شیر یا خط؟ 🪙", reply_markup=COIN_CHOICE_MENU)
        return

    # ---- انتخاب شیر/خط و نتیجه ----
    if state == "awaiting_coin_choice" and text in ("🪙 شیر", "🪙 خط"):
        bet = context.user_data.get("bet", 0)
        user_choice = "شیر" if text == "🪙 شیر" else "خط"
        result = random.choice(["شیر", "خط"])
        if user_choice == result:
            add_points(user.id, bet)
            msg = f"🪙 نتیجه: {result}\n✅ بردی! {bet} پوینت گرفتی.\nموجودی: {get_points(user.id)}"
        else:
            add_points(user.id, -bet)
            msg = f"🪙 نتیجه: {result}\n❌ باختی! {bet} پوینت از دست دادی.\nموجودی: {get_points(user.id)}"
        await update.message.reply_text(msg)
        await go_casino(update, context)
        return

    # ---- گرفتن مبلغ شرط اسلات و نتیجه ----
    if state == "awaiting_slot_bet":
        if not text.isdigit() or int(text) <= 0:
            await update.message.reply_text("لطفاً یه عدد معتبر بنویس.")
            return
        bet = int(text)
        if bet > get_points(user.id):
            await update.message.reply_text("موجودی کافی نداری!")
            return

        symbols = ["🍒", "🍋", "🔔", "⭐️", "💎"]
        reels = [random.choice(symbols) for _ in range(3)]
        result_text = " | ".join(reels)

        if reels[0] == reels[1] == reels[2]:
            win = bet * 5
            add_points(user.id, win)
            msg = f"🎰 {result_text}\n🎉 برد بزرگ! {win} پوینت گرفتی.\nموجودی: {get_points(user.id)}"
        elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
            win = bet * 2
            add_points(user.id, win)
            msg = f"🎰 {result_text}\n✅ بردی! {win} پوینت گرفتی.\nموجودی: {get_points(user.id)}"
        else:
            add_points(user.id, -bet)
            msg = f"🎰 {result_text}\n❌ باختی! {bet} پوینت از دست دادی.\nموجودی: {get_points(user.id)}"

        await update.message.reply_text(msg)
        await go_casino(update, context)
        return

    # ---- پشتیبانی ----
    if text == "📩 ارسال پیام به پشتیبانی":
        context.user_data["state"] = "awaiting_support_message"
        await update.message.reply_text(
            "پیام، ایراد، باگ یا نظر خود را ارسال نمایید:",
            reply_markup=BACK_MENU,
        )
        return

    if state == "awaiting_support_message":
        username = user.username or "بدون یوزرنیم"
        forward_text = (
            f"📩 پیام جدید از پشتیبانی\n"
            f"از طرف: {user.first_name} (@{username})\n"
            f"آیدی عددی: {user.id}\n\n"
            f"متن پیام:\n{text}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=forward_text)
            await update.message.reply_text("✅ پیام شما ارسال شد. متشکریم!")
        except Exception:
            await update.message.reply_text("مشکلی در ارسال پیام پیش اومد.")
        await go_main(update, context)
        return

    # ---- پنل ادمین: تعداد کاربران ----
    if text == "👥 تعداد کاربران" and user.id == ADMIN_ID:
        await update.message.reply_text(f"تعداد کاربران ربات: {count_users()} نفر")
        return

    # ---- حالت پیش‌فرض ----
    await update.message.reply_text("از منوی پایین یکی رو انتخاب کن، یا /start رو بزن.", reply_markup=MAIN_MENU)


def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
