# bot.py
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import BOT_TOKEN, ADMIN_ID, CHANNEL_USERNAME, PRICES
import database as db

logging.basicConfig(level=logging.INFO)
DB_NAME = "lise.db"

# حالت‌های مکالمه خرید
MONTHS, VOLUME, PAYMENT_METHOD, TRACKING_CODE = range(4)

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
    # ثبت کاربر
    db.init_db()
    db.add_user(user_id, update.effective_user.username, update.effective_user.full_name)
    # نمایش منوی اصلی
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
        context.user_data["buy_step"] = MONTHS
        await query.edit_message_text("📅 تعداد ماه مورد نظر را وارد کنید (عدد بین 1 تا 12):")
        return ConversationHandler.END  # باید برگردیم به مکالمه

    if data == "wallet":
        keyboard = [
            [InlineKeyboardButton("➕ شارژ کیف پول", callback_data="charge_wallet")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
        ]
        await query.edit_message_text("👛 **کیف پول شما**\nاز دکمه زیر برای شارژ استفاده کنید.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "charge_wallet":
        context.user_data["charge_amount"] = True
        await query.edit_message_text("💳 مبلغ شارژ را به تومان وارد کنید (مثلاً 50000):")
        return

    if data == "my_services":
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT volume, months, status, end_date, config FROM services WHERE user_id = ? ORDER BY id DESC", (user_id,))
        services = c.fetchall()
        conn.close()
        if not services:
            await query.edit_message_text("📭 شما هیچ سرویسی ندارید.")
        else:
            text = "📦 **سرویس‌های شما**\n"
            for vol, mon, status, end, config in services:
                text += f"🔹 {vol} گیگ - {mon} ماه - وضعیت: {status}\n"
            await query.edit_message_text(text, parse_mode="Markdown")
        return

    if data == "support":
        await query.edit_message_text("🆘 پشتیبانی: با ادمین تماس بگیرید\n@admin_username")
        return

    if data == "main_menu":
        await show_main_menu(update, context, is_new=False)
        return

# ---------- مکالمه خرید ----------
async def buy_months(update, context):
    try:
        months = int(update.message.text)
        if months < 1 or months > 12:
            await update.message.reply_text("❌ عدد باید بین 1 تا 12 باشد. دوباره وارد کن:")
            return MONTHS
        context.user_data["months"] = months
        context.user_data["buy_step"] = VOLUME
        # نمایش دکمه‌های حجم
        keyboard = [[InlineKeyboardButton(f"{vol} گیگ - {price:,} تومان", callback_data=f"vol_{vol}")] for vol, price in PRICES.items()]
        keyboard.append([InlineKeyboardButton("🔙 انصراف", callback_data="main_menu")])
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
    context.user_data["buy_step"] = PAYMENT_METHOD
    keyboard = [
        [InlineKeyboardButton("💳 کارت به کارت", callback_data="pay_card")],
        [InlineKeyboardButton("👛 کیف پول", callback_data="pay_wallet")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
    ]
    await query.edit_message_text(f"💰 مبلغ قابل پرداخت: {total:,} تومان\nروش پرداخت را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PAYMENT_METHOD

async def pay_card(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💳 لطفاً شناسه (کد رهگیری) پرداخت کارت به کارت را وارد کنید:")
    context.user_data["buy_step"] = TRACKING_CODE
    return TRACKING_CODE

async def pay_wallet(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    total = context.user_data["total_price"]
    user = db.get_user(user_id)
    if user and user[4] >= total:
        db.update_balance(user_id, -total)
        service_id = db.add_service(user_id, context.user_data["volume"], context.user_data["months"], total, "wait_config")
        db.add_transaction(user_id, total, "wallet", "کیف پول", "confirmed")
        await query.edit_message_text(f"✅ خرید موفق! مبلغ {total:,} تومان از کیف پول کسر شد.\nسرویس شما ثبت شد و به زودی کانفیگ ارسال می‌شود.")
        # اطلاع به ادمین
        await context.bot.send_message(ADMIN_ID, f"سرویس جدید از {user_id} - حجم {context.user_data['volume']} گیگ - {context.user_data['months']} ماه - نیاز به ارسال کانفیگ")
        return ConversationHandler.END
    else:
        await query.edit_message_text("❌ موجودی کیف پول کافی نیست. لطفاً شارژ کنید.")
        return ConversationHandler.END

async def tracking_code_received(update, context):
    code = update.message.text.strip()
    user_id = update.effective_user.id
    total = context.user_data["total_price"]
    db.add_transaction(user_id, total, "card", code, "pending")
    db.add_service(user_id, context.user_data["volume"], context.user_data["months"], total, "wait_payment")
    await update.message.reply_text("✅ درخواست خرید ثبت شد. پس از تأیید پرداخت توسط ادمین، کانفیگ برای شما ارسال می‌شود.")
    # اطلاع به ادمین
    await context.bot.send_message(ADMIN_ID, f"💰 تراکنش جدید نیاز به تأیید:\nکاربر {user_id}\nمبلغ {total:,} تومان\nکد رهگیری: {code}\nبرای تأیید به پنل ادمین مراجعه کنید.")
    return ConversationHandler.END

async def cancel(update, context):
    await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END

def main():
    import asyncio
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(conv_handler)
    # اجرای صحیح با asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(app.run_polling())

if __name__ == "__main__":
    main()
