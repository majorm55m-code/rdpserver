# -*- coding: utf-8 -*-
import os, sys, sqlite3, psutil, asyncio, subprocess, signal, shutil, json
from datetime import datetime, timedelta
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler,
    MessageHandler, filters, ContextTypes
)

TOKEN = "8879965742:AAH6t_1lteGgrJ14f-cbq0IwSQRtAs5yZeY"
OWNER_ID = 6330128098
BASE_DIR = Path("/app/data/users") if os.path.exists("/app") else Path("./data/users")
BASE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path("/app/data/db.sqlite") if os.path.exists("/app") else Path("./data/db.sqlite")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE, username TEXT, full_name TEXT, is_active INTEGER DEFAULT 0, ram_limit INTEGER DEFAULT 512, disk_limit INTEGER DEFAULT 100, expiry_date TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'pending')")
    c.execute("CREATE TABLE IF NOT EXISTS bots (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, bot_name TEXT, status TEXT DEFAULT 'stopped', pid INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()

init_db()

def db_conn():
    return sqlite3.connect(str(DB_PATH))

def get_user(user_id):
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def add_user(user_id, username, full_name):
    conn = db_conn()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (telegram_id, username, full_name) VALUES (?,?,?)", (user_id, username, full_name))
    conn.commit()
    conn.close()

def update_user_status(user_id, status, ram=None, disk=None, days=None):
    conn = db_conn()
    c = conn.cursor()
    expiry = None
    if days:
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
    fields = ["status=?"]
    vals = [status]
    if ram is not None:
        fields.append("ram_limit=?")
        vals.append(ram)
    if disk is not None:
        fields.append("disk_limit=?")
        vals.append(disk)
    if expiry:
        fields.append("expiry_date=?")
        vals.append(expiry)
    vals.append(user_id)
    c.execute("UPDATE users SET " + ",".join(fields) + " WHERE telegram_id=?", tuple(vals))
    conn.commit()
    conn.close()

def get_system_info():
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    cpu = psutil.cpu_percent(interval=1)
    return {"cpu": cpu, "ram_used": mem.used // (1024**2), "ram_total": mem.total // (1024**2), "ram_percent": mem.percent, "disk_used": disk.used // (1024**2), "disk_total": disk.total // (1024**2), "disk_percent": disk.percent}

def get_user_dir(user_id):
    d = BASE_DIR / str(user_id)
    d.mkdir(exist_ok=True)
    return d

running_bots = {}

def start_bot_process(user_id):
    user_dir = get_user_dir(user_id)
    bot_file = user_dir / "bot.py"
    if not bot_file.exists():
        return False, "bot.py not found"
    if user_id in running_bots:
        try:
            running_bots[user_id].terminate()
            running_bots[user_id].wait(timeout=5)
        except:
            pass
        del running_bots[user_id]
    req_file = user_dir / "requirements.txt"
    if req_file.exists():
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_file)], capture_output=True, timeout=60, cwd=str(user_dir))
        except:
            pass
    env = os.environ.copy()
    env["USER_ID"] = str(user_id)
    env["USER_DIR"] = str(user_dir)
    proc = subprocess.Popen([sys.executable, str(bot_file)], cwd=str(user_dir), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    running_bots[user_id] = proc
    conn = db_conn()
    c = conn.cursor()
    c.execute("UPDATE bots SET status='running', pid=? WHERE user_id=?", (proc.pid, user_id))
    if c.rowcount == 0:
        c.execute("INSERT INTO bots (user_id, bot_name, status, pid) VALUES (?, 'main', 'running', ?)", (user_id, proc.pid))
    conn.commit()
    conn.close()
    return True, "Running PID: " + str(proc.pid)

def stop_bot_process(user_id):
    if user_id in running_bots:
        proc = running_bots[user_id]
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except:
            proc.kill()
        del running_bots[user_id]
        conn = db_conn()
        c = conn.cursor()
        c.execute("UPDATE bots SET status='stopped', pid=0 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return True, "Stopped"
    return False, "Not running"

def main_keyboard(user_id):
    is_owner = user_id == OWNER_ID
    buttons = [
        [InlineKeyboardButton("Control Panel", callback_data="panel")],
        [InlineKeyboardButton("My Files", callback_data="files"), InlineKeyboardButton("Hosting Info", callback_data="info")],
        [InlineKeyboardButton("Bot Control", callback_data="bot_control")],
        [InlineKeyboardButton("Upload Files", callback_data="upload_menu")],
    ]
    if is_owner:
        buttons.append([InlineKeyboardButton("Owner Panel", callback_data="admin")])
    return InlineKeyboardMarkup(buttons)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Users List", callback_data="admin_users")],
        [InlineKeyboardButton("Activate User", callback_data="admin_activate")],
        [InlineKeyboardButton("System Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("Back", callback_data="back_main")]
    ])

def back_button(data="back_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data=data)]])

# ─── HANDLERS ───
async def start_cmd(update, context):
    user = update.effective_user
    add_user(user.id, user.username or "", user.full_name)
    text = "Welcome " + user.full_name + "!\n\nRailway Hosting Manager Bot\n\nHost your Python bots 24/7\nManage files, RAM, storage\n\nUse buttons below:"
    await update.message.reply_text(text, reply_markup=main_keyboard(user.id))

async def panel_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    u = get_user(user_id)
    if not u or u[4] == 0:
        await query.edit_message_text("Account not activated. Contact owner.", reply_markup=back_button())
        return
    status = "Active" if u[4] else "Inactive"
    expiry = u[8] or "Not set"
    ram = u[5] or 512
    disk = u[6] or 100
    text = "<b>Control Panel</b>\n\nUser: " + str(u[3]) + "\nStatus: " + status + "\nExpiry: " + str(expiry) + "\nRAM: " + str(ram) + " MB\nDisk: " + str(disk) + " MB"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start Bot", callback_data="bot_start"), InlineKeyboardButton("Stop Bot", callback_data="bot_stop")],
        [InlineKeyboardButton("Restart", callback_data="bot_restart")],
        [InlineKeyboardButton("Open Files", callback_data="files")],
        [InlineKeyboardButton("Back", callback_data="back_main")]
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

async def bot_control_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    u = get_user(user_id)
    if not u or u[4] == 0:
        await query.edit_message_text("Not activated", reply_markup=back_button())
        return
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT status, pid FROM bots WHERE user_id=?", (user_id,))
    bot_row = c.fetchone()
    conn.close()
    status = bot_row[0] if bot_row else "stopped"
    pid = bot_row[1] if bot_row else 0
    text = "<b>Bot Control</b>\n\nStatus: " + str(status) + "\nPID: " + str(pid)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Start", callback_data="bot_start"), InlineKeyboardButton("Stop", callback_data="bot_stop")],
        [InlineKeyboardButton("Restart", callback_data="bot_restart")],
        [InlineKeyboardButton("Back", callback_data="panel")]
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

async def bot_start_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    ok, msg = start_bot_process(user_id)
    await query.edit_message_text(("OK: " if ok else "Error: ") + msg, reply_markup=back_button("bot_control"))

async def bot_stop_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    ok, msg = stop_bot_process(user_id)
    await query.edit_message_text(("OK: " if ok else "Error: ") + msg, reply_markup=back_button("bot_control"))

async def bot_restart_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    stop_bot_process(user_id)
    await asyncio.sleep(1)
    ok, msg = start_bot_process(user_id)
    await query.edit_message_text("Restart: " + msg, reply_markup=back_button("bot_control"))

async def info_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    u = get_user(user_id)
    if not u or u[4] == 0:
        await query.edit_message_text("Not activated", reply_markup=back_button())
        return
    info = get_system_info()
    user_dir = get_user_dir(user_id)
    user_size = sum(f.stat().st_size for f in user_dir.rglob("*") if f.is_file()) // (1024**2)
    text = "<b>Hosting Info</b>\n\n<b>System:</b>\nCPU: " + str(info['cpu']) + "%\nRAM: " + str(info['ram_used']) + "/" + str(info['ram_total']) + " MB (" + str(info['ram_percent']) + "%)\nDisk: " + str(info['disk_used']) + "/" + str(info['disk_total']) + " MB (" + str(info['disk_percent']) + "%)\n\n<b>Your Usage:</b>\nFolder: " + str(user_dir) + "\nSize: " + str(user_size) + " MB / " + str(u[6]) + " MB limit"
    await query.edit_message_text(text, reply_markup=back_button("panel"), parse_mode="HTML")

async def files_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    u = get_user(user_id)
    if not u or u[4] == 0:
        await query.edit_message_text("Not activated", reply_markup=back_button())
        return
    user_dir = get_user_dir(user_id)
    files = list(user_dir.iterdir())
    if not files:
        text = "Your folder is empty."
    else:
        text = "<b>Your Files:</b>"
        for f in files:
            size = f.stat().st_size if f.is_file() else 0
            text += "\n" + f.name + " (" + str(size) + " bytes)"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Delete All", callback_data="del_all")],
        [InlineKeyboardButton("Upload Files", callback_data="upload_menu")],
        [InlineKeyboardButton("Back", callback_data="panel")]
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

async def del_all_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user_dir = get_user_dir(user_id)
    for f in user_dir.iterdir():
        if f.is_file():
            f.unlink()
        elif f.is_dir():
            shutil.rmtree(f)
    await query.edit_message_text("All files deleted.", reply_markup=back_button("files"))

async def admin_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await query.edit_message_text("Owner only.", reply_markup=back_button())
        return
    await query.edit_message_text("<b>Owner Panel</b>", reply_markup=admin_keyboard(), parse_mode="HTML")

async def admin_stats_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    info = get_system_info()
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_active=1")
    active_users = c.fetchone()[0]
    conn.close()
    text = "<b>System Stats</b>\n\nCPU: " + str(info['cpu']) + "%\nRAM: " + str(info['ram_used']) + "/" + str(info['ram_total']) + " MB\nDisk: " + str(info['disk_used']) + "/" + str(info['disk_total']) + " MB\n\nUsers: " + str(total_users) + "\nActive: " + str(active_users)
    await query.edit_message_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")

async def admin_users_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    conn = db_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id, full_name, is_active, status, ram_limit, disk_limit, expiry_date FROM users")
    rows = c.fetchall()
    conn.close()
    if not rows:
        text = "No users yet."
    else:
        text = "<b>Users:</b>"
        for r in rows:
            text += "\nID: " + str(r[0]) + " | " + str(r[1]) + " | Active:" + str(r[2]) + " | " + str(r[3]) + " | RAM:" + str(r[4]) + " | Disk:" + str(r[5]) + " | Exp:" + str(r[6])
    await query.edit_message_text(text[:4000], reply_markup=admin_keyboard(), parse_mode="HTML")

# ─── ADMIN ACTIVATE CONVERSATION ───
ASK_USER_ID, ASK_RAM, ASK_DISK, ASK_DAYS = range(4)

async def admin_activate_start(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return ConversationHandler.END
    await query.edit_message_text("Enter user Telegram ID to activate:")
    return ASK_USER_ID

async def admin_get_user_id(update, context):
    text = update.message.text.strip()
    try:
        target_id = int(text)
    except:
        await update.message.reply_text("Invalid ID. Enter numbers only:")
        return ASK_USER_ID
    context.user_data["target_id"] = target_id
    await update.message.reply_text("Enter RAM limit in MB (e.g. 512):")
    return ASK_RAM

async def admin_get_ram(update, context):
    text = update.message.text.strip()
    try:
        ram = int(text)
    except:
        await update.message.reply_text("Invalid number. Enter RAM in MB:")
        return ASK_RAM
    context.user_data["ram"] = ram
    await update.message.reply_text("Enter Disk limit in MB (e.g. 100):")
    return ASK_DISK

async def admin_get_disk(update, context):
    text = update.message.text.strip()
    try:
        disk = int(text)
    except:
        await update.message.reply_text("Invalid number. Enter Disk in MB:")
        return ASK_DISK
    context.user_data["disk"] = disk
    await update.message.reply_text("Enter days of activation (e.g. 30):")
    return ASK_DAYS

async def admin_get_days(update, context):
    text = update.message.text.strip()
    try:
        days = int(text)
    except:
        await update.message.reply_text("Invalid number. Enter days:")
        return ASK_DAYS
    target_id = context.user_data["target_id"]
    ram = context.user_data["ram"]
    disk = context.user_data["disk"]
    update_user_status(target_id, "active", ram=ram, disk=disk, days=days)
    conn = db_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_active=1 WHERE telegram_id=?", (target_id,))
    conn.commit()
    conn.close()
    await update.message.reply_text("User " + str(target_id) + " activated!\nRAM: " + str(ram) + " MB\nDisk: " + str(disk) + " MB\nDays: " + str(days), reply_markup=admin_keyboard())
    return ConversationHandler.END

async def cancel_conv(update, context):
    await update.message.reply_text("Cancelled.", reply_markup=admin_keyboard())
    return ConversationHandler.END

# ─── UPLOAD CONVERSATION ───
UPLOAD_SELECT, UPLOAD_FILE = range(2)

async def upload_menu_callback(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    u = get_user(user_id)
    if not u or u[4] == 0:
        await query.edit_message_text("Not activated", reply_markup=back_button())
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Upload bot.py", callback_data="upload_botpy")],
        [InlineKeyboardButton("Upload requirements.txt", callback_data="upload_req")],
        [InlineKeyboardButton("Upload any file", callback_data="upload_any")],
        [InlineKeyboardButton("Back", callback_data="files")]
    ])
    await query.edit_message_text("Select upload type:", reply_markup=kb)
    return UPLOAD_SELECT

async def upload_select_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "upload_botpy":
        context.user_data["upload_target"] = "bot.py"
    elif data == "upload_req":
        context.user_data["upload_target"] = "requirements.txt"
    else:
        context.user_data["upload_target"] = "any"
    await query.edit_message_text("Send the file now (as document):")
    return UPLOAD_FILE

async def upload_file_receive(update, context):
    user_id = update.effective_user.id
    target = context.user_data.get("upload_target", "any")
    user_dir = get_user_dir(user_id)
    if update.message.document:
        file = await update.message.document.get_file()
        if target == "bot.py":
            dest = user_dir / "bot.py"
        elif target == "requirements.txt":
            dest = user_dir / "requirements.txt"
        else:
            dest = user_dir / update.message.document.file_name
        await file.download_to_drive(str(dest))
        await update.message.reply_text("Saved: " + dest.name, reply_markup=back_button("files"))
    elif update.message.text:
        if target == "bot.py":
            dest = user_dir / "bot.py"
        elif target == "requirements.txt":
            dest = user_dir / "requirements.txt"
        else:
            dest = user_dir / "file.txt"
        with open(dest, "w", encoding="utf-8") as f:
            f.write(update.message.text)
        await update.message.reply_text("Saved: " + dest.name, reply_markup=back_button("files"))
    else:
        await update.message.reply_text("Send as document please.", reply_markup=back_button("files"))
    return ConversationHandler.END

async def back_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    if data == "back_main":
        await query.edit_message_text("Main Menu", reply_markup=main_keyboard(user_id))
    elif data == "panel":
        await panel_callback(update, context)
    elif data == "files":
        await files_callback(update, context)
    elif data == "bot_control":
        await bot_control_callback(update, context)
    elif data == "admin":
        await admin_callback(update, context)

# ─── MAIN ───
def main():
    app = Application.builder().token(TOKEN).build()

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_activate_start, pattern="^admin_activate$")],
        states={
            ASK_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_user_id)],
            ASK_RAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_ram)],
            ASK_DISK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_disk)],
            ASK_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_days)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )

    upload_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_menu_callback, pattern="^upload_menu$")],
        states={
            UPLOAD_SELECT: [CallbackQueryHandler(upload_select_callback, pattern="^upload_")],
            UPLOAD_FILE: [MessageHandler(filters.TEXT | filters.Document.ALL, upload_file_receive)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(admin_conv)
    app.add_handler(upload_conv)

    app.add_handler(CallbackQueryHandler(panel_callback, pattern="^panel$"))
    app.add_handler(CallbackQueryHandler(bot_control_callback, pattern="^bot_control$"))
    app.add_handler(CallbackQueryHandler(bot_start_callback, pattern="^bot_start$"))
    app.add_handler(CallbackQueryHandler(bot_stop_callback, pattern="^bot_stop$"))
    app.add_handler(CallbackQueryHandler(bot_restart_callback, pattern="^bot_restart$"))
    app.add_handler(CallbackQueryHandler(info_callback, pattern="^info$"))
    app.add_handler(CallbackQueryHandler(files_callback, pattern="^files$"))
    app.add_handler(CallbackQueryHandler(del_all_callback, pattern="^del_all$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin$"))
    app.add_handler(CallbackQueryHandler(admin_stats_callback, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(back_callback, pattern="^back_|^panel$|^files$|^bot_control$|^admin$"))

    print("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
