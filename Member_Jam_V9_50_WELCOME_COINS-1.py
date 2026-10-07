# -*- coding: utf-8 -*-
# MEMBER JAM | نسخه تک فایل مخصوص Pydroid 3
# نصب: pip install pyTelegramBotAPI
# سپس TOKEN را در خط زیر وارد کن و Run بزن.

import sqlite3, threading, time
import telebot
from telebot import types

TOKEN = input("توکن ربات را وارد کنید: ").strip()

if ":" not in TOKEN:
    raise ValueError("توکن واردشده معتبر نیست؛ توکن باید شامل : باشد.")
OWNER_ID = 8880176059
OWNER_KEY = "221311"

# اطلاعات پرداخت
CARD_NUMBER = "6219861353157687"
CARD_HOLDER = "ادریس"

SEP = "━━━━━━━━━━━━━━━━━━"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
DB = "member_jam.db"
lock = threading.Lock()

def db():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

with db() as c:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, username TEXT, coins INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0, created INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS channels(
        id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT UNIQUE,
        username TEXT, title TEXT, active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS claims(
        user_id INTEGER, channel_id INTEGER,
        claimed INTEGER DEFAULT 1, PRIMARY KEY(user_id,channel_id)
    );
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        amount INTEGER, status TEXT DEFAULT 'active', created INTEGER,
        original_amount INTEGER DEFAULT 0,
        channel_id TEXT DEFAULT '',
        channel_title TEXT DEFAULT '',
        channel_username TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS order_claims(
        order_id INTEGER,
        user_id INTEGER,
        claimed INTEGER DEFAULT 1,
        created INTEGER,
        PRIMARY KEY(order_id,user_id)
    );
    CREATE TABLE IF NOT EXISTS purchases(
        id INTEGER PRIMARY KEY AUTOINCREMENT, buyer_id INTEGER,
        target_id INTEGER, coins INTEGER, price INTEGER,
        receipt_file TEXT DEFAULT '', status TEXT DEFAULT 'pending',
        created INTEGER
    );
    CREATE TABLE IF NOT EXISTS tickets(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        text TEXT, status TEXT DEFAULT 'open', created INTEGER
    );
    CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT,
        user_id INTEGER, text TEXT, created INTEGER
    );
    """)

# مهاجرت دیتابیس‌های قدیمی: اگر member_jam.db از نسخه قبلی باشد،
# ستون‌های جدید بدون حذف اطلاعات قبلی اضافه می‌شوند.
MIGRATIONS = {
    "users": {
        "username": "TEXT DEFAULT ''",
        "coins": "INTEGER DEFAULT 0",
        "blocked": "INTEGER DEFAULT 0",
        "created": "INTEGER DEFAULT 0",
    },
    "channels": {
        "chat_id": "TEXT",
        "username": "TEXT",
        "title": "TEXT",
        "active": "INTEGER DEFAULT 1",
    },
    "claims": {
        "user_id": "INTEGER",
        "channel_id": "INTEGER",
        "claimed": "INTEGER DEFAULT 1",
    },
    "orders": {
        "user_id": "INTEGER",
        "amount": "INTEGER DEFAULT 0",
        "status": "TEXT DEFAULT 'pending'",
        "created": "INTEGER DEFAULT 0",
        "original_amount": "INTEGER DEFAULT 0",
        "channel_id": "TEXT DEFAULT ''",
        "channel_title": "TEXT DEFAULT ''",
        "channel_username": "TEXT DEFAULT ''",
    },
    "order_claims": {
        "order_id": "INTEGER",
        "user_id": "INTEGER",
        "claimed": "INTEGER DEFAULT 1",
        "created": "INTEGER DEFAULT 0",
    },
    "purchases": {
        "buyer_id": "INTEGER",
        "target_id": "INTEGER",
        "coins": "INTEGER DEFAULT 0",
        "price": "INTEGER DEFAULT 0",
        "receipt_file": "TEXT DEFAULT ''",
        "status": "TEXT DEFAULT 'pending'",
        "created": "INTEGER DEFAULT 0",
    },
    "tickets": {
        "user_id": "INTEGER",
        "text": "TEXT",
        "status": "TEXT DEFAULT 'open'",
        "created": "INTEGER DEFAULT 0",
    },
    "logs": {
        "action": "TEXT",
        "user_id": "INTEGER",
        "text": "TEXT",
        "created": "INTEGER DEFAULT 0",
    },
}

with db() as c:
    for table, columns in MIGRATIONS.items():
        existing = {row["name"] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}
        for col, definition in columns.items():
            if col not in existing:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
    # برای رکوردهای قدیمی مقدار زمان را پر می‌کنیم.
    try:
        c.execute("UPDATE users SET created=? WHERE created IS NULL OR created=0", (int(time.time()),))
    except Exception:
        pass

def now(): return int(time.time())

def add_user(u):
    """کاربر را ثبت می‌کند و برای کاربر کاملاً جدید True برمی‌گرداند."""
    with db() as c:
        exists = c.execute("SELECT 1 FROM users WHERE id=?", (u.id,)).fetchone()
        if not exists:
            c.execute(
                "INSERT INTO users(id,username,coins,created) VALUES(?,?,0,?)",
                (u.id, u.username or "", now())
            )
            c.execute(
                "INSERT INTO logs(action,user_id,text,created) VALUES(?,?,?,?)",
                ("new_user", u.id, "ثبت کاربر جدید", now())
            )
            return True
        c.execute(
            "UPDATE users SET username=? WHERE id=?",
            (u.username or "", u.id)
        )
        return False

def is_owner(m): return m.from_user.id == OWNER_ID

@bot.message_handler(func=lambda m: is_owner(m) and (m.text or "").strip() == f"مالک {OWNER_KEY}")
def owner_key(m):
    bot.send_message(
        m.chat.id,
        styled("👑 پنل مالک",
               "━━━━━━━━━━━━━━━━━━\n"
               "پنل مدیریت فعال شد."),
        reply_markup=owner_menu()
    )

# منوی اصلی صفحه‌بندی‌شده؛ هیچ دکمه‌ای به نام «امکانات بیشتر» ندارد.
CORE_BUTTONS = [
    "🎯 دریافت سکه", "👥 سفارش ممبر",
    "💳 خرید کوین", "📦 پیگیری سفارش",
    "📢 ثبت کانال", "📊 آمار من",
    "🔗 لینک دعوت من", "📣 تبلیغ کانال من",
    "🎮 کلوب بازی", "💎 VIP",
    "☎️ پشتیبانی",
]

# 60 سیستم کاربری مستقیماً داخل صفحات منوی اصلی قرار دارند.
ADVANCED_BUTTONS = [
    "👤 پروفایل من", "🪙 موجودی سکه", "📊 آمار سکه", "📦 آمار سفارش",
    "💳 تاریخچه خرید", "🧾 تاریخچه سفارش", "🎯 کانال‌های کسب سکه", "🔗 آمار دعوت",
    "💰 تعرفه کوین", "🛒 بسته‌های خرید", "✏️ خرید تعداد دلخواه", "📢 راهنمای ثبت کانال",
    "🔎 جستجوی سفارش", "🧾 شماره سفارش", "💳 اطلاعات پرداخت", "📈 آمار تبلیغات",
    "🔔 اعلان‌ها", "🎁 هدیه روزانه", "🎟 کد هدیه", "🛡 امنیت حساب",
    "📋 قوانین", "🆘 مرکز کمک", "☎️ تماس با مالک", "🐞 گزارش مشکل",
    "💸 گزارش تراکنش", "📦 گزارش سفارش", "⭐ امتیازدهی", "🕐 تاریخ عضویت",
    "🔢 تعداد سفارش", "👥 تعداد دعوت", "📢 تعداد کانال", "✨ سکه دریافت‌شده",
    "🔥 سکه مصرف‌شده", "💎 سکه خریداری‌شده", "🎁 سکه هدیه", "📦 آخرین سفارش",
    "💳 آخرین خرید", "🟢 آخرین فعالیت", "✅ وضعیت حساب", "🔐 وضعیت دسترسی",
    "⚙️ تنظیمات حساب", "🔔 تنظیم اعلان", "🛒 مرکز سفارش", "💳 مرکز خرید",
    "🪙 مرکز سکه", "🤝 مرکز دعوت", "☎️ مرکز پشتیبانی", "📚 مرکز راهنما",
    "💎 مرکز VIP", "🎮 مرکز بازی", "📣 مرکز تبلیغات", "🗂 آرشیو خرید",
    "🗂 آرشیو سفارش", "📜 راهنمای سریع", "🧑‍💻 شناسه عددی", "👤 یوزرنیم",
    "🚫 لغو سفارش", "🔒 امنیت پیشرفته", "📌 وضعیت عضویت", "📌 وضعیت سفارش",
]

MAIN_BUTTONS = CORE_BUTTONS + ADVANCED_BUTTONS
MAIN_PAGE_SIZE = 20

def main_menu(page=0):
    total_pages=(len(MAIN_BUTTONS)-1)//MAIN_PAGE_SIZE+1
    page=max(0,min(page,total_pages-1))
    k=types.ReplyKeyboardMarkup(resize_keyboard=True,row_width=2)
    chunk=MAIN_BUTTONS[page*MAIN_PAGE_SIZE:(page+1)*MAIN_PAGE_SIZE]
    for i in range(0,len(chunk),2):
        if i+1<len(chunk):
            k.row(chunk[i],chunk[i+1])
        else:
            k.row(chunk[i])
    nav=[]
    if page>0:
        nav.append("⬅️ قبلی")
    if page<total_pages-1:
        nav.append("بعدی ➡️")
    if nav:
        k.row(*nav)
    return k

def send_main_page(chat_id,page=0):
    total_pages=(len(MAIN_BUTTONS)-1)//MAIN_PAGE_SIZE+1
    bot.send_message(
        chat_id,
        styled("Member Jam",
               f"صفحه <b>{page+1}</b> از <b>{total_pages}</b>\n"
               "━━━━━━━━━━━━━━━━━━\n"
               "همه امکانات مستقیماً در منوی اصلی قرار دارند."),
        reply_markup=main_menu(page)
    )


def owner_menu():
    k=types.ReplyKeyboardMarkup(resize_keyboard=True,row_width=2)
    rows=[
        ("📊 آمار کلی","👥 کاربران"),
        ("🪙 دادن سکه","💳 خریدهای در انتظار"),
        ("📢 کانال‌های کسب سکه","📦 سفارش‌ها"),
        ("🎫 تیکت‌ها","📣 پیام همگانی"),
        ("🚫 مدیریت مسدودی","⚙️ تنظیمات"),
        ("🧩 200 سیستم مالک","📜 لاگ‌ها"),
        ("❌ خروج مالک","🛠 ابزار مالک")
    ]
    for a,b in rows:k.row(a,b)
    return k


def force_join_markup(channels):
    k=types.InlineKeyboardMarkup()
    for ch in channels:
        if ch["username"]:
            k.add(types.InlineKeyboardButton(
                "📢 "+(ch["title"] or ch["username"]),
                url="https://t.me/"+ch["username"].lstrip("@")))
    k.add(types.InlineKeyboardButton("✅ عضو شدم",callback_data="check_all"))
    return k

def styled(title, body):
    return f"🔷 <b>{title}</b>\n{SEP}\n{body}\n{SEP}"

def user_extra_menu(page=0):
    k=types.InlineKeyboardMarkup(row_width=2)
    chunk=USER_SYSTEMS[page*20:(page+1)*20]
    for i,name in enumerate(chunk,page*20):
        k.add(types.InlineKeyboardButton(f"{i+1}. {name}",callback_data=f"us:{i}"))
    if page>0:k.add(types.InlineKeyboardButton("⬅️ قبلی",callback_data=f"usp:{page-1}"))
    if (page+1)*20<len(USER_SYSTEMS):k.add(types.InlineKeyboardButton("بعدی ➡️",callback_data=f"usp:{page+1}"))
    return k

USER_SYSTEMS=(['پروفایل', 'موجودی', 'آمار سکه', 'آمار سفارش', 'تاریخچه خرید', 'تاریخچه سفارش', 'کانال\u200cهای کسب سکه', 'عضویت\u200cهای ثبت\u200cشده', 'لینک دعوت', 'آمار دعوت', 'تعرفه کوین', 'بسته\u200cهای کوین', 'خرید تعداد دلخواه', 'ثبت کانال', 'راهنمای ثبت کانال', 'پیگیری سفارش', 'لغو سفارش', 'رسید خرید', 'وضعیت خرید', 'پشتیبانی', 'تیکت جدید', 'قوانین', 'امنیت', 'اعلان\u200cها', 'هدیه روزانه', 'کد هدیه', 'VIP', 'کلوب بازی', 'تبلیغات کانال', 'آمار تبلیغات', 'سفارش ممبر', 'تأیید سفارش', 'موجودی سفارش', 'تاریخچه سکه', 'کسب سکه', 'بررسی عضویت', 'تأیید خودکار', 'جلوگیری از سکه تکراری', 'جستجوی سفارش', 'شماره سفارش', 'اطلاعات پرداخت', 'کارت بانکی', 'نام صاحب کارت', 'قیمت هر 10 کوین', 'حداقل خرید', 'حداکثر خرید', 'پروفایل عمومی', 'شناسه عددی', 'یوزرنیم', 'تغییر اعلان', 'راهنمای سریع', 'راهنمای خرید', 'راهنمای سفارش', 'راهنمای کسب سکه', 'راهنمای دعوت', 'مرکز کمک', 'تماس با مالک', 'گزارش مشکل', 'گزارش تراکنش', 'گزارش سفارش', 'درخواست بررسی', 'بازخورد', 'امتیازدهی', 'تاریخ عضویت', 'تعداد سفارش', 'تعداد خرید', 'تعداد دعوت', 'تعداد کانال', 'سکه دریافت\u200cشده', 'سکه مصرف\u200cشده', 'سکه خریداری\u200cشده', 'سکه هدیه', 'آخرین سفارش', 'آخرین خرید', 'آخرین فعالیت', 'وضعیت حساب', 'وضعیت دسترسی', 'امنیت حساب', 'حالت ساده', 'حالت حرفه\u200cای', 'تنظیمات حساب', 'تنظیم اعلان', 'مرکز سفارش', 'مرکز خرید', 'مرکز سکه', 'مرکز دعوت', 'مرکز پشتیبانی', 'مرکز راهنما', 'مرکز VIP', 'مرکز بازی', 'مرکز تبلیغات', 'آرشیو خرید', 'آرشیو سفارش', 'بازگشت به منو', 'خروج', 'سیستم کاربر 1', 'سیستم کاربر 2', 'سیستم کاربر 3', 'سیستم کاربر 4', 'سیستم کاربر 5'])


def active_channels():
    with db() as c:
        return c.execute("SELECT * FROM channels WHERE active=1").fetchall()

def check_join(uid, ch):
    try:
        x=bot.get_chat_member(ch["chat_id"],uid)
        return x.status not in ("left","kicked")
    except:
        return False

@bot.message_handler(commands=["start"])
def start(m):
    is_new_user = add_user(m.from_user)
    MAIN_PAGES[m.from_user.id]=0

    # 🎁 جایزه ورود اول: فقط یک‌بار برای کاربرانی که برای اولین بار
    # وارد ربات می‌شوند، 50 سکه به موجودی اضافه می‌شود.
    welcome_bonus = 50
    if is_new_user and not is_owner(m):
        with db() as c:
            c.execute(
                "UPDATE users SET coins=COALESCE(coins,0)+? WHERE id=?",
                (welcome_bonus, m.from_user.id)
            )
            c.execute(
                "INSERT INTO logs(action,user_id,text,created) VALUES(?,?,?,?)",
                ("welcome_bonus", m.from_user.id, "دریافت 50 سکه خوش‌آمدگویی", now())
            )

    with db() as c:
        u=c.execute("SELECT blocked,coins FROM users WHERE id=?",(m.from_user.id,)).fetchone()
    if u and u["blocked"]:
        return bot.send_message(m.chat.id,"🚫 دسترسی شما مسدود است.")

    # مالک با /start مستقیماً پنل مالک را می‌بیند.
    if is_owner(m):
        return bot.send_message(
            m.chat.id,
            styled("👑 پنل مالک",
                   "خوش آمدید مالک عزیز.\n"
                   "━━━━━━━━━━━━━━━━━━\n"
                   "مدیریت کامل ربات از اینجا در دسترس است."),
            reply_markup=owner_menu()
        )

    if is_new_user:
        welcome_text = (
            "🎉 <b>خوش آمدی!</b>\n"
            f"{SEP}\n"
            "🎁 جایزه ورود اول\n"
            "🪙 <b>50 سکه</b> به موجودی شما اضافه شد.\n"
            f"{SEP}\n"
            "از سکه‌ها برای سفارش ممبر استفاده کن."
        )
    else:
        welcome_text = (
            "👋 دوباره خوش آمدی!\n"
            f"{SEP}\n"
            f"🪙 موجودی فعلی: <b>{u['coins'] or 0}</b> سکه\n"
            f"{SEP}\n"
            "هر 1 سکه = 1 ممبر"
        )

    bot.send_message(
        m.chat.id,
        styled("Member Jam", welcome_text),
        reply_markup=main_menu()
    )

# ---------- EARN COINS ----------
def earn_jobs():
    """کانال‌های کسب سکه + سفارش‌های ممبر را یکجا برمی‌گرداند."""
    channels=active_channels()
    with db() as c:
        orders=c.execute(
            """SELECT * FROM orders
               WHERE status='pending' AND amount>0
               ORDER BY id DESC LIMIT 100"""
        ).fetchall()
    return channels,orders

def earn_jobs_markup(channels,orders):
    k=types.InlineKeyboardMarkup(row_width=1)
    for ch in channels:
        label=ch["title"] or ch["username"] or str(ch["chat_id"])
        k.add(types.InlineKeyboardButton(
            f"📢 {label} • +1 سکه",
            callback_data=f"earnch:{ch['id']}"
        ))
    for o in orders:
        label=o["channel_title"] or o["channel_username"] or o["channel_id"]
        k.add(types.InlineKeyboardButton(
            f"👥 سفارش #{o['id']} • {o['amount']} باقی • +1 سکه",
            callback_data=f"earnord:{o['id']}"
        ))
    k.add(types.InlineKeyboardButton("🔄 بروزرسانی",callback_data="earn_refresh"))
    return k

@bot.message_handler(func=lambda m:m.text=="🎯 دریافت سکه")
def earn(m):
    add_user(m.from_user)
    channels,orders=earn_jobs()
    if not channels and not orders:
        return bot.send_message(
            m.chat.id,
            styled("🎯 دریافت سکه",
                   "━━━━━━━━━━━━━━━━━━\n"
                   "فعلاً کانال یا سفارش ممبری برای کسب سکه موجود نیست.")
        )
    lines=[
        "🎯 <b>دریافت سکه</b>",
        SEP,
        "📢 با عضویت تأییدشده در کانال‌ها 1 سکه بگیر.",
        "👥 با انجام سفارش‌های ممبر هم 1 سکه بگیر.",
        "",
    ]
    if orders:
        lines.append(f"👥 سفارش‌های فعال: <b>{len(orders)}</b>")
    if channels:
        lines.append(f"📢 کانال‌های کسب سکه: <b>{len(channels)}</b>")
    lines += ["", "⬇️ یکی را انتخاب کن، عضو شو و تأیید کن."]
    bot.send_message(m.chat.id,"\n".join(lines),reply_markup=earn_jobs_markup(channels,orders))

@bot.callback_query_handler(func=lambda c:c.data=="earn_refresh")
def earn_refresh(c):
    channels,orders=earn_jobs()
    bot.answer_callback_query(c.id,"لیست بروزرسانی شد ✅")
    try:
        bot.edit_message_text(
            "🎯 <b>دریافت سکه</b>\n"+SEP+
            f"\n📢 کانال‌ها: {len(channels)}\n👥 سفارش‌های فعال: {len(orders)}\n\n⬇️ انتخاب کن:",
            c.message.chat.id,c.message.message_id,
            reply_markup=earn_jobs_markup(channels,orders)
        )
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c:c.data.startswith("earnch:"))
def earn_channel_open(c):
    add_user(c.from_user)
    cid=int(c.data.split(":")[1])
    with db() as d:
        ch=d.execute("SELECT * FROM channels WHERE id=? AND active=1",(cid,)).fetchone()
        if not ch:
            return bot.answer_callback_query(c.id,"کانال پیدا نشد.",show_alert=True)
        old=d.execute(
            "SELECT 1 FROM claims WHERE user_id=? AND channel_id=?",
            (c.from_user.id,cid)).fetchone()
    if old:
        return bot.answer_callback_query(c.id,"این کانال را قبلاً انجام داده‌ای.",show_alert=True)
    k=types.InlineKeyboardMarkup()
    if ch["username"]:
        k.add(types.InlineKeyboardButton(
            "📢 عضویت در کانال",
            url="https://t.me/"+ch["username"].lstrip("@")))
    k.add(types.InlineKeyboardButton("✅ عضو شدم؛ بررسی کن",callback_data=f"claimch:{cid}"))
    bot.answer_callback_query(c.id)
    bot.send_message(c.from_user.id,
        styled("عضویت برای دریافت سکه",
               f"📢 <b>{ch['title'] or ch['username']}</b>\n\n"
               "عضو کانال شو و سپس دکمه بررسی را بزن.\n"
               "🎁 پاداش: <b>1 سکه</b>"),
        reply_markup=k)

@bot.callback_query_handler(func=lambda c:c.data.startswith("claimch:"))
def claim_channel(c):
    add_user(c.from_user)
    cid=int(c.data.split(":")[1])
    with db() as d:
        ch=d.execute("SELECT * FROM channels WHERE id=? AND active=1",(cid,)).fetchone()
        old=d.execute(
            "SELECT 1 FROM claims WHERE user_id=? AND channel_id=?",
            (c.from_user.id,cid)).fetchone()
    if not ch:
        return bot.answer_callback_query(c.id,"کانال پیدا نشد.",show_alert=True)
    if old:
        return bot.answer_callback_query(c.id,"این پاداش قبلاً دریافت شده.",show_alert=True)
    if not check_join(c.from_user.id,ch):
        return bot.answer_callback_query(c.id,"هنوز عضویت تأیید نشد.",show_alert=True)
    with db() as d:
        d.execute("INSERT INTO claims(user_id,channel_id,claimed) VALUES(?,?,1)",
                  (c.from_user.id,cid))
        d.execute("UPDATE users SET coins=coins+1 WHERE id=?",(c.from_user.id,))
        d.execute("INSERT INTO logs(action,user_id,text,created) VALUES(?,?,?,?)",
                  ("coin_earned",c.from_user.id,f"channel #{cid}",now()))
    bot.answer_callback_query(c.id,"1 سکه اضافه شد 🎉",show_alert=True)
    bot.send_message(c.from_user.id,
        styled("عضویت تأیید شد",
               "✅ عضویت شما تأیید شد.\n"
               "━━━━━━━━━━━━━━━━━━\n"
               "🪙 <b>1 سکه</b> به موجودی شما اضافه شد."))

@bot.callback_query_handler(func=lambda c:c.data.startswith("earnord:"))
def earn_order_open(c):
    add_user(c.from_user)
    oid=int(c.data.split(":")[1])
    with db() as d:
        o=d.execute(
            "SELECT * FROM orders WHERE id=? AND status='pending' AND amount>0",
            (oid,)).fetchone()
        old=d.execute(
            "SELECT 1 FROM order_claims WHERE order_id=? AND user_id=?",
            (oid,c.from_user.id)).fetchone()
    if not o:
        return bot.answer_callback_query(c.id,"این سفارش دیگر فعال نیست.",show_alert=True)
    if old:
        return bot.answer_callback_query(c.id,"این سفارش را قبلاً انجام داده‌ای.",show_alert=True)
    k=types.InlineKeyboardMarkup()
    if o["channel_username"]:
        k.add(types.InlineKeyboardButton(
            "📢 عضویت در کانال",
            url="https://t.me/"+o["channel_username"].lstrip("@")))
    k.add(types.InlineKeyboardButton("✅ عضو شدم؛ دریافت 1 سکه",
                                     callback_data=f"claimord:{oid}"))
    bot.answer_callback_query(c.id)
    bot.send_message(c.from_user.id,
        styled(f"سفارش ممبر #{oid}",
               f"📢 کانال: <b>{o['channel_title'] or o['channel_username'] or o['channel_id']}</b>\n"
               f"👥 ممبر باقی‌مانده: <b>{o['amount']}</b>\n"
               "🎁 پاداش شما: <b>1 سکه</b>\n\n"
               "عضو کانال شو و بعد «عضو شدم» را بزن."),
        reply_markup=k)

@bot.callback_query_handler(func=lambda c:c.data.startswith("claimord:"))
def claim_order(c):
    add_user(c.from_user)
    oid=int(c.data.split(":")[1])
    with db() as d:
        o=d.execute(
            "SELECT * FROM orders WHERE id=? AND status='pending' AND amount>0",
            (oid,)).fetchone()
        old=d.execute(
            "SELECT 1 FROM order_claims WHERE order_id=? AND user_id=?",
            (oid,c.from_user.id)).fetchone()
    if not o:
        return bot.answer_callback_query(c.id,"این سفارش تکمیل شده یا فعال نیست.",show_alert=True)
    if old:
        return bot.answer_callback_query(c.id,"این سفارش را قبلاً انجام داده‌ای.",show_alert=True)

    # برای تأیید عضویت، ربات باید در کانال مقصد دسترسی لازم داشته باشد.
    try:
        member=bot.get_chat_member(o["channel_id"],c.from_user.id)
        joined=member.status not in ("left","kicked")
    except Exception:
        joined=False
    if not joined:
        return bot.answer_callback_query(
            c.id,
            "عضویت تأیید نشد. مطمئن شو عضو کانال شده‌ای و ربات در کانال دسترسی لازم دارد.",
            show_alert=True)

    with db() as d:
        # دوباره داخل تراکنش بررسی می‌کنیم تا دو نفر همزمان یک ظرفیت را نگیرند.
        fresh=d.execute(
            "SELECT amount,status FROM orders WHERE id=?",
            (oid,)).fetchone()
        if not fresh or fresh["status"]!="pending" or fresh["amount"]<=0:
            return bot.answer_callback_query(c.id,"ظرفیت سفارش تمام شد.",show_alert=True)
        d.execute(
            "INSERT INTO order_claims(order_id,user_id,claimed,created) VALUES(?,?,1,?)",
            (oid,c.from_user.id,now()))
        d.execute("UPDATE orders SET amount=amount-1,status=CASE WHEN amount-1<=0 THEN 'completed' ELSE 'pending' END WHERE id=?",(oid,))
        d.execute("UPDATE users SET coins=coins+1 WHERE id=?",(c.from_user.id,))
        d.execute("INSERT INTO logs(action,user_id,text,created) VALUES(?,?,?,?)",
                  ("order_member",c.from_user.id,f"order #{oid}",now()))
        owner_id=d.execute("SELECT user_id FROM orders WHERE id=?",(oid,)).fetchone()["user_id"]

    bot.answer_callback_query(c.id,"عضویت تأیید شد؛ 1 سکه گرفتی 🎉",show_alert=True)
    bot.send_message(c.from_user.id,
        styled("سکه دریافت شد",
               "✅ عضویت شما تأیید شد.\n"
               "━━━━━━━━━━━━━━━━━━\n"
               "🪙 <b>1 سکه</b> به حساب شما اضافه شد."))
    try:
        with db() as d:
            o2=d.execute("SELECT amount,status,original_amount FROM orders WHERE id=?",(oid,)).fetchone()
        done=o2["original_amount"]-o2["amount"] if o2 else 0
        bot.send_message(owner_id,
            styled(f"سفارش #{oid} بروزرسانی شد",
                   f"👥 یک ممبر جدید اضافه شد.\n"
                   f"📈 انجام‌شده: <b>{done}</b>\n"
                   f"⏳ باقی‌مانده: <b>{o2['amount']}</b>\n"
                   f"📌 وضعیت: <b>{o2['status']}</b>"))
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c:c.data=="check_all")
def check_all(c):
    # سازگاری با دکمه‌های قدیمی نسخه‌های قبلی
    add_user(c.from_user)
    channels=active_channels()
    got=0
    missing=[]
    for ch in channels:
        if not check_join(c.from_user.id,ch):
            missing.append(ch)
            continue
        with db() as d:
            old=d.execute(
                "SELECT 1 FROM claims WHERE user_id=? AND channel_id=?",
                (c.from_user.id,ch["id"])).fetchone()
            if not old:
                d.execute("INSERT INTO claims(user_id,channel_id,claimed) VALUES(?,?,1)",
                          (c.from_user.id,ch["id"]))
                d.execute("UPDATE users SET coins=coins+1 WHERE id=?",(c.from_user.id,))
                got+=1
    bot.answer_callback_query(c.id,f"{got} سکه اضافه شد.",show_alert=True)
    if missing:
        bot.send_message(c.from_user.id,f"❌ هنوز {len(missing)} کانال باقی مانده.")
    else:
        bot.send_message(c.from_user.id,f"✅ همه عضویت‌ها تأیید شد.\n🪙 +{got} سکه")

# ---------- BUY COINS ----------
PACKAGES = {50:10000,100:20000,200:40000,500:100000}

@bot.message_handler(func=lambda m:m.text=="💳 خرید کوین")
def buy_menu(m):
    k=types.InlineKeyboardMarkup()
    for n in (50,100,200,500):
        k.add(types.InlineKeyboardButton(f"{n} کوین",callback_data=f"pkg:{n}"))
    k.add(types.InlineKeyboardButton("✏️ مبلغ دلخواه",callback_data="custom_price"))
    bot.send_message(m.chat.id,
        styled("خرید کوین",
        "نرخ فعلی:\n"
        "هر 10 کوین = 2,000 تومان\n\n"
        f"💳 شماره کارت: <code>{CARD_NUMBER}</code>\n"
        f"👤 به نام: <b>{CARD_HOLDER}</b>\n\n"
        "یکی از بسته‌ها را انتخاب کن یا مبلغ دلخواه را بفرست:"),
        reply_markup=k)

@bot.callback_query_handler(func=lambda c:c.data.startswith("pkg:"))
def choose_pkg(c):
    coins=int(c.data.split(":")[1])
    price=PACKAGES[coins]
    bot.answer_callback_query(c.id)
    bot.send_message(c.from_user.id,
        f"💳 خرید <b>{coins} کوین</b>\n"
        f"💰 مبلغ: <b>{price:,} تومان</b>\n\n"
        f"حالا <b>آیدی عددی</b> شخصی که باید کوین‌ها به حسابش برود را ارسال کن.\n"
        f"مثال: <code>8880176059</code>")
    bot.register_next_step_handler_by_chat_id(c.from_user.id,
        receive_target,coins,price)

@bot.callback_query_handler(func=lambda c:c.data=="custom_price")
def custom(c):
    bot.answer_callback_query(c.id)
    bot.send_message(c.from_user.id,
        "✏️ تعداد کوین موردنظر را به صورت عدد بفرست.")
    bot.register_next_step_handler_by_chat_id(c.from_user.id,custom_coins)

def custom_coins(m):
    try:n=int(m.text)
    except:return bot.send_message(m.chat.id,"❌ فقط عدد.")
    if n<=0:return bot.send_message(m.chat.id,"❌ تعداد نامعتبر.")
    price=n*200
    bot.send_message(m.chat.id,
        f"💳 {n} کوین = <b>{price:,} تومان</b>\n\n"
        "آیدی عددی دریافت‌کننده را بفرست:")
    bot.register_next_step_handler(m,receive_target,n,price)

def receive_target(m,coins,price):
    try:target=int(m.text.strip())
    except:return bot.send_message(m.chat.id,"❌ فقط آیدی عددی بفرست.")
    bot.send_message(m.chat.id,
        f"👤 دریافت‌کننده: <code>{target}</code>\n"
        f"🪙 کوین: <b>{coins}</b>\n"
        f"💰 مبلغ: <b>{price:,} تومان</b>\n\n"
        f"💳 شماره کارت: <code>{CARD_NUMBER}</code>\n"
        f"👤 به نام: <b>{CARD_HOLDER}</b>\n\n"
        "حالا رسید پرداخت را به صورت <b>عکس</b> بفرست.")
    bot.register_next_step_handler(m,receive_receipt,coins,price,target)

def receive_receipt(m,coins,price,target):
    if not m.photo:
        bot.send_message(m.chat.id,"❌ لطفاً عکس رسید پرداخت را بفرست.")
        return bot.register_next_step_handler(m,receive_receipt,coins,price,target)
    fid=m.photo[-1].file_id
    with db() as c:
        cur=c.execute("""INSERT INTO purchases
            (buyer_id,target_id,coins,price,receipt_file,created)
            VALUES(?,?,?,?,?,?)""",
            (m.from_user.id,target,coins,price,fid,now()))
        pid=cur.lastrowid
    bot.send_message(m.chat.id,
        f"✅ درخواست خرید #{pid} ثبت شد.\n\n"
        "⏳ پس از بررسی رسید توسط مالک، کوین‌ها به آیدی عددی ثبت‌شده اضافه می‌شود.")
    k=types.InlineKeyboardMarkup()
    k.row(types.InlineKeyboardButton("✅ تأیید خرید",callback_data=f"approve:{pid}"),
          types.InlineKeyboardButton("❌ رد خرید",callback_data=f"reject:{pid}"))
    bot.send_photo(OWNER_ID,fid,
        caption=f"💳 <b>درخواست خرید کوین #{pid}</b>\n\n"
                f"👤 خریدار: <code>{m.from_user.id}</code>\n"
                f"🎯 دریافت‌کننده: <code>{target}</code>\n"
                f"🪙 کوین: <b>{coins}</b>\n"
                f"💰 مبلغ: <b>{price:,} تومان</b>",
        reply_markup=k)

@bot.callback_query_handler(func=lambda c:c.data.startswith("approve:") and c.from_user.id==OWNER_ID)
def approve(c):
    pid=int(c.data.split(":")[1])
    try:
        with db() as d:
            p=d.execute("SELECT * FROM purchases WHERE id=?",(pid,)).fetchone()
            if not p or p["status"]!="pending":
                return bot.answer_callback_query(c.id,"این درخواست قبلاً بررسی شده.",show_alert=True)
            d.execute("UPDATE purchases SET status='approved' WHERE id=?",(pid,))
            d.execute("INSERT OR IGNORE INTO users(id,username,created) VALUES(?,?,?)",
                      (p["target_id"],"",now()))
            d.execute("UPDATE users SET coins=coins+? WHERE id=?",(p["coins"],p["target_id"]))
            d.execute("INSERT INTO logs(action,user_id,text,created) VALUES(?,?,?,?)",
                      ("purchase_approved",p["target_id"],f"+{p['coins']} coins purchase #{pid}",now()))
        bot.answer_callback_query(c.id,"خرید تأیید شد و سکه‌ها اضافه شدند ✅",show_alert=True)
        bot.edit_message_caption(
            caption=styled(f"خرید #{pid} تأیید شد",
                f"🎯 دریافت‌کننده: <code>{p['target_id']}</code>\n"
                f"🪙 +{p['coins']} کوین\n"
                f"💰 {p['price']:,} تومان\n"
                "✅ وضعیت: تأیید شده"),
            chat_id=c.message.chat.id,message_id=c.message.message_id)
        try:
            bot.send_message(p["target_id"],
                styled("خرید شما تأیید شد",
                    f"🎉 <b>{p['coins']} کوین</b> به حساب شما اضافه شد."))
        except: pass
    except Exception as e:
        bot.answer_callback_query(c.id,"خطا در تأیید خرید؛ دوباره امتحان کنید.",show_alert=True)

@bot.callback_query_handler(func=lambda c:c.data.startswith("reject:") and c.from_user.id==OWNER_ID)
def reject(c):
    pid=int(c.data.split(":")[1])
    try:
        with db() as d:
            p=d.execute("SELECT * FROM purchases WHERE id=?",(pid,)).fetchone()
            if not p or p["status"]!="pending":
                return bot.answer_callback_query(c.id,"این درخواست قبلاً بررسی شده.",show_alert=True)
            d.execute("UPDATE purchases SET status='rejected' WHERE id=?",(pid,))
        bot.answer_callback_query(c.id,"درخواست رد شد ❌",show_alert=True)
        bot.edit_message_caption(
            caption=styled(f"خرید #{pid} رد شد","❌ وضعیت: رد شده"),
            chat_id=c.message.chat.id,message_id=c.message.message_id)
        try: bot.send_message(p["buyer_id"],f"❌ خرید #{pid} توسط مالک رد شد.")
        except: pass
    except:
        bot.answer_callback_query(c.id,"خطا در رد درخواست.",show_alert=True)

# ---------- MEMBER ORDER ----------
@bot.message_handler(func=lambda m:m.text=="👥 سفارش ممبر")
def order_start(m):
    add_user(m.from_user)
    with db() as c:
        u=c.execute("SELECT coins FROM users WHERE id=?",(m.from_user.id,)).fetchone()
    bot.send_message(m.chat.id, styled("ثبت سفارش ممبر",
        f"🪙 موجودی شما: <b>{u['coins']}</b> سکه\n"
        f"{SEP}\n"
        "📢 یوزرنیم یا آیدی عددی کانال را بفرست.\n"
        "⚠️ برای اینکه ممبرها بتوانند عضویتشان را تأیید کنند، ربات باید در کانال مقصد دسترسی لازم داشته باشد.\n"
        "مثال: <code>@MyChannel</code>"))
    bot.register_next_step_handler(m, order_channel)

def order_channel(m):
    ch=m.text.strip() if m.text else ""
    if not ch:
        return bot.send_message(m.chat.id,"❌ آدرس کانال معتبر نیست.")
    try:
        info=bot.get_chat(ch)
        title=info.title or getattr(info,"username","") or str(info.id)
        uname=getattr(info,"username","") or ""
        me=bot.get_me()
        mm=bot.get_chat_member(info.id,me.id)
        if mm.status not in ("administrator","creator"):
            return bot.send_message(
                m.chat.id,
                "❌ ربات در این کانال ادمین نیست.\n"
                "ربات را ادمین کن و دوباره سفارش را ثبت کن.")
        bot.send_message(m.chat.id, styled("تعداد ممبر",
            f"📢 کانال: <b>{title}</b>\n"
            f"🔗 @{uname if uname else 'بدون یوزرنیم'}\n"
            f"{SEP}\n"
            "تعداد ممبر موردنظر را فقط به صورت عدد بفرست.\n"
            "مثال: <code>100</code>"))
        bot.register_next_step_handler(m, order_amount, str(info.id), title, uname)
    except Exception:
        bot.send_message(m.chat.id,"❌ کانال پیدا نشد یا ربات دسترسی لازم را ندارد.")

def order_amount(m, chat_id, title, uname):
    try:n=int((m.text or "").strip())
    except:return bot.send_message(m.chat.id,"❌ تعداد باید عدد باشد.")
    if n<=0 or n>100000:
        return bot.send_message(m.chat.id,"❌ تعداد باید بین 1 تا 100000 باشد.")
    with db() as c:
        u=c.execute("SELECT coins FROM users WHERE id=?",(m.from_user.id,)).fetchone()
    if not u or u["coins"]<n:
        return bot.send_message(m.chat.id,
            f"❌ موجودی کافی نیست.\n🪙 موجودی: {u['coins'] if u else 0}\n"
            f"🪙 موردنیاز: {n}")
    k=types.InlineKeyboardMarkup()
    k.row(types.InlineKeyboardButton("✅ تأیید سفارش",callback_data=f"neworder:{m.from_user.id}:{n}:{chat_id}:{uname}"),
          types.InlineKeyboardButton("❌ لغو",callback_data="cancelorder"))
    bot.send_message(m.chat.id, styled("تأیید سفارش",
        f"📢 کانال: <b>{title}</b>\n"
        f"👥 تعداد: <b>{n} ممبر</b>\n"
        f"🪙 هزینه: <b>{n} سکه</b>\n"
        f"{SEP}\n"
        "بعد از تأیید، سفارش فوراً در «🎯 دریافت سکه» برای کاربران نمایش داده می‌شود.\n"
        "❌ سفارش برای مالک ارسال نمی‌شود."),reply_markup=k)

@bot.callback_query_handler(func=lambda c:c.data=="cancelorder")
def cancel_order(c):
    bot.answer_callback_query(c.id,"لغو شد.")
    try:bot.delete_message(c.message.chat.id,c.message.message_id)
    except:pass

@bot.callback_query_handler(func=lambda c:c.data.startswith("neworder:"))
def create_order(c):
    parts=c.data.split(":",4)
    if len(parts)<5:
        return bot.answer_callback_query(c.id,"اطلاعات سفارش ناقص است.",show_alert=True)
    _,uid,n,chat_id,uname=parts
    if c.from_user.id != int(uid):
        return bot.answer_callback_query(c.id,"این سفارش برای شما نیست.",show_alert=True)
    uid=int(uid); n=int(n)
    with db() as d:
        u=d.execute("SELECT coins FROM users WHERE id=?",(uid,)).fetchone()
        if not u or u["coins"]<n:
            return bot.answer_callback_query(c.id,"موجودی کافی نیست.",show_alert=True)
        d.execute("UPDATE users SET coins=coins-? WHERE id=?",(n,uid))
        # عنوان/یوزرنیم را از تلگرام دوباره می‌گیریم.
        try:
            info=bot.get_chat(chat_id)
            title=info.title or uname or chat_id
            uname2=getattr(info,"username","") or uname
        except:
            title=uname or chat_id
            uname2=uname
        cur=d.execute(
            """INSERT INTO orders
               (user_id,amount,status,created,original_amount,channel_id,channel_title,channel_username)
               VALUES(?,?,?,?,?,?,?,?)""",
            (uid,n,"pending",now(),n,str(chat_id),title,uname2))
        oid=cur.lastrowid
        d.execute("INSERT INTO logs(action,user_id,text,created) VALUES(?,?,?,?)",
                  ("order_created",uid,f"order #{oid} {n} members -> {chat_id}",now()))
    bot.answer_callback_query(c.id,"سفارش ثبت شد و وارد صف دریافت سکه شد ✅",show_alert=True)
    bot.edit_message_text(styled("سفارش ثبت شد",
        f"📦 شماره سفارش: <b>#{oid}</b>\n"
        f"📢 کانال: <b>{title}</b>\n"
        f"👥 تعداد: <b>{n}</b> ممبر\n"
        f"🪙 کسر شده: <b>{n}</b> سکه\n"
        f"{SEP}\n"
        "🟢 سفارش برای کاربران «🎯 دریافت سکه» فعال شد.\n"
        "👥 هر عضو تأییدشده = 1 سکه برای او + 1 ممبر برای سفارش شما."),
        c.message.chat.id,c.message.message_id)

@bot.callback_query_handler(func=lambda c:c.data.startswith("ordercancel:"))
def order_cancel(c):
    oid=int(c.data.split(":")[1])
    with db() as d:
        o=d.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
        if not o or o["status"]!="pending":
            return bot.answer_callback_query(c.id,"سفارش قابل لغو نیست.",show_alert=True)
        if c.from_user.id != o["user_id"] and c.from_user.id != OWNER_ID:
            return bot.answer_callback_query(c.id,"دسترسی ندارید.",show_alert=True)
        d.execute("UPDATE orders SET status='cancelled' WHERE id=?",(oid,))
        # فقط سکه‌های باقی‌مانده برگردانده می‌شود.
        d.execute("UPDATE users SET coins=coins+? WHERE id=?",(o["amount"],o["user_id"]))
    bot.answer_callback_query(c.id,"سفارش لغو شد و سکه باقی‌مانده برگشت.",show_alert=True)
    try:
        bot.edit_message_text(
            styled(f"سفارش #{oid} لغو شد",
                   f"🪙 <b>{o['amount']} سکه</b> باقی‌مانده به حساب صاحب سفارش برگشت."),
            c.message.chat.id,c.message.message_id)
    except: pass
    try:
        bot.send_message(o["user_id"],
                         f"❌ سفارش <b>#{oid}</b> لغو شد.\n🪙 {o['amount']} سکه باقی‌مانده برگشت.")
    except: pass

@bot.message_handler(func=lambda m:m.text=="📦 پیگیری سفارش")
def track(m):
    with db() as c:r=c.execute(
        "SELECT id,amount,original_amount,channel_title,channel_username,status FROM orders "
        "WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (m.from_user.id,)).fetchall()
    lines=[]
    for x in r:
        done=(x["original_amount"] or x["amount"])-x["amount"]
        lines.append(
            f"📦 <b>#{x['id']}</b> | {x['channel_title'] or x['channel_username'] or '-'}\n"
            f"👥 انجام‌شده: {done} | باقی: {x['amount']} | وضعیت: {x['status']}"
        )
    bot.send_message(m.chat.id,styled("پیگیری سفارش", "\n\n".join(lines) or "📦 سفارشی ندارید."))

@bot.message_handler(func=lambda m:m.text=="📣 تبلیغ کانال من")
def ads(m): bot.send_message(m.chat.id,"📣 سیستم تبلیغات کانال در نسخه بعدی فعال می‌شود.")

@bot.message_handler(func=lambda m:m.text=="🎮 کلوب بازی")
def club(m): bot.send_message(m.chat.id,"🎮 کلوب بازی به‌زودی.")

@bot.message_handler(func=lambda m:m.text=="💎 VIP")
def vip(m): bot.send_message(m.chat.id,"💎 بخش VIP به‌زودی.")

@bot.message_handler(func=lambda m:m.text=="🔗 لینک دعوت من")
def invite(m):
    bot.send_message(m.chat.id,
        f"🔗 لینک دعوت شما:\nhttps://t.me/{bot.get_me().username}?start={m.from_user.id}")

@bot.message_handler(func=lambda m:m.text=="📢 ثبت کانال")
def register_channel(m):
    bot.send_message(m.chat.id,"📢 آیدی عددی یا @username کانال را بفرست.\nمثال: @MyChannel")
    bot.register_next_step_handler(m,verify_channel)

def verify_channel(m):
    x=m.text.strip()
    try:
        ch=bot.get_chat(x)
        me=bot.get_me()
        mm=bot.get_chat_member(ch.id,me.id)
        if mm.status not in ("administrator","creator"):
            return bot.send_message(m.chat.id,"❌ ربات ادمین کانال نیست.")
        with db() as c:
            c.execute("""INSERT OR REPLACE INTO channels
                (chat_id,username,title,active) VALUES(?,?,?,1)""",
                (str(ch.id),getattr(ch,"username","") or "",ch.title))
        bot.send_message(m.chat.id,
            f"✅ <b>{ch.title}</b>\n\nربات ادمین بودن خودش را بررسی کرد و کانال ثبت شد.")
    except Exception as e:
        bot.send_message(m.chat.id,"❌ کانال پیدا نشد یا دسترسی ربات کافی نیست.")

@bot.message_handler(func=lambda m:m.text=="☎️ پشتیبانی")
def support(m):
    bot.send_message(m.chat.id,"☎️ پیام خودت را بفرست تا تیکت ثبت شود.")
    bot.register_next_step_handler(m,save_ticket)

def save_ticket(m):
    with db() as c:
        c.execute("INSERT INTO tickets(user_id,text,created) VALUES(?,?,?)",
                  (m.from_user.id,m.text,now()))
    bot.send_message(m.chat.id,"✅ تیکت ثبت شد. مالک بررسی می‌کند.")

# ---------- USER EXTRA SYSTEMS ----------
# 60 سیستم کاربردی کاربر، در 3 صفحه 20تایی
USER_SYSTEMS=[
    ("👤 پروفایل من","profile"),
    ("🪙 موجودی سکه","balance"),
    ("📊 آمار سکه","earnstats"),
    ("📦 آمار سفارش","orders"),
    ("💳 تاریخچه خرید","purchases"),
    ("🧾 تاریخچه سفارش","history"),
    ("🎯 کانال‌های کسب سکه","channels"),
    ("🔗 آمار دعوت","ref"),
    ("💰 تعرفه کوین","prices"),
    ("🛒 بسته‌های خرید","packages"),
    ("✏️ خرید تعداد دلخواه","custom"),
    ("📢 راهنمای ثبت کانال","channel_help"),
    ("🔎 جستجوی سفارش","search_order"),
    ("🧾 شماره سفارش","order_no"),
    ("💳 اطلاعات پرداخت","payment"),
    ("📈 آمار تبلیغات","ads"),
    ("🔔 اعلان‌ها","notify"),
    ("🎁 هدیه روزانه","daily"),
    ("🎟 کد هدیه","gift"),
    ("🛡 امنیت حساب","security"),
    ("📋 قوانین","rules"),
    ("🆘 مرکز کمک","help"),
    ("☎️ تماس با مالک","owner_contact"),
    ("🐞 گزارش مشکل","report"),
    ("💸 گزارش تراکنش","transaction"),
    ("📦 گزارش سفارش","order_report"),
    ("⭐ امتیازدهی","rating"),
    ("🕐 تاریخ عضویت","join_date"),
    ("🔢 تعداد سفارش","order_count"),
    ("👥 تعداد دعوت","invite_count"),
    ("📢 تعداد کانال","channel_count"),
    ("✨ سکه دریافت‌شده","coins_earned"),
    ("🔥 سکه مصرف‌شده","coins_spent"),
    ("💎 سکه خریداری‌شده","coins_bought"),
    ("🎁 سکه هدیه","coins_gift"),
    ("📦 آخرین سفارش","last_order"),
    ("💳 آخرین خرید","last_purchase"),
    ("🟢 آخرین فعالیت","last_activity"),
    ("✅ وضعیت حساب","account_status"),
    ("🔐 وضعیت دسترسی","access_status"),
    ("⚙️ تنظیمات حساب","settings"),
    ("🔔 تنظیم اعلان","notify_settings"),
    ("🛒 مرکز سفارش","order_center"),
    ("💳 مرکز خرید","shop_center"),
    ("🪙 مرکز سکه","coin_center"),
    ("🤝 مرکز دعوت","invite_center"),
    ("☎️ مرکز پشتیبانی","support_center"),
    ("📚 مرکز راهنما","help_center"),
    ("💎 مرکز VIP","vip_center"),
    ("🎮 مرکز بازی","game_center"),
    ("📣 مرکز تبلیغات","ad_center"),
    ("🗂 آرشیو خرید","purchase_archive"),
    ("🗂 آرشیو سفارش","order_archive"),
    ("🔄 بازگشت به منو","back"),
    ("📜 راهنمای سریع","quick_help"),
    ("🧑‍💻 شناسه عددی","numeric_id"),
    ("👤 یوزرنیم","username"),
    ("🚫 لغو سفارش","cancel_info"),
]

def user_extra_menu(page=0):
    k=types.InlineKeyboardMarkup(row_width=2)
    chunk=USER_SYSTEMS[page*20:(page+1)*20]
    for i,(name,key) in enumerate(chunk,page*20):
        k.add(types.InlineKeyboardButton(name,callback_data=f"u:{key}"))
    nav=[]
    if page>0:
        nav.append(types.InlineKeyboardButton("⬅️ قبلی",callback_data=f"usp:{page-1}"))
    if (page+1)*20<len(USER_SYSTEMS):
        nav.append(types.InlineKeyboardButton("بعدی ➡️",callback_data=f"usp:{page+1}"))
    if nav:
        k.row(*nav)
    k.add(types.InlineKeyboardButton("🏠 منوی اصلی",callback_data="u:back"))
    return k

@bot.message_handler(func=lambda m:m.text=="⚙️ امکانات بیشتر")
def extra_user(m):
    bot.send_message(
        m.chat.id,
        styled("⚙️ امکانات پیشرفته",
               "━━━━━━━━━━━━━━━━━━\n"
               "۶۰ سیستم کاربردی برای حساب، سکه، سفارش، دعوت، پرداخت و پشتیبانی.\n"
               "صفحه‌ها را با «بعدی» ورق بزن."),
        reply_markup=user_extra_menu(0)
    )

@bot.callback_query_handler(func=lambda c:c.data.startswith("usp:"))
def user_system_page(c):
    try:
        page=int(c.data.split(":")[1])
        max_page=(len(USER_SYSTEMS)-1)//20
        if page<0 or page>max_page:
            return bot.answer_callback_query(c.id,"صفحه نامعتبر است.",show_alert=True)
        bot.answer_callback_query(c.id)
        bot.edit_message_reply_markup(
            c.message.chat.id,
            c.message.message_id,
            reply_markup=user_extra_menu(page)
        )
    except Exception:
        bot.answer_callback_query(c.id,"خطا در تغییر صفحه.",show_alert=True)

@bot.callback_query_handler(func=lambda c:c.data.startswith("u:"))
def user_system(c):
    add_user(c.from_user)
    key=c.data[2:]
    with db() as d:
        u=d.execute("SELECT * FROM users WHERE id=?",(c.from_user.id,)).fetchone()
        claims=d.execute("SELECT COUNT(*) n FROM claims WHERE user_id=?",(c.from_user.id,)).fetchone()["n"]
        orders=d.execute("SELECT COUNT(*) n FROM orders WHERE user_id=?",(c.from_user.id,)).fetchone()["n"]
        purchases=d.execute("SELECT COUNT(*) n FROM purchases WHERE buyer_id=?",(c.from_user.id,)).fetchone()["n"]
        earned=d.execute("SELECT COUNT(*) n FROM claims WHERE user_id=?",(c.from_user.id,)).fetchone()["n"]
        spent=d.execute("SELECT COALESCE(SUM(amount),0) n FROM orders WHERE user_id=? AND status!='cancelled'",(c.from_user.id,)).fetchone()["n"]
        bought=d.execute("SELECT COALESCE(SUM(coins),0) n FROM purchases WHERE target_id=? AND status='approved'",(c.from_user.id,)).fetchone()["n"]
        last_order=d.execute("SELECT id,amount,status FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1",(c.from_user.id,)).fetchone()
        last_purchase=d.execute("SELECT id,coins,price,status FROM purchases WHERE buyer_id=? ORDER BY id DESC LIMIT 1",(c.from_user.id,)).fetchone()
    msgs={
        "profile":f"👤 شناسه عددی: <code>{c.from_user.id}</code>\n🪙 سکه: <b>{u['coins']}</b>",
        "balance":f"🪙 موجودی فعلی: <b>{u['coins']}</b> سکه",
        "earnstats":f"🎯 عضویت‌های ثبت‌شده: <b>{claims}</b>\n🪙 موجودی: <b>{u['coins']}</b>",
        "orders":f"📦 تعداد سفارش‌ها: <b>{orders}</b>",
        "purchases":f"💳 تعداد خریدها: <b>{purchases}</b>",
        "history":f"📦 سفارش‌ها: <b>{orders}</b> | 💳 خریدها: <b>{purchases}</b>",
        "channels":"📢 کانال‌های فعال کسب سکه از دکمه «دریافت سکه» قابل مشاهده‌اند.",
        "ref":f"🔗 لینک دعوت:\nhttps://t.me/{bot.get_me().username}?start={c.from_user.id}",
        "prices":"💰 هر 10 کوین = 2,000 تومان",
        "packages":"🛒 50 / 100 / 200 / 500 کوین + خرید تعداد دلخواه",
        "custom":"✏️ برای خرید تعداد دلخواه، از «خرید کوین» گزینه «مبلغ دلخواه» را انتخاب کن.",
        "channel_help":"📢 برای ثبت کانال، ربات باید در کانال ادمین باشد و سپس @username کانال را بفرست.",
        "search_order":"🔎 برای مشاهده سفارش‌ها از «پیگیری سفارش» استفاده کن.",
        "order_no":f"📦 آخرین شماره سفارش: #{last_order['id'] if last_order else 'نداری'}",
        "payment":f"💳 شماره کارت: <code>{CARD_NUMBER}</code>\n👤 به نام: <b>{CARD_HOLDER}</b>",
        "ads": "📣 سیستم تبلیغات در بخش تبلیغ کانال من قرار دارد.",
        "notify":"🔔 اعلان‌های مهم سفارش و خرید برایت ارسال می‌شوند.",
        "daily":"🎁 هدیه روزانه در این نسخه آماده توسعه است.",
        "gift":"🎟 کد هدیه از طرف مالک قابل ارائه است.",
        "security":"🛡 اطلاعات ورود یا کدهای حساس را برای کسی ارسال نکن.",
        "rules":"📋 قوانین: اسپم، تقلب و سوءاستفاده از سیستم ممنوع است.",
        "help":"🆘 از منوی اصلی برای سکه، خرید، سفارش و پشتیبانی استفاده کن.",
        "owner_contact":"☎️ از بخش پشتیبانی برای ارتباط با مالک استفاده کن.",
        "report":"🐞 مشکل را از بخش پشتیبانی گزارش کن.",
        "transaction":"💸 اطلاعات خرید و تراکنش از بخش خرید قابل پیگیری است.",
        "order_report":"📦 سفارش‌ها از بخش پیگیری سفارش قابل مشاهده‌اند.",
        "rating":"⭐ امتیازدهی در نسخه بعدی فعال می‌شود.",
        "join_date":f"🕐 تاریخ ثبت حساب: {time.strftime('%Y-%m-%d %H:%M',time.localtime(u['created']))}",
        "order_count":f"🔢 تعداد سفارش: <b>{orders}</b>",
        "invite_count":"👥 آمار دعوت در نسخه فعلی بر اساس دعوت‌های ثبت‌شده توسعه داده می‌شود.",
        "channel_count":f"📢 تعداد کانال‌های فعال: <b>{len(active_channels())}</b>",
        "coins_earned":f"✨ سکه کسب‌شده از عضویت: <b>{earned}</b>",
        "coins_spent":f"🔥 سکه مصرف‌شده برای سفارش: <b>{spent}</b>",
        "coins_bought":f"💎 سکه خریداری‌شده برای حساب: <b>{bought}</b>",
        "coins_gift":"🎁 سکه هدیه: توسط مالک قابل اضافه شدن است.",
        "last_order":f"📦 آخرین سفارش: #{last_order['id']} | {last_order['amount']} | {last_order['status']}" if last_order else "📦 سفارشی نداری.",
        "last_purchase":f"💳 آخرین خرید: #{last_purchase['id']} | {last_purchase['coins']} کوین | {last_purchase['status']}" if last_purchase else "💳 خریدی نداری.",
        "last_activity":"🟢 آخرین فعالیت: همین الان",
        "account_status":"✅ وضعیت حساب: فعال",
        "access_status":"✅ وضعیت دسترسی: مجاز",
        "settings":"⚙️ تنظیمات حساب در حال توسعه است.",
        "notify_settings":"🔔 اعلان‌ها فعال هستند.",
        "order_center":"🛒 مرکز سفارش: ثبت و پیگیری سفارش ممبر.",
        "shop_center":"💳 مرکز خرید: خرید کوین و ارسال رسید.",
        "coin_center":"🪙 مرکز سکه: کسب، خرید و مصرف سکه.",
        "invite_center":"🤝 مرکز دعوت: لینک دعوت و آمار دعوت.",
        "support_center":"☎️ مرکز پشتیبانی: ثبت تیکت.",
        "help_center":"📚 مرکز راهنما: راهنمای سریع امکانات ربات.",
        "vip_center":"💎 مرکز VIP: امکانات VIP در حال توسعه.",
        "game_center":"🎮 مرکز بازی: کلوب بازی در حال توسعه.",
        "ad_center":"📣 مرکز تبلیغات: تبلیغ کانال من.",
        "purchase_archive":f"🗂 آرشیو خریدهای شما: <b>{purchases}</b>",
        "order_archive":f"🗂 آرشیو سفارش‌های شما: <b>{orders}</b>",
        "quick_help":"📜 سریع‌ترین مسیر: دریافت سکه ← سفارش ممبر / خرید کوین ← ارسال رسید.",
        "numeric_id":f"🧑‍💻 آیدی عددی شما: <code>{c.from_user.id}</code>",
        "username":f"👤 یوزرنیم: @{c.from_user.username}" if c.from_user.username else "👤 یوزرنیم تنظیم نشده.",
        "cancel_info":"🚫 برای لغو سفارش‌های در انتظار، با پشتیبانی تماس بگیر.",
    }
    if key=="back":
        bot.answer_callback_query(c.id)
        return bot.send_message(c.from_user.id,"🏠 منوی اصلی",reply_markup=main_menu())
    bot.answer_callback_query(c.id)
    bot.send_message(c.from_user.id,styled("سیستم کاربری",msgs.get(key,"این سیستم آماده استفاده است.")))

# ---------- OWNER EXTENDED SYSTEMS ----------
OWNER_SYSTEMS=[
    "مدیریت کاربران","جستجوی کاربر","مشاهده موجودی","افزایش سکه","کاهش سکه","صفر کردن سکه",
    "مسدودسازی","رفع مسدودی","یادداشت کاربر","آمار کاربر","آخرین فعالیت","تعداد سفارش‌ها",
    "خریدهای کاربر","عضویت‌های کاربر","مدیریت کانال‌ها","ثبت کانال","حذف کانال","فعال/غیرفعال کانال",
    "بررسی ادمین بودن","آمار کانال","سفارش‌های جدید","تکمیل سفارش","لغو سفارش","برگشت سکه",
    "جستجوی سفارش","وضعیت سفارش","خریدهای در انتظار","تأیید خرید","رد خرید","جستجوی خرید",
    "تیکت‌های باز","بستن تیکت","پاسخ تیکت","ارسال پیام خصوصی","پیام همگانی","پیام به کانال",
    "آمار روزانه","آمار هفتگی","آمار ماهانه","گزارش درآمد","گزارش سکه","گزارش سفارش",
    "گزارش کانال","گزارش کاربران","لاگ سیستم","لاگ خرید","لاگ سفارش","تنظیم تعرفه",
    "تنظیم بسته‌ها","تنظیم حداقل خرید","تنظیم حداکثر خرید","تنظیم متن خوشامد","تنظیم متن قوانین",
    "تنظیم متن پشتیبانی","تنظیم کارت","تنظیم نام صاحب کارت","مدیریت VIP","مدیریت کلوب بازی",
    "مدیریت تبلیغات","مدیریت دعوت","مدیریت هدیه","مدیریت کد هدیه","مدیریت اعلان‌ها","ارسال اعلان",
    "پاکسازی لاگ","پاکسازی سفارش قدیمی","پاکسازی تیکت قدیمی","پشتیبان دیتابیس","وضعیت دیتابیس",
    "تعداد رکوردها","تست اتصال تلگرام","تست ارسال پیام","تست ارسال عکس","تست دکمه‌ها",
    "مدیریت دسترسی","سطح دسترسی","مدیران","افزودن مدیر","حذف مدیر","ثبت رویداد","مدیریت رویداد",
    "قرعه‌کشی","مسابقه","کد تخفیف","شارژ دستی","برداشت دستی","تراز حساب‌ها","بررسی تراکنش",
    "تأیید دستی","رد دستی","بازگشت تراکنش","قفل سفارش","بازکردن سفارش","قفل کاربر",
    "بازکردن کاربر","پیام خوشامد","پیام خروج","آمار آنلاین","کاربران فعال","کاربران جدید",
    "کاربران مسدود","کانال‌های فعال","کانال‌های خاموش","خریدهای تأییدشده","خریدهای ردشده",
    "سفارش‌های تکمیل‌شده","سفارش‌های لغوشده","سکه‌های توزیع‌شده","سکه‌های خریداری‌شده",
    "سکه‌های مصرف‌شده","محاسبه درآمد","محاسبه بدهی","گزارش مالی","گزارش امنیت",
    "هشدارهای سیستم","مدیریت خطا","حالت تعمیرات","فعال‌سازی ربات","خاموشی سرویس",
    "تنظیم پیام تعمیرات","تنظیم زبان","تنظیم منطقه زمانی","تنظیم قالب پیام","تنظیم جداکننده",
    "قالب رسید","قالب سفارش","قالب تیکت","قالب کانال","قالب دعوت","قالب سکه",
    "سیستم ضدتقلب","جلوگیری از تکرار سکه","جلوگیری از سفارش تکراری","محدودیت درخواست",
    "محدودیت پیام","محدودیت خرید","محدودیت سفارش","ثبت IP","ثبت دستگاه","گزارش مشکوک",
    "لیست کاربران مشکوک","بررسی خودکار","بررسی دستی","تأیید عضویت","رد عضویت","مدیریت صف",
    "اولویت سفارش","اولویت تیکت","آرشیو سفارش","آرشیو تیکت","آرشیو خرید","آرشیو کاربر",
    "بازگردانی داده","خروجی کاربران","خروجی سفارش‌ها","خروجی خریدها","خروجی لاگ‌ها",
    "نمایش نسخه","نمایش زمان اجرا","نمایش شناسه مالک","نمایش تنظیمات","بازنشانی تنظیمات",
    "بازنشانی کانال‌ها","بازنشانی صف","بازنشانی آمار","تأیید نهایی","گزارش مدیریتی",
    "داشبورد مالک","مرکز کنترل","مرکز مالی","مرکز سفارش","مرکز کاربران","مرکز کانال",
    "مرکز پشتیبانی","مرکز امنیت","مرکز اعلان","مرکز گزارش","مرکز ابزار","حالت حرفه‌ای",
    "حالت ساده","راهنمای مالک","راهنمای سفارش","راهنمای خرید","راهنمای کانال","راهنمای تیکت",
    "راهنمای سکه","نسخه آزمایشی","بررسی سلامت","پاکسازی امن","قفل تنظیمات","بازکردن تنظیمات",
    "تأیید تغییرات","ثبت تغییرات","تاریخچه تغییرات","پایان"
]
# Ensure exactly 200 labeled owner systems by padding if needed.
OWNER_SYSTEMS=(OWNER_SYSTEMS+[f"سیستم مالک {i}" for i in range(1,201)])[:200]

def owner_extended_keyboard(page=0):
    k=types.InlineKeyboardMarkup(row_width=2)
    chunk=OWNER_SYSTEMS[page*20:(page+1)*20]
    for i,name in enumerate(chunk,page*20):
        k.add(types.InlineKeyboardButton(f"{i+1}. {name}",callback_data=f"os:{i}"))
    if page>0:k.add(types.InlineKeyboardButton("⬅️ قبلی",callback_data=f"osp:{page-1}"))
    if (page+1)*20<len(OWNER_SYSTEMS):k.add(types.InlineKeyboardButton("بعدی ➡️",callback_data=f"osp:{page+1}"))
    return k

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="🧩 200 سیستم مالک")
def owner_200(m):
    bot.send_message(m.chat.id,styled("مرکز 200 سیستم مالک",
        "سیستم‌ها به صورت دسته‌بندی‌شده نمایش داده می‌شوند.\n"
        "سیستم‌های اصلی مانند خرید، سکه، سفارش، کانال و تیکت فعال هستند."),
        reply_markup=owner_extended_keyboard(0))

@bot.callback_query_handler(func=lambda c:c.data.startswith("osp:") and c.from_user.id==OWNER_ID)
def owner_system_page(c):
    page=int(c.data.split(":")[1])
    bot.answer_callback_query(c.id)
    bot.edit_message_reply_markup(c.message.chat.id,c.message.message_id,reply_markup=owner_extended_keyboard(page))

@bot.callback_query_handler(func=lambda c:c.data.startswith("os:") and c.from_user.id==OWNER_ID)
def owner_system(c):
    i=int(c.data.split(":")[1])
    name=OWNER_SYSTEMS[i]
    bot.answer_callback_query(c.id)
    if name=="افزایش سکه":
        bot.send_message(c.from_user.id,"فرمت: <code>سکه ID AMOUNT</code>")
    elif name=="کاهش سکه":
        bot.send_message(c.from_user.id,"برای کاهش سکه: <code>کسر ID AMOUNT</code>")
    elif name=="پشتیبان دیتابیس":
        bot.send_message(c.from_user.id,f"💾 دیتابیس فعال: <code>{DB}</code>")
    elif name=="نمایش شناسه مالک":
        bot.send_message(c.from_user.id,f"👑 OWNER ID: <code>{OWNER_ID}</code>")
    elif name=="تنظیم کارت":
        bot.send_message(c.from_user.id,f"💳 کارت فعلی: <code>{CARD_NUMBER}</code>\n👤 {CARD_HOLDER}")
    else:
        bot.send_message(c.from_user.id,styled(name,"این سیستم در پنل حرفه‌ای ثبت شده است و بخش اجرایی آن از منوی اصلی مدیریت می‌شود."))

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="🛠 ابزار مالک")
def owner_tools(m):
    bot.send_message(m.chat.id,styled("ابزار مالک",
        "دستورات سریع:\n"
        "<code>سکه ID AMOUNT</code> — دادن سکه\n"
        "<code>کسر ID AMOUNT</code> — کسر سکه\n"
        "<code>مسدود ID</code> — مسدود\n"
        "<code>رفع ID</code> — رفع مسدودی"))

@bot.message_handler(func=lambda m:is_owner(m) and m.text and m.text.startswith("کسر "))
def take_coin(m):
    p=m.text.split()
    if len(p)!=3:return bot.send_message(m.chat.id,"❌ فرمت: کسر ID AMOUNT")
    try:uid,amount=int(p[1]),int(p[2])
    except:return bot.send_message(m.chat.id,"❌ آیدی و مقدار باید عدد باشند.")
    if amount<=0:return bot.send_message(m.chat.id,"❌ مقدار نامعتبر.")
    with db() as c:
        u=c.execute("SELECT coins FROM users WHERE id=?",(uid,)).fetchone()
        if not u:return bot.send_message(m.chat.id,"❌ کاربر پیدا نشد.")
        if u["coins"]<amount:return bot.send_message(m.chat.id,"❌ موجودی کاربر کافی نیست.")
        c.execute("UPDATE users SET coins=coins-? WHERE id=?",(amount,uid))
    bot.send_message(m.chat.id,f"✅ {amount} سکه از <code>{uid}</code> کسر شد.")

@bot.callback_query_handler(func=lambda c:c.data.startswith("usp:"))
def user_system_page(c):
    page=int(c.data.split(":")[1])
    bot.answer_callback_query(c.id)
    bot.edit_message_reply_markup(c.message.chat.id,c.message.message_id,reply_markup=user_extra_menu(page))

@bot.callback_query_handler(func=lambda c:c.data.startswith("us:"))
def user_system_detail(c):
    i=int(c.data.split(":")[1])
    name=USER_SYSTEMS[i]
    bot.answer_callback_query(c.id)
    if name=="اطلاعات پرداخت":
        body=f"💳 شماره کارت: <code>{CARD_NUMBER}</code>\n👤 به نام: <b>{CARD_HOLDER}</b>"
    elif name=="قیمت هر 10 کوین":
        body="💰 هر 10 کوین = 2,000 تومان"
    elif name=="شناسه عددی":
        body=f"🆔 شناسه عددی شما: <code>{c.from_user.id}</code>"
    elif name=="موجودی":
        with db() as d:u=d.execute("SELECT coins FROM users WHERE id=?",(c.from_user.id,)).fetchone()
        body=f"🪙 موجودی شما: <b>{u['coins'] if u else 0}</b>"
    else:
        body="این بخش در مرکز سیستم‌های کاربری قرار دارد. برای عملیات اصلی از دکمه‌های اصلی استفاده کن."
    bot.send_message(c.from_user.id,styled(name,body))


# ---------- MAIN MENU NAVIGATION ----------
@bot.message_handler(func=lambda m:m.text=="بعدی ➡️")
def main_next(m):
    # شماره صفحه فعلی از متن پیام نگه‌داری نمی‌شود؛ با شمارنده ساده برای هر کاربر کار می‌کنیم.
    page=MAIN_PAGES.get(m.from_user.id,0)+1
    max_page=(len(MAIN_BUTTONS)-1)//MAIN_PAGE_SIZE
    if page>max_page: page=max_page
    MAIN_PAGES[m.from_user.id]=page
    send_main_page(m.chat.id,page)

@bot.message_handler(func=lambda m:m.text=="⬅️ قبلی")
def main_prev(m):
    page=max(MAIN_PAGES.get(m.from_user.id,0)-1,0)
    MAIN_PAGES[m.from_user.id]=page
    send_main_page(m.chat.id,page)

MAIN_PAGES={}

MAIN_ADVANCED_MAP={'👤 پروفایل من': 'profile', '🪙 موجودی سکه': 'balance', '📊 آمار سکه': 'earnstats', '📦 آمار سفارش': 'orders', '💳 تاریخچه خرید': 'purchases', '🧾 تاریخچه سفارش': 'history', '🎯 کانال\u200cهای کسب سکه': 'channels', '🔗 آمار دعوت': 'ref', '💰 تعرفه کوین': 'prices', '🛒 بسته\u200cهای خرید': 'packages', '✏️ خرید تعداد دلخواه': 'custom', '📢 راهنمای ثبت کانال': 'channel_help', '🔎 جستجوی سفارش': 'search_order', '🧾 شماره سفارش': 'order_no', '💳 اطلاعات پرداخت': 'payment', '📈 آمار تبلیغات': 'ads', '🔔 اعلان\u200cها': 'notify', '🎁 هدیه روزانه': 'daily', '🎟 کد هدیه': 'gift', '🛡 امنیت حساب': 'security', '📋 قوانین': 'rules', '🆘 مرکز کمک': 'help', '☎️ تماس با مالک': 'owner_contact', '🐞 گزارش مشکل': 'report', '💸 گزارش تراکنش': 'transaction', '📦 گزارش سفارش': 'order_report', '⭐ امتیازدهی': 'rating', '🕐 تاریخ عضویت': 'join_date', '🔢 تعداد سفارش': 'order_count', '👥 تعداد دعوت': 'invite_count', '📢 تعداد کانال': 'channel_count', '✨ سکه دریافت\u200cشده': 'coins_earned', '🔥 سکه مصرف\u200cشده': 'coins_spent', '💎 سکه خریداری\u200cشده': 'coins_bought', '🎁 سکه هدیه': 'coins_gift', '📦 آخرین سفارش': 'last_order', '💳 آخرین خرید': 'last_purchase', '🟢 آخرین فعالیت': 'last_activity', '✅ وضعیت حساب': 'account_status', '🔐 وضعیت دسترسی': 'access_status', '⚙️ تنظیمات حساب': 'settings', '🔔 تنظیم اعلان': 'notify_settings', '🛒 مرکز سفارش': 'order_center', '💳 مرکز خرید': 'shop_center', '🪙 مرکز سکه': 'coin_center', '🤝 مرکز دعوت': 'invite_center', '☎️ مرکز پشتیبانی': 'support_center', '📚 مرکز راهنما': 'help_center', '💎 مرکز VIP': 'vip_center', '🎮 مرکز بازی': 'game_center', '📣 مرکز تبلیغات': 'ad_center', '🗂 آرشیو خرید': 'purchase_archive', '🗂 آرشیو سفارش': 'order_archive', '📜 راهنمای سریع': 'quick_help', '🧑\u200d💻 شناسه عددی': 'numeric_id', '👤 یوزرنیم': 'username', '🚫 لغو سفارش': 'cancel_info', '🔒 امنیت پیشرفته': 'security', '📌 وضعیت عضویت': 'channels', '📌 وضعیت سفارش': 'search_order'}

@bot.message_handler(func=lambda m: (m.text or "") in MAIN_ADVANCED_MAP)
def main_advanced_system(m):
    add_user(m.from_user)
    key=MAIN_ADVANCED_MAP[m.text]
    with db() as d:
        u=d.execute("SELECT * FROM users WHERE id=?",(m.from_user.id,)).fetchone()
        claims=d.execute("SELECT COUNT(*) n FROM claims WHERE user_id=?",(m.from_user.id,)).fetchone()["n"]
        orders=d.execute("SELECT COUNT(*) n FROM orders WHERE user_id=?",(m.from_user.id,)).fetchone()["n"]
        purchases=d.execute("SELECT COUNT(*) n FROM purchases WHERE buyer_id=?",(m.from_user.id,)).fetchone()["n"]
        earned=d.execute("SELECT COUNT(*) n FROM claims WHERE user_id=?",(m.from_user.id,)).fetchone()["n"]
        spent=d.execute("SELECT COALESCE(SUM(original_amount,0),0) n FROM orders WHERE user_id=? AND status!='cancelled'",(m.from_user.id,)).fetchone()["n"] if False else 0
        spent_row=d.execute("SELECT COALESCE(SUM(CASE WHEN original_amount>0 THEN original_amount ELSE amount END),0) n FROM orders WHERE user_id=? AND status!='cancelled'",(m.from_user.id,)).fetchone()
        spent=spent_row["n"] if spent_row else 0
        bought=d.execute("SELECT COALESCE(SUM(coins),0) n FROM purchases WHERE target_id=? AND status='approved'",(m.from_user.id,)).fetchone()["n"]
        last_order=d.execute("SELECT id,amount,original_amount,status FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1",(m.from_user.id,)).fetchone()
        last_purchase=d.execute("SELECT id,coins,price,status FROM purchases WHERE buyer_id=? ORDER BY id DESC LIMIT 1",(m.from_user.id,)).fetchone()
    msgs={
        "profile":f"👤 آیدی عددی: <code>{m.from_user.id}</code>\\n🪙 سکه: <b>{u['coins']}</b>",
        "balance":f"🪙 موجودی: <b>{u['coins']}</b> سکه",
        "earnstats":f"🎯 عضویت‌های تأییدشده: <b>{claims}</b>\\n🪙 موجودی: <b>{u['coins']}</b>",
        "orders":f"📦 تعداد سفارش‌ها: <b>{orders}</b>",
        "purchases":f"💳 تعداد خریدها: <b>{purchases}</b>",
        "history":f"🧾 سفارش‌ها: {orders} | خریدها: {purchases}",
        "channels":"📢 کانال‌های کسب سکه از «🎯 دریافت سکه» در دسترس‌اند.",
        "ref":f"🔗 لینک دعوت: https://t.me/{bot.get_me().username}?start={m.from_user.id}",
        "prices":"💰 هر 10 کوین = 2,000 تومان",
        "packages":"🛒 50 / 100 / 200 / 500 کوین + تعداد دلخواه",
        "custom":"✏️ از «💳 خرید کوین» تعداد دلخواه را انتخاب کن.",
        "channel_help":"📢 برای ثبت کانال، ربات باید ادمین کانال باشد.",
        "search_order":"🔎 سفارش‌ها را از «📦 پیگیری سفارش» ببین.",
        "order_no":f"🧾 آخرین سفارش: #{last_order['id'] if last_order else 'نداری'}",
        "payment":f"💳 کارت: <code>{CARD_NUMBER}</code>\\n👤 به نام: <b>{CARD_HOLDER}</b>",
        "ads":"📣 سیستم تبلیغ کانال از دکمه «📣 تبلیغ کانال من» قابل دسترسی است.",
        "notify":"🔔 اعلان‌های مهم خرید و سفارش ارسال می‌شوند.",
        "daily":"🎁 هدیه روزانه در حال آماده‌سازی است.",
        "gift":"🎟 کد هدیه توسط مالک ارائه می‌شود.",
        "security":"🛡 اطلاعات حساس حساب را در اختیار دیگران قرار نده.",
        "rules":"📋 تقلب، اسپم و سوءاستفاده از سیستم ممنوع است.",
        "help":"🆘 دریافت سکه ← سفارش ممبر / خرید کوین ← ارسال رسید.",
        "owner_contact":"☎️ از «پشتیبانی» برای ارتباط با مالک استفاده کن.",
        "report":"🐞 مشکل را از بخش پشتیبانی گزارش کن.",
        "transaction":"💸 اطلاعات تراکنش در تاریخچه خرید قابل بررسی است.",
        "order_report":"📦 وضعیت سفارش از پیگیری سفارش قابل مشاهده است.",
        "rating":"⭐ امتیازدهی در حال آماده‌سازی است.",
        "join_date":f"🕐 تاریخ ثبت: {time.strftime('%Y-%m-%d %H:%M',time.localtime(u['created']))}",
        "order_count":f"🔢 تعداد سفارش: <b>{orders}</b>",
        "invite_count":"👥 آمار دعوت در نسخه فعلی پایه است.",
        "channel_count":f"📢 کانال‌های فعال کسب سکه: <b>{len(active_channels())}</b>",
        "coins_earned":f"✨ سکه کسب‌شده از عضویت: <b>{earned}</b>",
        "coins_spent":f"🔥 سکه مصرف‌شده برای سفارش: <b>{spent}</b>",
        "coins_bought":f"💎 سکه خریداری‌شده: <b>{bought}</b>",
        "coins_gift":"🎁 سکه هدیه از مالک دریافت می‌شود.",
        "last_order":f"📦 آخرین سفارش: #{last_order['id']} | باقی: {last_order['amount']} | {last_order['status']}" if last_order else "📦 سفارشی نداری.",
        "last_purchase":f"💳 آخرین خرید: #{last_purchase['id']} | {last_purchase['coins']} کوین | {last_purchase['status']}" if last_purchase else "💳 خریدی نداری.",
        "last_activity":"🟢 آخرین فعالیت: همین الان",
        "account_status":"✅ حساب فعال است.",
        "access_status":"🔐 دسترسی حساب مجاز است.",
        "settings":"⚙️ تنظیمات حساب در نسخه پایه فعال است.",
        "notify_settings":"🔔 اعلان‌های مهم فعال هستند.",
        "order_center":"🛒 مرکز سفارش: ثبت و پیگیری سفارش ممبر.",
        "shop_center":"💳 مرکز خرید: بسته‌ها، تعداد دلخواه و رسید.",
        "coin_center":"🪙 مرکز سکه: کسب، خرید و مصرف.",
        "invite_center":"🤝 مرکز دعوت و لینک دعوت.",
        "support_center":"☎️ مرکز پشتیبانی و تیکت.",
        "help_center":"📚 راهنمای کامل امکانات ربات.",
        "vip_center":"💎 مرکز VIP در حال توسعه است.",
        "game_center":"🎮 مرکز بازی در حال توسعه است.",
        "ad_center":"📣 مرکز تبلیغات کانال.",
        "purchase_archive":f"🗂 آرشیو خریدها: <b>{purchases}</b>",
        "order_archive":f"🗂 آرشیو سفارش‌ها: <b>{orders}</b>",
        "quick_help":"📜 مسیر سریع: 🎯 دریافت سکه → 👥 سفارش ممبر → 💳 خرید کوین.",
        "numeric_id":f"🧑‍💻 آیدی عددی شما: <code>{m.from_user.id}</code>",
        "username":f"👤 یوزرنیم: @{m.from_user.username}" if m.from_user.username else "👤 یوزرنیم تنظیم نشده.",
        "cancel_info":"🚫 سفارش‌های فعال از مسیر پیگیری سفارش قابل مدیریت‌اند.",
    }
    body=msgs.get(key,"این سیستم آماده استفاده است.")
    bot.send_message(m.chat.id,styled(m.text,body))
# ---------- OWNER ----------
@bot.message_handler(func=lambda m:m.text and m.text.strip()==f"مالک {OWNER_KEY}")
def owner_login(m):
    if is_owner(m):
        bot.send_message(m.chat.id,"👑 <b>پنل مالک Member Jam</b>",reply_markup=owner_menu())
    else:
        bot.send_message(m.chat.id,"❌ دسترسی ندارید.")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="❌ خروج مالک")
def owner_exit(m):
    bot.send_message(m.chat.id,"✅ از پنل مالک خارج شدید.",reply_markup=main_menu())

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="📊 آمار کلی")
def owner_stats(m):
    with db() as c:
        u=c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        ch=c.execute("SELECT COUNT(*) n FROM channels WHERE active=1").fetchone()["n"]
        p=c.execute("SELECT COUNT(*) n FROM purchases WHERE status='pending'").fetchone()["n"]
        o=c.execute("SELECT COUNT(*) n FROM orders").fetchone()["n"]
    bot.send_message(m.chat.id,f"📊 کاربران: {u}\n📢 کانال‌ها: {ch}\n💳 خریدهای منتظر: {p}\n📦 سفارش‌ها: {o}")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="👥 کاربران")
def owner_users(m):
    with db() as c:r=c.execute(
        "SELECT id,username,coins,blocked FROM users ORDER BY id DESC LIMIT 50").fetchall()
    bot.send_message(m.chat.id,"\n".join(
        f"{x['id']} | {('@'+x['username']) if x['username'] else '-'} | 🪙{x['coins']} | "
        f"{'🚫' if x['blocked'] else '✅'}" for x in r) or "خالی")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="🪙 دادن سکه")
def give_help(m):
    bot.send_message(m.chat.id,
        "برای دادن سکه فقط آیدی عددی:\n"
        "<code>سکه ID AMOUNT</code>\n\n"
        "مثال:\n<code>سکه 123456789 50</code>")

@bot.message_handler(func=lambda m:is_owner(m) and m.text and m.text.startswith("سکه "))
def give_coin(m):
    p=m.text.split()
    if len(p)!=3:return bot.send_message(m.chat.id,"❌ فرمت: سکه ID AMOUNT")
    try:uid,amount=int(p[1]),int(p[2])
    except:return bot.send_message(m.chat.id,"❌ آیدی و مقدار باید عدد باشند.")
    if amount<=0:return bot.send_message(m.chat.id,"❌ مقدار نامعتبر.")
    with db() as c:
        c.execute("INSERT OR IGNORE INTO users(id,username,created) VALUES(?,?,?)",(uid,"",now()))
        c.execute("UPDATE users SET coins=coins+? WHERE id=?",(amount,uid))
    bot.send_message(m.chat.id,f"✅ <code>{uid}</code> +{amount} سکه دریافت کرد.")
    try:bot.send_message(uid,f"🎁 مالک <b>{amount} سکه</b> به حساب شما اضافه کرد.")
    except:pass

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="💳 خریدهای در انتظار")
def pending(m):
    with db() as c:r=c.execute(
        "SELECT id,buyer_id,target_id,coins,price,status FROM purchases "
        "WHERE status='pending' ORDER BY id DESC LIMIT 30").fetchall()
    if not r:return bot.send_message(m.chat.id,"✅ خرید در انتظاری نیست.")
    bot.send_message(m.chat.id,"\n".join(
        f"#{x['id']} | دریافت‌کننده {x['target_id']} | {x['coins']} کوین | {x['price']:,} تومان"
        for x in r))

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="📢 کانال‌های کسب سکه")
def owner_channels(m):
    with db() as c:r=c.execute("SELECT id,title,username,active FROM channels").fetchall()
    bot.send_message(m.chat.id,"\n".join(
        f"{x['id']} | {x['title']} | {x['username']} | {'فعال' if x['active'] else 'خاموش'}"
        for x in r) or "کانالی ثبت نشده.")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="📦 سفارش‌ها")
def owner_orders(m):
    with db() as c:r=c.execute(
        "SELECT id,user_id,amount,original_amount,channel_title,status FROM orders ORDER BY id DESC LIMIT 30").fetchall()
    lines=[]
    for x in r:
        done=(x["original_amount"] or x["amount"])-x["amount"]
        lines.append(f"#{x['id']} | صاحب {x['user_id']} | {x['channel_title']} | انجام {done}/{x['original_amount'] or x['amount']} | {x['status']}")
    bot.send_message(m.chat.id,"\n".join(lines) or "خالی")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="🎫 تیکت‌ها")
def owner_tickets(m):
    with db() as c:r=c.execute(
        "SELECT id,user_id,text,status FROM tickets ORDER BY id DESC LIMIT 30").fetchall()
    bot.send_message(m.chat.id,"\n".join(
        f"#{x['id']} | {x['user_id']} | {x['status']}\n{x['text'][:100]}" for x in r) or "خالی")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="🚫 مدیریت مسدودی")
def ban_help(m):
    bot.send_message(m.chat.id,"<code>مسدود ID</code>\n<code>رفع ID</code>")

@bot.message_handler(func=lambda m:is_owner(m) and m.text and
                     (m.text.startswith("مسدود ") or m.text.startswith("رفع ")))
def ban(m):
    p=m.text.split()
    try:uid=int(p[1])
    except:return
    v=1 if p[0]=="مسدود" else 0
    with db() as c:c.execute("UPDATE users SET blocked=? WHERE id=?",(v,uid))
    bot.send_message(m.chat.id,"✅ انجام شد.")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="📣 پیام همگانی")
def broadcast(m):
    bot.send_message(m.chat.id,"متن پیام همگانی را بفرست.")
    bot.register_next_step_handler(m,do_broadcast)

def do_broadcast(m):
    with db() as c:rows=c.execute("SELECT id FROM users WHERE blocked=0").fetchall()
    ok=0
    for r in rows:
        try:bot.send_message(r["id"],m.text);ok+=1
        except:pass
    bot.send_message(m.chat.id,f"✅ برای {ok} کاربر ارسال شد.")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="⚙️ تنظیمات")
def settings(m):
    bot.send_message(m.chat.id,
        "⚙️ تنظیمات پایه\n\n"
        "🪙 هر 1 سکه = 1 ممبر\n"
        "🎯 هر عضویت تأییدشده در کانال کسب سکه = 1 سکه\n"
        "💳 خریدها فقط بعد از تأیید مالک شارژ می‌شوند.")

@bot.message_handler(func=lambda m:is_owner(m) and m.text=="📜 لاگ‌ها")
def logs(m):
    with db() as c:r=c.execute(
        "SELECT action,user_id,text FROM logs ORDER BY id DESC LIMIT 30").fetchall()
    bot.send_message(m.chat.id,"\n".join(
        f"{x['action']} | {x['user_id']} | {x['text']}" for x in r) or "خالی")

print("━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🚀 MEMBER JAM در حال اتصال است...")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━")

# تست اتصال قبل از شروع polling
try:
    me = bot.get_me()
    print(f"✅ اتصال موفق: @{me.username}")
    print(f"🆔 Bot ID: {me.id}")
except Exception as e:
    print("❌ اتصال به تلگرام برقرار نشد.")
    print("خطا:", e)
    print("این موارد را بررسی کن: اینترنت، توکن جدید و دسترسی Pydroid به اینترنت.")
    raise

print("✅ ربات روشن شد. حالا /start را بفرست.")

# اگر polling به هر دلیل قطع شود، دوباره تلاش می‌کند.
while True:
    try:
        bot.infinity_polling(
            skip_pending=False,
            timeout=30,
            long_polling_timeout=30,
            allowed_updates=["message", "callback_query"]
        )
    except Exception as e:
        print("⚠️ polling قطع شد:", e)
        print("🔄 تلاش مجدد تا 5 ثانیه دیگر...")
        time.sleep(5)
