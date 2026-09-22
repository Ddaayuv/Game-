import os
import io
import json
import logging
from datetime import datetime, timezone

import qrcode
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # مثال: @mychannel
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

USERS_FILE = "users.json"


# ---------------------------------------------------------------------------
# تخزين بسيط للمستخدمين (ملف JSON محلي)
# ---------------------------------------------------------------------------
def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def register_user(update: Update) -> None:
    user = update.effective_user
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "username": user.username or "",
            "first_name": user.first_name or "",
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
        save_users(users)


# ---------------------------------------------------------------------------
# التحقق من الاشتراك الإجباري
# ---------------------------------------------------------------------------
async def is_subscribed(bot, user_id: int) -> bool:
    if not CHANNEL_USERNAME:
        return True  # ما فيه قناة مضبوطة = بدون قيود
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError as exc:
        logger.warning("Subscription check failed: %s", exc)
        return False


def subscribe_keyboard() -> InlineKeyboardMarkup:
    channel_link = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 اشترك بالقناة", url=channel_link)],
            [InlineKeyboardButton("✅ تحققت، تابع", callback_data="check_sub")],
        ]
    )


async def send_subscribe_prompt(update: Update) -> None:
    await update.message.reply_text(
        "🚫 يجب الاشتراك بالقناة أولاً لاستخدام البوت.\n\n"
        "بعد الاشتراك اضغط زر (تحققت، تابع).",
        reply_markup=subscribe_keyboard(),
    )


# ---------------------------------------------------------------------------
# أوامر المستخدم العادي
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update)

    if not await is_subscribed(context.bot, update.effective_user.id):
        await send_subscribe_prompt(update)
        return

    await update.message.reply_text(
        "مرحباً 👋\n"
        "أرسل لي أي رابط أو نص وسأحوله إلى صورة QR Code فوراً."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "طريقة الاستخدام:\n"
        "فقط أرسل رسالة نصية (رابط أو أي نص) وسأرد عليك بصورة QR Code.\n\n"
        "مثال: https://example.com"
    )


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if await is_subscribed(context.bot, query.from_user.id):
        await query.edit_message_text("✅ تم التحقق من اشتراكك، تفضل أرسل رابط أو نص.")
    else:
        await query.answer("لسا ما اشتركت بالقناة ❌", show_alert=True)


async def make_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update)

    if not await is_subscribed(context.bot, update.effective_user.id):
        await send_subscribe_prompt(update)
        return

    text = update.message.text
    if not text or not text.strip():
        await update.message.reply_text("الرجاء إرسال نص أو رابط صالح.")
        return

    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(text.strip())
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        await update.message.reply_photo(
            photo=InputFile(buffer, filename="qrcode.png"),
            caption="✅ تم إنشاء رمز QR الخاص بك.",
        )
    except Exception as exc:
        logger.exception("Failed to generate QR code")
        await update.message.reply_text(f"حدث خطأ أثناء إنشاء الرمز: {exc}")


# ---------------------------------------------------------------------------
# لوحة تحكم المشرف
# ---------------------------------------------------------------------------
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    await update.message.reply_text(
        f"📊 إحصائيات البوت\n\n"
        f"عدد المستخدمين الكلي: {len(users)}"
    )


@admin_only
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    if not users:
        await update.message.reply_text("لا يوجد مستخدمون بعد.")
        return

    # آخر 30 مستخدم مسجل
    items = list(users.items())[-30:]
    lines = []
    for uid, info in items:
        uname = f"@{info['username']}" if info.get("username") else "بدون يوزر"
        lines.append(f"• {info.get('first_name', '')} ({uname}) — ID: {uid}")

    text = "👥 آخر المستخدمين:\n\n" + "\n".join(lines)
    # تقسيم الرسالة إذا كانت طويلة جداً
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i : i + 4000])


@admin_only
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("استخدم: /broadcast <الرسالة>")
        return

    message = " ".join(context.args)
    users = load_users()
    sent, failed = 0, 0

    await update.message.reply_text(f"⏳ جاري الإرسال إلى {len(users)} مستخدم...")

    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=message)
            sent += 1
        except TelegramError:
            failed += 1

    await update.message.reply_text(f"✅ تم الإرسال: {sent} | فشل: {failed}")


# ---------------------------------------------------------------------------
def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set. "
            "Set it before running the bot."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("users", users_cmd))
    application.add_handler(CommandHandler("broadcast", broadcast_cmd))
    application.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, make_qr)
    )

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
