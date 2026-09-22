import os
import io
import json
import logging
from datetime import datetime, timezone

import qrcode
from telegram import (
    Update,
    InputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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
ADMIN_IDS = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

USERS_FILE = "users.json"
SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "welcome_message": "مرحباً 👋\nأرسل لي أي رابط أو نص وسأحوله إلى صورة QR Code فوراً.",
    "force_sub_enabled": False,
    "channel_username": "",  # مثال: @mychannel
    "banned_users": [],
}

COLOR_PALETTE = {
    "⚫ أسود": "#000000",
    "🔴 أحمر": "#E63946",
    "🔵 أزرق": "#1D4ED8",
    "🟢 أخضر": "#16A34A",
    "🟣 بنفسجي": "#7C3AED",
    "🟠 برتقالي": "#EA580C",
    "🌸 وردي": "#DB2777",
    "🟤 بني": "#78350F",
}


# ---------------------------------------------------------------------------
# تخزين (ملفات JSON محلية)
# ---------------------------------------------------------------------------
def load_json(path: str, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_users() -> dict:
    return load_json(USERS_FILE, {})


def save_users(users: dict) -> None:
    save_json(USERS_FILE, users)


def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    settings.update(load_json(SETTINGS_FILE, {}))
    return settings


def save_settings(settings: dict) -> None:
    save_json(SETTINGS_FILE, settings)


def register_user(update: Update) -> dict:
    user = update.effective_user
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "username": user.username or "",
            "first_name": user.first_name or "",
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "color": "#000000",
        }
        save_users(users)
    return users[uid]


def is_banned(user_id: int) -> bool:
    settings = load_settings()
    return user_id in settings.get("banned_users", [])


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------------------------------------------------------------------
# الاشتراك الإجباري
# ---------------------------------------------------------------------------
async def is_subscribed(bot, user_id: int) -> bool:
    settings = load_settings()
    if not settings["force_sub_enabled"] or not settings["channel_username"]:
        return True
    try:
        member = await bot.get_chat_member(settings["channel_username"], user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError as exc:
        logger.warning("Subscription check failed: %s", exc)
        return False


def subscribe_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    channel_link = f"https://t.me/{channel_username.lstrip('@')}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 اشترك بالقناة", url=channel_link)],
            [InlineKeyboardButton("✅ تحققت، تابع", callback_data="check_sub")],
        ]
    )


async def send_subscribe_prompt(update: Update) -> None:
    settings = load_settings()
    await update.message.reply_text(
        "🚫 يجب الاشتراك بالقناة أولاً لاستخدام البوت.\n\n"
        "بعد الاشتراك اضغط زر (تحققت، تابع).",
        reply_markup=subscribe_keyboard(settings["channel_username"]),
    )


# ---------------------------------------------------------------------------
# أوامر المستخدم العادي
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_banned(update.effective_user.id):
        await update.message.reply_text("⛔ تم حظرك من استخدام هذا البوت.")
        return

    register_user(update)

    if not await is_subscribed(context.bot, update.effective_user.id):
        await send_subscribe_prompt(update)
        return

    settings = load_settings()
    await update.message.reply_text(settings["welcome_message"])


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "طريقة الاستخدام:\n\n"
        "• أرسل أي رابط أو نص → أحوله لصورة QR فوراً.\n"
        "• /color → اختر لون الباركود المفضل لك.\n"
        "• /start → رسالة الترحيب.\n"
    )


