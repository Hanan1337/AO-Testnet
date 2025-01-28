import logging
import os
import time
import csv
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
    TypeHandler
)

# ... [Bagian yang sama sampai ke CSV_FILE] ...

# Konfigurasi CSV
CSV_FILE = "airdropbot.csv"
CSV_COLUMNS = ['Nama', 'Twitter', 'Discord', 'Telegram', 'Link', 'Type', 'Deadline']

# States baru
NAMA, TWITTER, DISCORD, TELEGRAM, LINK, TYPE, DEADLINE = range(7)

# ... [Bagian yang sama sampai ke init_csv] ...

def init_csv():
    if not Path(CSV_FILE).exists():
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)

def append_to_csv(data):
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(data)

# ... [Bagian yang sama sampai ke get_link] ...

async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    if user_input == 'Skip':
        context.user_data['link'] = '-'
    else:
        if not is_valid_url(user_input):
            await update.message.reply_text(
                "❌ Format URL Airdrop tidak valid! Ketik URL yang benar atau 'Skip'",
                reply_markup=ReplyKeyboardMarkup([['Skip']], resize_keyboard=True)
            )
            return LINK
        context.user_data['link'] = user_input
    
    reply_keyboard = [
        ['Galxe', 'Testnet', 'Layer3'],
        ['Waitlist', 'Node', 'Social Task']
    ]
    await update.message.reply_text(
        'Pilih TYPE AIRDROP:',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, 
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return TYPE

# Tambah state deadline
async def get_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['type'] = update.message.text
    
    reply_keyboard = [['Skip']]
    await update.message.reply_text(
        'Masukkan DEADLINE (DD-MM-YYYY HH:mm) atau Skip:',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return DEADLINE

async def save_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    # Parse deadline
    if user_input != 'Skip':
        try:
            deadline = datetime.strptime(user_input, "%d-%m-%Y %H:%M")
            context.user_data['deadline'] = deadline.strftime("%d-%m-%Y %H:%M")
        except ValueError:
            await update.message.reply_text(
                "❌ Format deadline salah! Gunakan DD-MM-YYYY HH:mm atau Skip"
            )
            return DEADLINE
    else:
        context.user_data['deadline'] = '-'
    
    try:
        row = [
            context.user_data['nama'],
            context.user_data['twitter'],
            context.user_data['discord'],
            context.user_data['telegram'],
            context.user_data['link'],
            context.user_data['type'],
            context.user_data['deadline']
        ]
        append_to_csv(row)
        await update.message.reply_text('✅ Data berhasil disimpan!')
    except Exception as e:
        logger.exception("Error saving to CSV:")
        await update.message.reply_text('🔥 Error sistem! Hubungi admin')
    
    return ConversationHandler.END

# Fungsi reminder
async def check_deadlines(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    records = read_csv()
    
    for record in records:
        if record['Deadline'] != '-':
            try:
                deadline = datetime.strptime(record['Deadline'], "%d-%m-%Y %H:%M")
                time_diff = deadline - now
                
                if timedelta(0) < time_diff < timedelta(hours=24):
                    message = (
                        f"⏳ DEADLINE MENDEKAT!\n\n"
                        f"📛 {record['Nama']}\n"
                        f"🔗 {record['Link']}\n"
                        f"⏰ Tersisa {time_diff.seconds//3600} jam"
                    )
                    await context.bot.send_message(
                        chat_id=context.job.chat_id,
                        text=message
                    )
            except:
                continue

async def periodic_reminder(context: ContextTypes.DEFAULT_TYPE):
    records = read_csv()
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"📌 Periodic Reminder!\nTotal Airdrop Aktif: {len(records)}"
    )

async def daily_summary(context: ContextTypes.DEFAULT_TYPE):
    records = read_csv()
    upcoming = sum(1 for r in records if r['Deadline'] != '-')
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"📊 Laporan Harian\n• Total: {len(records)}\n• Deadline Mendatang: {upcoming}"
    )

async def weekly_summary(context: ContextTypes.DEFAULT_TYPE):
    records = read_csv()
    weekly_stats = {}
    for r in records:
        weekly_stats[r['Type']] = weekly_stats.get(r['Type'], 0) + 1
    
    stats_text = "\n".join([f"• {k}: {v}" for k,v in weekly_stats.items()])
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"📈 Laporan Mingguan\n{stats_text}"
    )

# Command handler baru
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    scheduler = context.job_queue.scheduler
    
    # Hapus job lama jika ada
    if 'jobs' in context.chat_data:
        for job in context.chat_data['jobs']:
            job.remove()
    
    # Buat job baru
    jobs = [
        scheduler.add_job(daily_summary, 'cron', hour=9, args=[context], id=f"daily_{chat_id}"),
        scheduler.add_job(weekly_summary, 'cron', day_of_week='mon', hour=9, args=[context], id=f"weekly_{chat_id}"),
        scheduler.add_job(check_deadlines, 'interval', hours=6, args=[context], id=f"deadline_{chat_id}"),
        scheduler.add_job(periodic_reminder, 'interval', hours=4, args=[context], id=f"periodic_{chat_id}")
    ]
    
    context.chat_data['jobs'] = jobs
    await update.message.reply_text("🔔 Reminder aktif!\n• Daily 09:00\n• Weekly Senin 09:00\n• Cek deadline tiap 6 jam\n• Periodic tiap 4 jam")

# Di main() tambahkan scheduler
def main():
    init_csv()
    application = Application.builder().token(TOKEN).build()
    scheduler = AsyncIOScheduler()
    scheduler.start()

    # Update conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAMA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nama)],
            TWITTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_twitter)],
            DISCORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_discord)],
            TELEGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_telegram)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link)],
            TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_type)],
            DEADLINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_data)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=300
    )

    # Tambah handler baru
    application.add_handler(CommandHandler('reminder', set_reminder))
    
    # ... [Bagian lainnya tetap sama] ...

    application.run_polling()
