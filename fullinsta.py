import logging
import re
import os
import time
import random
import json
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler
)
import instaloader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== LOAD CONFIGURATION ==========
REQUIRED_ENV_VARS = [
    'TOKEN_BOT', 'INSTAGRAM_SESSIONID', 'INSTAGRAM_DS_USER_ID',
    'INSTAGRAM_CSRFTOKEN', 'INSTAGRAM_RUR', 'INSTAGRAM_MID', 'INSTAGRAM_USERNAME'
]

def clean_cookie_value(value: str) -> str:
    """Membersihkan nilai cookie dari tanda kutip dan whitespace"""
    return value.strip().strip('"').strip("'") if value else None

env_vars = {var: clean_cookie_value(os.getenv(var)) for var in REQUIRED_ENV_VARS}

if any(value is None for value in env_vars.values()):
    missing = [var for var, val in env_vars.items() if val is None]
    logger.error(f"❌ Missing .env variables: {', '.join(missing)}")
    exit(1)

# ========== USER AGENT MANAGEMENT ==========
def load_user_agents():
    try:
        with open("user-agents.json", "r", encoding="utf-8") as f:
            agents = json.load(f)
            if not isinstance(agents, list):
                raise ValueError("User agents should be an array")
            valid_agents = [ua for ua in agents if isinstance(ua, str) and ua.strip()]
            if not valid_agents:
                raise ValueError("No valid User-Agents found")
            return valid_agents
    except Exception as e:
        logger.error(f"❌ Error loading user agents: {str(e)}")
        exit(1)

USER_AGENTS = load_user_agents()

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Cookie": (
            f"sessionid={env_vars['INSTAGRAM_SESSIONID']}; "
            f"ds_user_id={env_vars['INSTAGRAM_DS_USER_ID']}; "
            f"csrftoken={env_vars['INSTAGRAM_CSRFTOKEN']}"
        ),
        "X-CSRFToken": env_vars['INSTAGRAM_CSRFTOKEN'],
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/"
    }

# ========== INSTAGRAM SETUP ==========
loader = instaloader.Instaloader()

try:
    # Setup session lengkap
    cookies = {
        "sessionid": env_vars['INSTAGRAM_SESSIONID'],
        "ds_user_id": env_vars['INSTAGRAM_DS_USER_ID'],
        "csrftoken": env_vars['INSTAGRAM_CSRFTOKEN'],
        "rur": env_vars['INSTAGRAM_RUR'],
        "mid": env_vars['INSTAGRAM_MID']
    }
    
    loader.context._session.cookies.update(cookies)
    logger.info("✅ Instagram session initialized successfully")

except Exception as e:
    logger.error(f"❌ Failed to initialize Instagram session: {str(e)}")
    exit(1)

# ========== BOT HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📸 Kirim URL profil Instagram untuk melihat:\n"
        "- Foto Profil HD\n"
        "- Story Terbaru\n"
        "- Highlight\n"
        "- Info Profil\n\n"
        "Contoh URL: https://www.instagram.com/nasa/"
    )