async def color_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_banned(update.effective_user.id):
        return
    buttons = [
        InlineKeyboardButton(name, callback_data=f"setcolor_{hexcode}")
        for name, hexcode in COLOR_PALETTE.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    await update.message.reply_text(
        "🎨 اختر لون الباركود:",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def color_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    hexcode = query.data.split("_", 1)[1]
    users = load_users()
    uid = str(query.from_user.id)
    if uid not in users:
        register_user(update)
        users = load_users()
    users[uid]["color"] = hexcode
    save_users(users)

    await query.edit_message_text(f"✅ تم ضبط لون الباركود على: {hexcode}")


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if await is_subscribed(context.bot, query.from_user.id):
        await query.edit_message_text("✅ تم التحقق من اشتراكك، تفضل أرسل رابط أو نص.")
    else:
        await query.answer("لسا ما اشتركت بالقناة ❌", show_alert=True)


async def make_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # مسار خاص: لو المشرف بوضع "انتظار إدخال" من لوحة التحكم
    if is_admin(user_id) and context.user_data.get("awaiting"):
        await handle_admin_input(update, context)
        return

    if is_banned(user_id):
        await update.message.reply_text("⛔ تم حظرك من استخدام هذا البوت.")
        return

    register_user(update)

    if not await is_subscribed(context.bot, user_id):
        await send_subscribe_prompt(update)
        return

    text = update.message.text
    if not text or not text.strip():
        await update.message.reply_text("الرجاء إرسال نص أو رابط صالح.")
        return

    try:
        users = load_users()
        color = users.get(str(user_id), {}).get("color", "#000000")

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(text.strip())
        qr.make(fit=True)
        img = qr.make_image(fill_color=color, back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        await update.message.reply_photo(
            photo=InputFile(buffer, filename="qrcode.png"),
            caption="✅ تم إنشاء رمز QR الخاص بك.\nغيّر اللون عبر /color",
        )
    except Exception as exc:
        logger.exception("Failed to generate QR code")
        await update.message.reply_text(f"حدث خطأ أثناء إنشاء الرمز: {exc}")


# ---------------------------------------------------------------------------
# لوحة تحكم المشرف
# ---------------------------------------------------------------------------
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
            return
        return await func(update, context)
    return wrapper


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📖 طريقة استخدام أوامر البوت", callback_data="admin_help")],
            [InlineKeyboardButton("✳️ تغيير رسالة الترحيب", callback_data="admin_welcome")],
            [InlineKeyboardButton("✳️ الاشتراك الإجباري", callback_data="admin_forcesub")],
            [InlineKeyboardButton("✳️ الاحصائيات", callback_data="admin_stats")],
            [InlineKeyboardButton("📢 إذاعة للمشتركين", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🚫 قائمة المحظورين", callback_data="admin_banned")],
            [InlineKeyboardButton("⚙️ إعدادات أخرى", callback_data="admin_settings")],
        ]
    )


@admin_only
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🛠 لوحة تحكم المطوّر:",
        reply_markup=admin_panel_keyboard(),
    )


async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ للمشرفين فقط", show_alert=True)
        return
    await query.answer()

    action = query.data
    settings = load_settings()
    users = load_users()

    if action == "admin_help":
        await query.edit_message_text(
            "📖 أوامر المشرف:\n\n"
            "/admin — فتح لوحة التحكم\n"
            "/stats — الإحصائيات\n"
            "/users — قائمة المستخدمين\n"
            "/ban <ID> — حظر مستخدم\n"
            "/unban <ID> — رفع الحظر\n"
            "/broadcast <رسالة> — إذاعة\n",
            reply_markup=admin_panel_keyboard(),
        )

    elif action == "admin_welcome":
        context.user_data["awaiting"] = "welcome"
        await query.edit_message_text(
            "✍️ أرسل الآن رسالة الترحيب الجديدة (كرسالة نصية عادية).\n\n"
            f"الحالية:\n{settings['welcome_message']}"
        )

    elif action == "admin_forcesub":
        new_state = not settings["force_sub_enabled"]
        settings["force_sub_enabled"] = new_state
        save_settings(settings)
        if new_state and not settings["channel_username"]:
            context.user_data["awaiting"] = "channel"
            await query.edit_message_text(
                "✅ تم تفعيل الاشتراك الإجباري.\n"
                "✍️ الآن أرسل يوزر القناة (مثال: @mychannel)"
            )
        else:
            status = "مُفعّل ✅" if new_state else "مُعطّل ❌"
            await query.edit_message_text(
                f"الاشتراك الإجباري: {status}\nالقناة: {settings['channel_username'] or 'غير محددة'}",
                reply_markup=admin_panel_keyboard(),
            )

    elif action == "admin_stats":
        await query.edit_message_text(
            f"📊 إحصائيات البوت\n\n"
            f"عدد المستخدمين الكلي: {len(users)}\n"
            f"عدد المحظورين: {len(settings['banned_users'])}",
            reply_markup=admin_panel_keyboard(),
        )

    elif action == "admin_broadcast":
        context.user_data["awaiting"] = "broadcast"
        await query.edit_message_text("✍️ أرسل الآن نص الرسالة اللي تبي تذيعها لكل المستخدمين.")

    elif action == "admin_banned":
        banned = settings["banned_users"]
        if not banned:
            text = "لا يوجد محظورون حالياً."
        else:
            text = "🚫 المحظورون:\n" + "\n".join(str(b) for b in banned)
        text += "\n\nاستخدم /ban <ID> أو /unban <ID> للتحكم."
        await query.edit_message_text(text, reply_markup=admin_panel_keyboard())

    elif action == "admin_settings":
        await query.edit_message_text(
            "⚙️ الإعدادات الحالية:\n\n"
            f"الاشتراك الإجباري: {'مُفعّل ✅' if settings['force_sub_enabled'] else 'مُعطّل ❌'}\n"
            f"القناة: {settings['channel_username'] or 'غير محددة'}\n"
            f"عدد المستخدمين: {len(users)}\n"
            f"عدد المحظورين: {len(settings['banned_users'])}",
            reply_markup=admin_panel_keyboard(),
        )


async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    awaiting = context.user_data.pop("awaiting", None)
    text = update.message.text.strip()
    settings = load_settings()

    if awaiting == "welcome":
        settings["welcome_message"] = text
        save_settings(settings)
        await update.message.reply_text("✅ تم تحديث رسالة الترحيب.")

    elif awaiting == "channel":
        settings["channel_username"] = text if text.startswith("@") else f"@{text}"
        save_settings(settings)
        await update.message.reply_text(f"✅ تم ضبط قناة الاشتراك الإجباري: {settings['channel_username']}")

    elif awaiting == "broadcast":
        users = load_users()
        sent, failed = 0, 0
        await update.message.reply_text(f"⏳ جاري الإرسال إلى {len(users)} مستخدم...")
        for uid in users:
            try:
                await context.bot.send_message(chat_id=int(uid), text=text)
                sent += 1
            except TelegramError:
                failed += 1
        await update.message.reply_text(f"✅ تم الإرسال: {sent} | فشل: {failed}")


# ---------------------------------------------------------------------------
# أوامر حظر إضافية
# ---------------------------------------------------------------------------
@admin_only
async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("استخدم: /ban <ID>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("الـ ID لازم يكون رقم صحيح.")
        return

    settings = load_settings()
    if target_id not in settings["banned_users"]:
        settings["banned_users"].append(target_id)
        save_settings(settings)
    await update.message.reply_text(f"⛔ تم حظر المستخدم {target_id}.")


@admin_only
async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("استخدم: /unban <ID>")
        return
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("الـ ID لازم يكون رقم صحيح.")
        return

    settings = load_settings()
    if target_id in settings["banned_users"]:
        settings["banned_users"].remove(target_id)
        save_settings(settings)
    await update.message.reply_text(f"✅ تم رفع الحظر عن {target_id}.")


@admin_only
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    settings = load_settings()
    await update.message.reply_text(
        f"📊 إحصائيات البوت\n\n"
        f"عدد المستخدمين الكلي: {len(users)}\n"
        f"عدد المحظورين: {len(settings['banned_users'])}"
    )


@admin_only
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = load_users()
    if not users:
        await update.message.reply_text("لا يوجد مستخدمون بعد.")
        return

    items = list(users.items())[-30:]
    lines = []
    for uid, info in items:
        uname = f"@{info['username']}" if info.get("username") else "بدون يوزر"
        lines.append(f"• {info.get('first_name', '')} ({uname}) — ID: {uid}")

    text = "👥 آخر المستخدمين:\n\n" + "\n".join(lines)
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
    application.add_handler(CommandHandler("color", color_cmd))
    application.add_handler(CommandHandler("admin", admin_cmd))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("users", users_cmd))
    application.add_handler(CommandHandler("ban", ban_cmd))
    application.add_handler(CommandHandler("unban", unban_cmd))
    application.add_handler(CommandHandler("broadcast", broadcast_cmd))

    application.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    application.add_handler(CallbackQueryHandler(color_callback, pattern="^setcolor_"))
    application.add_handler(CallbackQueryHandler(admin_panel_callback, pattern="^admin_"))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, make_qr)
    )

    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
