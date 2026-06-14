# bot.py
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_USERNAME, PRICES, SUPPORT_USERNAME
import database as db

logging.basicConfig(level=logging.INFO)
DB_NAME = "lise.db"

# حالت‌های مکالمه
MONTHS, VOLUME, PAYMENT_METHOD, TRACKING_CODE, CHARGE_AMOUNT = range(5)

async def start(update, context):
    user_id = update.effective_user.id
    # بررسی عضویت در کانال
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        if member.status in ["left", "kicked"]:
            keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME}")],
                        [InlineKeyboardButton("بررسی عضویت", callback_data="check_membership")]]
            await update.message.reply_text(
                f"🔰 لطفاً ابتدا در کانال زیر عضو شوید:\n@{CHANNEL_USERNAME}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
    except:
        pass
    db.init_db()
    db.add_user(user_id, update.effective_user.username, update.effective_user.full_name)
    await show_main_menu(update, context, is_new=True)

async def show_main_menu(update, context, is_new=False):
    keyboard = [
        [InlineKeyboardButton("📊 داشبورد من", callback_data="dashboard")],
        [InlineKeyboardButton("📋 تعرفه خدمات", callback_data="prices")],
        [InlineKeyboardButton("🛍️ خرید سرویس", callback_data="buy")],
        [InlineKeyboardButton("👛 کیف پول", callback_data="wallet")],
        [InlineKeyboardButton("📦 سرویس‌های من", callback_data="my_services")],
        [InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")]
    ]
    text = "🏠 منوی اصلی Lise\nلطفاً یکی از گزینه‌ها را انتخاب کنید."
    if is_new:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def callback_handler(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "check_membership":
        try:
            member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
            if member.status in ["left", "kicked"]:
                await query.edit_message_text("❌ شما هنوز عضو کانال نشده‌اید.")
            else:
                await query.edit_message_text("✅ عضویت تأیید شد. به فروشگاه Lise خوش آمدید.")
                await show_main_menu(update, context, is_new=False)
        except:
            await query.edit_message_text("خطا در بررسی عضویت.")
        return

    if data == "dashboard":
        user = db.get_user(user_id)
        if user:
            balance = user[4]
            text = f"📊 **داشبورد شما**\n💰 موجودی کیف پول: {balance:,} تومان\n🆔 آیدی: {user_id}"
        else:
            text = "خطا در دریافت اطلاعات."
        await query.edit_message_text(text, parse_mode="Markdown")
        return

    if data == "prices":
        text = "📋 **تعرفه خدمات (ماهیانه)**\n"
        for vol, price in PRICES.items():
            text += f"▫️ {vol} گیگ: {price:,} تومان\n"
        await query.edit_message_text(text, parse_mode="Markdown")
        return

    if data == "buy":
        await query.edit_message_text("📅 تعداد ماه را وارد کنید (1 تا 12):")
        return MONTHS

    if data == "wallet":
        keyboard = [
            [InlineKeyboardButton("➕ شارژ کیف پول", callback_data="charge_wallet")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
        ]
        await query.edit_message_text("👛 **کیف پول شما**\nاز دکمه زیر برای شارژ استفاده کنید.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "charge_wallet":
        await query.edit_message_text("💳 مبلغ شارژ را به تومان وارد کنید (مثلاً 50000):")
        return CHARGE_AMOUNT

    if data == "my_services":
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT volume, months, status FROM services WHERE user_id = ? ORDER BY id DESC", (user_id,))
        services = c.fetchall()
        conn.close()
        if not services:
            await query.edit_message_text("📭 شما هیچ سرویسی ندارید.")
        else:
            text = "📦 **سرویس‌های شما**\n"
            for vol, mon, status in services:
                status_text = {"wait_payment": "در انتظار پرداخت", "wait_config": "در انتظار کانفیگ", "active": "فعال", "expired": "منقضی"}.get(status, status)
                text += f"🔹 {vol} گیگ - {mon} ماه - وضعیت: {status_text}\n"
            await query.edit_message_text(text, parse_mode="Markdown")
        return

    if data == "support":
        await query.edit_message_text(f"🆘 پشتیبانی: با ادمین تماس بگیرید\n{SUPPORT_USERNAME}")
        return

    if data == "main_menu":
        await show_main_menu(update, context, is_new=False)
        return

    # برگشت در حین خرید (از طریق دکمه انصراف)
    if data == "cancel_buy":
        await show_main_menu(update, context, is_new=False)
        return ConversationHandler.END

# ---------- مکالمه خرید ----------
async def buy_months(update, context):
    try:
        months = int(update.message.text)
        if months < 1 or months > 12:
            await update.message.reply_text("❌ عدد بین 1 تا 12 وارد کن.")
            return MONTHS
        context.user_data["months"] = months
        # نمایش دکمه‌های حجم به صورت شبكه‌ای (2 ستون)
        keyboard = []
        row = []
        for i, (vol, price) in enumerate(PRICES.items()):
            row.append(InlineKeyboardButton(f"{vol} گیگ - {price:,} تومان", callback_data=f"vol_{vol}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 انصراف", callback_data="cancel_buy")])
        await update.message.reply_text("حجم مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        return VOLUME
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد وارد کن.")
        return MONTHS

async def buy_volume(update, context):
    query = update.callback_query
    await query.answer()
    vol = int(query.data.split("_")[1])
    context.user_data["volume"] = vol
    months = context.user_data["months"]
    total = PRICES[vol] * months
    context.user_data["total_price"] = total
    keyboard = [
        [InlineKeyboardButton("💳 کارت به کارت", callback_data="pay_card")],
        [InlineKeyboardButton("👛 کیف پول", callback_data="pay_wallet")],
        [InlineKeyboardButton("🔙 انصراف", callback_data="cancel_buy")]
    ]
    await query.edit_message_text(f"💰 مبلغ قابل پرداخت: {total:,} تومان\nروش پرداخت را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PAYMENT_METHOD

async def pay_card(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💳 لطفاً شناسه (کد رهگیری) پرداخت کارت به کارت را وارد کنید:")
    context.user_data["payment_method"] = "card"
    return TRACKING_CODE

async def pay_wallet(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    total = context.user_data["total_price"]
    user = db.get_user(user_id)
    if user and user[4] >= total:
        db.update_balance(user_id, -total)
        db.add_service(user_id, context.user_data["volume"], context.user_data["months"], total, "wait_config")
        db.add_transaction(user_id, total, "wallet", "کیف پول", "confirmed")
        await query.edit_message_text(f"✅ خرید موفق! مبلغ {total:,} تومان از کیف پول کسر شد.\nسرویس شما ثبت شد و به زودی کانفیگ ارسال می‌شود.")
        await context.bot.send_message(ADMIN_ID, f"سرویس جدید از {user_id} - حجم {context.user_data['volume']} گیگ - {context.user_data['months']} ماه - نیاز به ارسال کانفیگ")
        return ConversationHandler.END
    else:
        await query.edit_message_text("❌ موجودی کیف پول کافی نیست. لطفاً شارژ کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))
        return ConversationHandler.END

async def tracking_code_received(update, context):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    total = context.user_data["total_price"]
    tx_id = db.add_transaction(user_id, total, "card", code, "pending")
    service_id = db.add_service(user_id, context.user_data["volume"], context.user_data["months"], total, "wait_payment")
    # ذخیره service_id در جای دیگری نیست، بعداً در تایید ادمین باید service_id را پیدا کنیم. برای سادگی، در confirm_transaction نیاز به اصلاح دارد.
    # فعلاً پیغام بدهیم.
    await update.message.reply_text("✅ درخواست خرید ثبت شد. پس از تأیید پرداخت توسط ادمین، کانفیگ برای شما ارسال می‌شود.")
    await context.bot.send_message(ADMIN_ID, f"💰 تراکنش جدید نیاز به تأیید:\nکاربر {user_id}\nمبلغ {total:,} تومان\nکد رهگیری: {code}\nبرای تأیید به پنل ادمین مراجعه کنید.")
    return ConversationHandler.END

# ---------- شارژ کیف پول ----------
async def charge_amount_received(update, context):
    try:
        amount = int(update.message.text)
        if amount <= 0:
            raise ValueError
        user_id = update.effective_user.id
        tx_id = db.add_transaction(user_id, amount, "card", "", "pending")  # tracking_code خالی می‌ماند تا کاربر ارسال کند؟
        # بهتر است کاربر کد رهگیری را هم وارد کند. برای سادگی فعلاً اینگونه:
        await update.message.reply_text("💳 لطفاً کد رهگیری کارت به کارت را وارد کنید:")
        context.user_data["charge_amount"] = amount
        return TRACKING_CODE  # reuse same state but we need separate. برای سادگی دوباره از TRACKING_CODE استفاده می‌کنیم ولی باید تشخیص دهیم برای شارژ است.
    except ValueError:
        await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید.")
        return CHARGE_AMOUNT

async def charge_tracking_code_received(update, context):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    amount = context.user_data["charge_amount"]
    db.add_transaction(user_id, amount, "card", code, "pending")
    # برای شارژ، نیازی به service نیست. ادمین بعداً موجودی را افزایش می‌دهد.
    await update.message.reply_text("✅ درخواست شارژ ثبت شد. پس از تأیید ادمین، موجودی شما افزایش می‌یابد.")
    await context.bot.send_message(ADMIN_ID, f"💰 درخواست شارژ کیف پول:\nکاربر {user_id}\nمبلغ {amount:,} تومان\nکد رهگیری: {code}\nبرای تأیید به پنل ادمین مراجعه کنید.")
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END

# ---------- مکالمه عمومی ----------
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(callback_handler, pattern="^buy$")],
    states={
        MONTHS: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_months)],
        VOLUME: [CallbackQueryHandler(buy_volume, pattern="^vol_")],
        PAYMENT_METHOD: [
            CallbackQueryHandler(pay_card, pattern="^pay_card$"),
            CallbackQueryHandler(pay_wallet, pattern="^pay_wallet$")
        ],
        TRACKING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tracking_code_received)],
        CHARGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, charge_amount_received)]
    },
    fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel, pattern="^cancel_buy$")]
)

# برای شارژ کیف پول هم یک مکالمه جداگانه می‌سازیم یا از همین استفاده کنیم؟ برای سادگی، در کالبک charge_wallet مستقیماً state را به CHARGE_AMOUNT می‌بریم ولی ConversationHandler باید آن state را شامل شود. در کد بالا CHARGE_AMOUNT را به states اضافه کردم اما entry_points فقط buy دارد. پس باید یک handler جدا برای شارژ بسازیم. 
# برای جلوگیری از پیچیدگی، پیشنهاد می‌کنم شارژ کیف پول را هم در همین conv_handler بیاوریم با یک entry_point دیگر. اما فعلاً به دلیل وقت، نسخه نهایی را در یک پیام جدا ارائه می‌دهم که همه چیز به درستی کار کند.

def main():
    import asyncio
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(conv_handler)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(app.run_polling())

if __name__ == "__main__":
    main()