def extract_username(url: str) -> str:
    match = re.match(
        r"(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9_.]+)/?",
        url,
        re.IGNORECASE
    )
    return match.group(1) if match else None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text.strip()
    username = extract_username(url)
    
    if not username:
        await update.message.reply_text("❌ Format URL tidak valid!")
        return

    try:
        context.user_data['current_profile'] = username
        
        # Buat inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📷 Foto Profil", callback_data='profile_pic'),
                InlineKeyboardButton("📹 Story", callback_data='story')
            ],
            [
                InlineKeyboardButton("🌟 Highlights", callback_data='highlights'),
                InlineKeyboardButton("📊 Info Profil", callback_data='profile_info')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Pilih fitur untuk @{username}:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        await update.message.reply_text("⚠️ Terjadi kesalahan, coba lagi nanti")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    username = context.user_data.get('current_profile')
    if not username:
        await query.edit_message_text("❌ Session expired, silakan kirim URL lagi")
        return

    try:
        if query.data == 'profile_pic':
            await handle_profile_pic(query, username)
            
        elif query.data == 'story':
            await handle_stories(query, username)
            
        elif query.data == 'highlights':
            await handle_highlights(query, username)
            
        elif query.data == 'profile_info':
            await handle_profile_info(query, username)
            
    except Exception as e:
        logger.error(f"Error in button handler: {str(e)}", exc_info=True)
        await query.edit_message_text("⚠️ Gagal memproses permintaan")

async def handle_profile_pic(query, username):
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        
        if profile.is_private and not profile.followed_by_viewer:
            await query.message.reply_text("🔒 Profil privat - Anda belum follow akun ini")
            return

        # Dapatkan URL HD
        hd_url = profile.profile_pic_url.replace("/s150x150/", "/s1080x1080/")
        
        # Download gambar
        response = requests.get(hd_url, headers=get_random_headers(), stream=True)
        response.raise_for_status()

        # Simpan sementara
        temp_file = f"temp_{username}_{int(time.time())}.jpg"
        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Kirim sebagai dokumen
        await query.message.reply_document(
            document=open(temp_file, "rb"),
            filename=f"{username}_profile.jpg",
            caption=f"📸 Foto Profil @{username}"
        )
        os.remove(temp_file)

    except Exception as e:
        logger.error(f"Profile pic error: {str(e)}")
        await query.message.reply_text("⚠️ Gagal mengambil foto profil")

async def handle_stories(query, username):
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        
        if profile.is_private and not profile.followed_by_viewer:
            await query.message.reply_text("🔒 Profil privat - Anda belum follow akun ini")
            return

        # Dapatkan story terbaru
        stories = loader.get_stories([profile.userid])
        story_items = [item for item in stories]

        if not story_items:
            await query.message.reply_text("📭 Tidak ada story yang tersedia")
            return

        # Download story pertama
        story = story_items[0]
        temp_file = f"temp_story_{username}_{int(time.time())}.{'mp4' if story.is_video else 'jpg'}"
        
        loader.download_storyitem(story, temp_file)

        # Kirim ke Telegram
        with open(temp_file, 'rb') as f:
            if story.is_video:
                await query.message.reply_video(f)
            else:
                await query.message.reply_photo(f)
        
        os.remove(temp_file)

    except Exception as e:
        logger.error(f"Story error: {str(e)}")
        await query.message.reply_text("⚠️ Gagal mengambil story")

async def handle_highlights(query, username):
    try:
        loop = asyncio.get_event_loop()
        profile = await loop.run_in_executor(None, lambda: instaloader.Profile.from_username(loader.context, username))

        if profile.is_private and not profile.followed_by_viewer:
            await query.message.reply_text("🔒 Profil privat - Anda belum follow akun ini")
            return

        # Menggunakan Instaloader untuk mendapatkan highlights
        highlights = await loop.run_in_executor(None, lambda: loader.get_highlights(profile))
        
        if not highlights:
            await query.message.reply_text("🌟 Tidak ada highlights yang tersedia")
            return

        # Buat daftar highlight
        keyboard = []
        for highlight in highlights:
            title = highlight.title[:20] + "..." if len(highlight.title) > 20 else highlight.title
            keyboard.append([InlineKeyboardButton(f"🌟 {title}", callback_data=f"highlight_{highlight.unique_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"Pilih highlight untuk @{username}:",
            reply_markup=reply_markup
        )

    except Exception as e:
        print(f"Highlights error: {str(e)}")
        await query.message.reply_text("⚠️ Gagal mengambil daftar highlight")

async def handle_profile_info(query, username):
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        
        info_text = (
            f"📊 Info Profil @{username}:\n"
            f"👤 Nama: {profile.full_name}\n"
            f"📝 Bio: {profile.biography}\n"
            f"🔗 Followers: {profile.followers:,}\n"
            f"👀 Following: {profile.followees:,}\n"
            f"📌 Post: {profile.mediacount:,}"
        )
        
        await query.message.reply_text(info_text)

    except Exception as e:
        logger.error(f"Profile info error: {str(e)}")
        await query.message.reply_text("⚠️ Gagal mengambil info profil")

def main():
    application = Application.builder().token(env_vars['TOKEN_BOT']).build()
    
    # Tambah handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("🤖 Bot started successfully")
    application.run_polling()

if __name__ == "__main__":
    main()
