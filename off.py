import logging
import os
import time
import csv
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

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

# Load environment variables
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

# Konfigurasi CSV
CSV_FILE = "airdropbot.csv"

# States untuk conversation handler
NAMA, TWITTER, DISCORD, TELEGRAM, LINK, TYPE = range(6)

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# CSV Functions
def init_csv():
    if not Path(CSV_FILE).exists():
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Nama', 'Twitter', 'Discord', 'Telegram', 'Link', 'Type'])

def append_to_csv(data):
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(data)

def read_csv():
    with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

# Utility functions
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

async def limit_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get('last_request'):
        elapsed = time.time() - context.user_data['last_request']
        if elapsed < 5:
            await update.message.reply_text("⏳ Mohon tunggu 5 detik antar request")
            return
    context.user_data['last_request'] = time.time()

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [['Skip']]
    await update.message.reply_text(
        'Halo! Mari kita tambahkan airdrop baru. Silakan masukkan NAMA:',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, 
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return NAMA

async def get_nama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    context.user_data['nama'] = user_input if user_input != 'Skip' else '-'
    
    reply_keyboard = [['Skip']]
    await update.message.reply_text(
        'Masukkan LINK TWITTER:',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return TWITTER

async def get_twitter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    if user_input == 'Skip':
        context.user_data['twitter'] = '-'
    else:
        if not is_valid_url(user_input):
            await update.message.reply_text(
                "❌ Format URL Twitter tidak valid! Ketik URL yang benar atau 'Skip'",
                reply_markup=ReplyKeyboardMarkup([['Skip']], resize_keyboard=True)
            )
            return TWITTER
        context.user_data['twitter'] = user_input
    
    reply_keyboard = [['Skip']]
    await update.message.reply_text(
        'Masukkan LINK DISCORD:',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return DISCORD

async def get_discord(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    if user_input == 'Skip':
        context.user_data['discord'] = '-'
    else:
        if not is_valid_url(user_input):
            await update.message.reply_text(
                "❌ Format URL Discord tidak valid! Ketik URL yang benar atau 'Skip'",
                reply_markup=ReplyKeyboardMarkup([['Skip']], resize_keyboard=True)
            )
            return DISCORD
        context.user_data['discord'] = user_input
    
    reply_keyboard = [['Skip']]
    await update.message.reply_text(
        'Masukkan LINK TELEGRAM:',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return TELEGRAM

async def get_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    if user_input == 'Skip':
        context.user_data['telegram'] = '-'
    else:
        if not is_valid_url(user_input):
            await update.message.reply_text(
                "❌ Format URL Telegram tidak valid! Ketik URL yang benar atau 'Skip'",
                reply_markup=ReplyKeyboardMarkup([['Skip']], resize_keyboard=True)
            )
            return TELEGRAM
        context.user_data['telegram'] = user_input
    
    reply_keyboard = [['Skip']]
    await update.message.reply_text(
        'Masukkan LINK AIRDROP:',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    )
    return LINK

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

async def save_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['type'] = update.message.text
    
    try:
        row = [
            context.user_data['nama'],
            context.user_data['twitter'],
            context.user_data['discord'],
            context.user_data['telegram'],
            context.user_data['link'],
            context.user_data['type']
        ]
        append_to_csv(row)
        await update.message.reply_text('✅ Data berhasil disimpan!')
    except Exception as e:
        logger.exception("Error saving to CSV:")
        await update.message.reply_text('🔥 Error sistem! Hubungi admin')
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Input dibatalkan')
    return ConversationHandler.END

async def list_airdrops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        records = read_csv()
        
        if not records:
            await update.message.reply_text("📭 Database airdrop kosong")
            return
            
        response = "📋 <b>DAFTAR AIRDROP</b>\n\n"
        for idx, record in enumerate(records, 1):
            entry = (
                f"━━━━━━━━━━━━━━━━━\n"
                f"🆔 <b>Entry {idx}</b>\n\n"
                f"<b>Nama:</b> {record['Nama']}\n"
                f"<b>Twitter:</b> {record['Twitter']}\n"
                f"<b>Discord:</b> {record['Discord']}\n"
                f"<b>Telegram:</b> {record['Telegram']}\n"
                f"<b>Link:</b> {record['Link']}\n"
                f"<b>Type:</b> {record['Type']}\n"
            )
            
            if len(response + entry) > 4000:
                await update.message.reply_html(response)
                response = "📋 <b>DAFTAR AIRDROP</b> (Lanjutan)\n\n"
            
            response += entry

        if response:
            await update.message.reply_html(response)
            
    except Exception as e:
        logger.error(f"List error: {e}")
        await update.message.reply_text("🔧 Gagal mengambil data, coba lagi nanti")

async def search_airdrops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        keyword = update.message.text.split(' ', 1)[1].lower()
    except IndexError:
        await update.message.reply_text("❌ Format pencarian salah\nContoh: /search Bitcoin")
        return
    
    try:
        records = read_csv()
        
        results = []
        for record in records:
            if (keyword in record['Nama'].lower() or 
                keyword in record['Type'].lower()):
                results.append(record)
        
        if not results:
            await update.message.reply_text(f"🔍 Tidak ditemukan airdrop dengan kata kunci '{keyword}'")
            return
            
        response = f"🔍 <b>HASIL PENCARIAN '{keyword.upper()}':</b>\n\n"
        for result in results:
            entry = (
                f"━━━━━━━━━━━━━━━━━\n"
                f"<b>Nama:</b> {result['Nama']}\n"
                f"<b>Twitter:</b> {result['Twitter']}\n"
                f"<b>Discord:</b> {result['Discord']}\n"
                f"<b>Telegram:</b> {result['Telegram']}\n"
                f"<b>Link:</b> {result['Link']}\n"
                f"<b>Type:</b> {result['Type']}\n"
            )
            
            if len(response + entry) > 4000:
                await update.message.reply_html(response)
                response = f"🔍 <b>HASIL PENCARIAN '{keyword.upper()}' (Lanjutan):</b>\n\n"
            
            response += entry

        if response:
            await update.message.reply_html(response)
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("🔧 Gagal melakukan pencarian")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        records = read_csv()
        
        if not records:
            await update.message.reply_text("📭 Database airdrop kosong")
            return
            
        # Hitung statistik
        stats = {}
        for record in records:
            airdrop_type = record['Type']
            stats[airdrop_type] = stats.get(airdrop_type, 0) + 1
            
        # Format pesan
        message = "📊 <b>STATISTIK AIRDROP</b>\n\n"
        message += f"🪙 Total Airdrop: {len(records)}\n"
        message += "━━━━━━━━━━━━━━━━━\n"
        
        # Urutkan dari yang terbanyak
        sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
        
        # Emoji untuk tiap kategori
        type_emojis = {
            'Galxe': '🌌',
            'Testnet': '🔧',
            'Layer3': '📡',
            'Waitlist': '📝',
            'Node': '🖥️',
            'Social Task': '💬'
        }
        
        for type_name, count in sorted_stats:
            emoji = type_emojis.get(type_name, '🔘')
            message += f"{emoji} <b>{type_name}:</b> {count}\n"
            
        message += "\nℹ️ Gunakan /list untuk melihat detail"
        
        await update.message.reply_html(message)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await update.message.reply_text("🔧 Gagal memuat statistik")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📚 Panduan Penggunaan:
/start - Mulai input data baru
/list - Tampilkan semua airdrop
/stats - Tampilkan statistik
/search [keyword] - Cari airdrop
/help - Tampilkan pesan ini
/cancel - Batalkan proses input
"""
    await update.message.reply_text(help_text)

async def invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Input tidak valid! Silakan ikuti petunjuk (/help untuk bantuan)")

def main():
    init_csv()
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAMA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_nama),
                MessageHandler(~filters.TEXT, invalid_input)
            ],
            TWITTER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_twitter),
                MessageHandler(~filters.TEXT, invalid_input)
            ],
            DISCORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_discord),
                MessageHandler(~filters.TEXT, invalid_input)
            ],
            TELEGRAM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_telegram),
                MessageHandler(~filters.TEXT, invalid_input)
            ],
            LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_link),
                MessageHandler(~filters.TEXT, invalid_input)
            ],
            TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_data),
                MessageHandler(~filters.TEXT, invalid_input)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        conversation_timeout=300,
        per_message=False
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('list', list_airdrops))
    application.add_handler(CommandHandler('stats', stats_command))
    application.add_handler(CommandHandler('search', search_airdrops))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(TypeHandler(Update, limit_rate), group=-1)

    application.run_polling()

if __name__ == '__main__':
    main()
