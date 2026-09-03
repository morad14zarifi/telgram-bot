"""
ربات تلگرام - نسخه با:
- سیستم "گو گو" (کار در گروه هم می‌کنه): هر ۵ دقیقه یه بار پوینت میده
- هر ۵ بار گو گو گفتن = یک سطح بالاتر
- از سطح ۲: چوب بستنی به عنوان جایزه سطح
- از سطح ۳: باز شدن گمال (که با چوب بستنی تغذیه میشه)
- رتبه‌بندی بر اساس بیشترین گو گو
- کازینو، پشتیبانی، پنل ادمین

⚠️ برای کارکردن تو گروه:
باید تو @BotFather دستور /setprivacy رو بزنی، ربات رو انتخاب کنی، و
گزینه Disable رو بزنی. وگرنه ربات پیام‌های گروه رو (به‌جز دستورها) نمی‌بینه.

⚠️ دیتابیس SQLite کنار خود ربات ذخیره میشه. با هر Deploy جدید روی Railway
ممکنه پاک بشه؛ برای نگهداری دائمی بعداً یه دیتابیس ابری وصل می‌کنیم.
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
CLAIM_INTERVAL = 5 * 60
GOGO_INTERVAL = 5 * 60
START_BALANCE = 1000
STICK_SELL_PRICE = 15
BELLY_MAX = 5
BELLY_PER_STICK = 2

if not BOT_TOKEN:
    raise ValueError("متغیر محیطی BOT_TOKEN تنظیم نشده! باید تو تنظیمات Railway اضافه‌ش کنی.")

DB_PATH = "bot.db"


# ---------- دیتابیس ----------

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
            last_claim INTEGER DEFAULT 0,
            gogo_count INTEGER DEFAULT 0,
            last_gogo INTEGER DEFAULT 0,
            sticks INTEGER DEFAULT 0,
            belly INTEGER DEFAULT 0
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
            "INSERT INTO users (user_id, first_name, username, points) VALUES (?, ?, ?, ?)",
            (user.id, user.first_name, user.username or "", START_BALANCE),
        )
        conn.commit()
    else:
        conn.execute(
            "UPDATE users SET first_name = ?, username = ? WHERE user_id = ?",
            (user.first_name, user.username or "", user.id),
        )
        conn.commit()
    conn.close()


def get_user_row(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def get_points(user_id):
    row = get_user_row(user_id)
    return row["points"] if row else 0


def add_points(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def level_from_count(count):
    return count // 5 + 1


def add_sticks(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET sticks = sticks + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def add_belly(user_id, amount):
    conn = get_db()
    conn.execute(
        "UPDATE users SET belly = MIN(?, belly + ?) WHERE user_id = ?",
        (BELLY_MAX, amount, user_id),
    )
    conn.commit()
    conn.close()


def count_users():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
    conn.close()
    return row["c"]


def top_gogo(limit=10):
    conn = get_db()
    rows = conn.execute(
        "SELECT first_name, gogo_count FROM users ORDER BY gogo_count DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


# ---------- منوها ----------

def main_menu(level):
    rows = [
        [KeyboardButton("💰 موجودی من"), KeyboardButton("🎁 دریافت پوینت")],
        [KeyboardButton("🎰 کازینو"), KeyboardButton("🏆 رتبه‌بندی")],
    ]
    if level >= 2:
        rows.append([KeyboardButton("🍦 چوب بستنی من")])
    if level >= 3:
        rows.append([KeyboardButton("🐶 گمال من")])
    rows.append([KeyboardButton("📩 ارسال پیام به پشتیبانی")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


CASINO_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("🪙 شیر یا خط"), KeyboardButton("🎰 اسلات")], [KeyboardButton("⬅️ بازگشت")]],
    resize_keyboard=True,
)
COIN_CHOICE_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("🪙 شیر"), KeyboardButton("🪙 خط")], [KeyboardButton("⬅️ بازگشت")]],
    resize_keyboard=True,
)
BACK_MENU = ReplyKeyboardMarkup([[KeyboardButton("⬅️ بازگشت")]], resize_keyboard=True)
ADMIN_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("👥 تعداد کاربران")], [KeyboardButton("⬅️ بازگشت")]], resize_keyboard=True
)
STICK_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton("🦴 دادن به گمال"), KeyboardButton("💰 فروختن")], [KeyboardButton("⬅️ بازگشت")]],
    resize_keyboard=True,
)


def format_seconds(sec):
    m, s = divmod(sec, 60)
    return f"{m} دقیقه و {s} ثانیه"


async def go_main(update, context):
    context.user_data["state"] = None
    row = get_user_row(update.effective_user.id)
    level = level_from_count(row["gogo_count"]) if row else 1
    await update.message.reply_text("برگشتی به منو 🏠", reply_markup=main_menu(level))


async def go_casino(update, context):
    context.user_data["state"] = "casino_menu"
    await update.message.reply_text("🎰 یکی از بازی‌ها رو انتخاب کن:", reply_markup=CASINO_MENU)


# ---------- منطق "گو گو" ----------

GOGO_TRIGGERS = {"گو گو", "گوگو"}


async def handle_gogo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user)
    row = get_user_row(user.id)
    now = int(time.time())
    elapsed = now - row["last_gogo"]

    if elapsed < GOGO_INTERVAL:
        remaining = GOGO_INTERVAL - elapsed
        await update.message.reply_text(f"⏳ {user.first_name} باید {format_seconds(remaining)} دیگه صبر کنه.")
        return

    old_level = level_from_count(row["gogo_count"])
    new_count = row["gogo_count"] + 1
    new_level = level_from_count(new_count)

    reward = random.randint(30, 60)

    conn = get_db()
    conn.execute(
        "UPDATE users SET gogo_count = ?, last_gogo = ?, points = points + ? WHERE user_id = ?",
        (new_count, now, reward, user.id),
    )
    conn.commit()
    conn.close()

    msg = f"🐸 گو گو! {user.first_name} +{reward} پوینت گرفت.\nتعداد گو گو: {new_count}"

    if new_level > old_level:
        msg += f"\n\n🎉 تبریک! رفتی سطح {new_level}"
        if new_level >= 2:
            add_sticks(user.id, 1)
            msg += "\n🍦 یک چوب بستنی جایزه گرفتی!"
        if new_level == 3:
            msg += "\n🐶 گمال برات باز شد! از منو می‌تونی بهش سر بزنی."

    await update.message.reply_text(msg)

    # اگه تو چت خصوصیه و منو باز نیست، منو رو به‌روز نشون بده
    if update.effective_chat.type == "private":
        await update.message.reply_text("منو:", reply_markup=main_menu(new_level))


# ---------- دستورها ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    context.user_data["state"] = None
    row = get_user_row(update.effective_user.id)
    level = level_from_count(row["gogo_count"])
    await update.message.reply_text(
        f"سلام {update.effective_user.first_name}! 👋\nبرای گرفتن پوینت هر ۵ دقیقه، بنویس: گو گو\n\nاز منوی پایین هم می‌تونی بقیه امکانات رو ببینی:",
        reply_markup=main_menu(level),
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔️ دسترسی نداری.")
        return
    context.user_data["state"] = "admin_menu"
    await update.message.reply_text("🔧 پنل ادمین:", reply_markup=ADMIN_MENU)


# ---------- مدیریت پیام‌های متنی ----------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    chat_type = update.effective_chat.type
    user = update.effective_user

    # ---- گروه: فقط به "گو گو" واکنش نشون بده ----
    if chat_type in ("group", "supergroup"):
        if text in GOGO_TRIGGERS:
            await handle_gogo(update, context)
        return

    # ---- چت خصوصی از اینجا به بعد ----
    ensure_user(user)
    row = get_user_row(user.id)
    level = level_from_count(row["gogo_count"])
    state = context.user_data.get("state")

    if text in GOGO_TRIGGERS:
        await handle_gogo(update, context)
        return

    if text == "⬅️ بازگشت":
        if state in ("awaiting_coin_bet", "awaiting_coin_choice", "awaiting_slot_bet", "casino_menu"):
            await go_casino(update, context)
        else:
            await go_main(update, context)
        return

    if text == "💰 موجودی من":
        await update.message.reply_text(f"💰 موجودی شما: {get_points(user.id)} پوینت")
        return

    if text == "🎁 دریافت پوینت":
        now = int(time.time())
        elapsed = now - row["last_claim"]
        if elapsed >= CLAIM_INTERVAL:
            reward = random.randint(50, 150)
            add_points(user.id, reward)
            conn = get_db()
            conn.execute("UPDATE users SET last_claim = ? WHERE user_id = ?", (now, user.id))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"🎉 تبریک! {reward} پوینت گرفتی.\nموجودی جدید: {get_points(user.id)}")
        else:
            remaining = CLAIM_INTERVAL - elapsed
            await update.message.reply_text(f"⏳ باید {format_seconds(remaining)} دیگه صبر کنی.")
        return

    if text == "🏆 رتبه‌بندی":
        rows = top_gogo()
        if not rows:
            await update.message.reply_text("هنوز کسی گو گو نگفته!")
            return
        lines = ["🏆 رتبه‌بندی بر اساس گو گو:\n"]
        for i, r in enumerate(rows, start=1):
            lines.append(f"{i}. {r['first_name']} — {r['gogo_count']} بار")
        await update.message.reply_text("\n".join(lines))
        return

    if text == "🎰 کازینو":
        await go_casino(update, context)
        return

    if state == "casino_menu" and text == "🪙 شیر یا خط":
        context.user_data["state"] = "awaiting_coin_bet"
        await update.message.reply_text(f"چقدر شرط می‌بندی؟ (موجودی: {get_points(user.id)})", reply_markup=BACK_MENU)
        return

    if state == "casino_menu" and text == "🎰 اسلات":
        context.user_data["state"] = "awaiting_slot_bet"
        await update.message.reply_text(f"چقدر شرط می‌بندی؟ (موجودی: {get_points(user.id)})", reply_markup=BACK_MENU)
        return

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

    # ---- چوب بستنی ----
    if text == "🍦 چوب بستنی من" and level >= 2:
        context.user_data["state"] = "sticks_menu"
        await update.message.reply_text(
            f"🍦 تعداد چوب بستنی‌های تو: {row['sticks']}\nچیکار می‌خوای بکنی؟",
            reply_markup=STICK_MENU,
        )
        return

    if state == "sticks_menu" and text == "🦴 دادن به گمال":
        if level < 3:
            await update.message.reply_text("گمال هنوز باز نشده! باید سطح ۳ بشی.")
            return
        if row["sticks"] <= 0:
            await update.message.reply_text("چوب بستنی نداری!")
            return
        if row["belly"] >= BELLY_MAX:
            await update.message.reply_text("شکم گمال پره، نیازی به غذا نداره الان.")
            return
        add_sticks(user.id, -1)
        add_belly(user.id, BELLY_PER_STICK)
        new_row = get_user_row(user.id)
        await update.message.reply_text(
            f"🐶 گمال با اشتها خورد! شکمش الان {new_row['belly']} از {BELLY_MAX} پره.\nچوب بستنی باقیمونده: {new_row['sticks']}"
        )
        return

    if state == "sticks_menu" and text == "💰 فروختن":
        if row["sticks"] <= 0:
            await update.message.reply_text("چوب بستنی نداری!")
            return
        add_sticks(user.id, -1)
        add_points(user.id, STICK_SELL_PRICE)
        await update.message.reply_text(f"💰 فروختی و {STICK_SELL_PRICE} پوینت گرفتی.\nموجودی: {get_points(user.id)}")
        return

    # ---- گمال ----
    if text == "🐶 گمال من" and level >= 3:
        await update.message.reply_text(
            f"🐶 گمال تو:\nشکم: {row['belly']} از {BELLY_MAX}\n\nبرای غذا دادن برو به «🍦 چوب بستنی من»."
        )
        return

    # ---- پشتیبانی ----
    if text == "📩 ارسال پیام به پشتیبانی":
        context.user_data["state"] = "awaiting_support_message"
        await update.message.reply_text("پیام، ایراد، باگ یا نظر خود را ارسال نمایید:", reply_markup=BACK_MENU)
        return

    if state == "awaiting_support_message":
        username = user.username or "بدون یوزرنیم"
        forward_text = (
            f"📩 پیام جدید از پشتیبانی\nاز طرف: {user.first_name} (@{username})\nآیدی عددی: {user.id}\n\nمتن پیام:\n{text}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=forward_text)
            await update.message.reply_text("✅ پیام شما ارسال شد. متشکریم!")
        except Exception:
            await update.message.reply_text("مشکلی در ارسال پیام پیش اومد.")
        await go_main(update, context)
        return

    if text == "👥 تعداد کاربران" and user.id == ADMIN_ID:
        await update.message.reply_text(f"تعداد کاربران ربات: {count_users()} نفر")
        return

    await update.message.reply_text("از منوی پایین یکی رو انتخاب کن، یا بنویس: گو گو", reply_markup=main_menu(level))


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
