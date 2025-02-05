import logging
import re
import os
import pytz
import time
import random
import json
import requests
import glob
import shutil
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
from instaloader import Instaloader, Profile, QueryReturnedBadRequestException
from dotenv import load_dotenv
from requests.cookies import RequestsCookieJar

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
            return [ua for ua in agents if isinstance(ua, str) and ua.strip()]
    except Exception as e:
        logger.error(f"❌ Error loading user agents: {str(e)}")
        exit(1)

USER_AGENTS = load_user_agents()

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Cookie": f"sessionid={env_vars['INSTAGRAM_SESSIONID']}",
        "X-CSRFToken": env_vars['INSTAGRAM_CSRFTOKEN']
    }

# ========== INSTAGRAM SETUP ==========
loader = Instaloader(
    user_agent=random.choice(USER_AGENTS),
    sleep=True,
    quiet=True,
    request_timeout=30,
    dirname_pattern="{target}",
    filename_pattern="{date_utc}_UTC_{profile}",
    download_pictures=True, download_videos=True,
    download_video_thumbnails=False, download_geotags=False,
    post_metadata_txt_pattern="",
    storyitem_metadata_txt_pattern="",
    compress_json=False, download_comments=False
)

try:
    # Buat cookie jar
    cookie_jar = RequestsCookieJar()
    cookies = {
        "sessionid": env_vars['INSTAGRAM_SESSIONID'],
        "ds_user_id": env_vars['INSTAGRAM_DS_USER_ID'],
        "csrftoken": env_vars['INSTAGRAM_CSRFTOKEN'],
        "rur": env_vars['INSTAGRAM_RUR'],
        "mid": env_vars['INSTAGRAM_MID']
    }

    # Tambahkan cookies ke session
    for name, value in cookies.items():
        cookie_jar.set(name, value, domain='.instagram.com', path='/')

    loader.context._session.cookies = cookie_jar
    loader.context.username = env_vars['INSTAGRAM_USERNAME']

    # Verifikasi session
    test_profile = Profile.from_username(loader.context, env_vars['INSTAGRAM_USERNAME'])
    logger.info(f"✅ Login berhasil sebagai: {test_profile.full_name}")

except Exception as e:
    logger.error(f"❌ Gagal login: {str(e)}")
    exit(1)

# ========== BOT HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📸 Kirim URL profil Instagram untuk melihat:\n"
        "- Foto Profil HD\n"
        "- Story Terbaru\n"
        "- Highlight\n"
        "- Info Profil\n\n"
        "Contoh URL: https://www.instagram.com/hanan.ac.id/"
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
            ],
            [
                #InlineKeyboardButton("📥 Export Followers", callback_data='export_followers'),
                #InlineKeyboardButton("📥 Export Following", callback_data='export_following')
            #],
            #[
                #InlineKeyboardButton("🔍 Track Followers", callback_data='track_followers'),
                #InlineKeyboardButton("🔍 Track Following", callback_data='track_following')
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
            await handle_highlights(query, username, page=0)

        elif query.data.startswith('highlights_next_'):
            next_page = int(query.data.split('_')[2])
            await handle_highlights(query, username, page=next_page)

        elif query.data.startswith('highlights_prev_'):
            prev_page = int(query.data.split('_')[2])
            await handle_highlights(query, username, page=prev_page)

        elif query.data == 'profile_info':
            await handle_profile_info(query, username)

        elif query.data.startswith('highlight_'):
            highlight_id = query.data.split('_')[1]
            await handle_highlight_items(query, username, highlight_id)

        elif query.data == 'export_followers':
            await export_followers(query, username)

        elif query.data == 'export_following':
            await export_following(query, username)

        elif query.data == 'track_followers':
            await track_followers(query, username)

        elif query.data == 'track_following':
            await track_following(query, username)

    except Exception as e:
        logger.error(f"Error in button handler: {str(e)}", exc_info=True)
        await query.edit_message_text("⚠️ Gagal memproses permintaan")

async def handle_profile_pic(query, username):
    try:
        profile = Profile.from_username(loader.context, username)

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
        profile = Profile.from_username(loader.context, username)

        if profile.is_private and not profile.followed_by_viewer:
            await query.message.reply_text("🔒 Profil privat - Anda belum follow akun ini")
            return

        stories = []
        try:
            for story in loader.get_stories([profile.userid]):
                stories.extend(story.get_items())
        except QueryReturnedBadRequestException:
            await query.message.reply_text("🔒 Profil privat - Bot tidak dapat mengakses story")
            return

        # Sort stories by date (oldest first)
        stories.sort(key=lambda x: x.date_utc)

        if not stories:
            await query.message.reply_text("📭 Tidak ada story yang tersedia")
            return

        # Set time zone (contoh: Asia/Jakarta untuk WIB)
        time_zone = pytz.timezone("Asia/Jakarta")

        temp_dir = f"temp_{username}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)

        try:
            sent_count = 0
            logger.info(f"🔄 Memproses {len(stories)} story untuk @{username}")

            for story_item in stories:
                try:
                    download_success = loader.download_storyitem(story_item, temp_dir)
                    if not download_success:
                        logger.warning(f"Gagal mengunduh story item: {story_item.mediaid}")
                        continue

                    # Filter file media valid
                    valid_extensions = ('.jpg', '.jpeg', '.png', '.mp4', '.mov')
                    media_files = [
                        f for f in glob.glob(os.path.join(temp_dir, "*"))
                        if f.lower().endswith(valid_extensions)
                    ]

                    if not media_files:
                        logger.warning("Tidak ada file media yang valid")
                        continue

                    # Ambil file terbaru
                    latest_file = max(media_files, key=os.path.getmtime)

                    # Validasi tipe file
                    is_video = story_item.is_video
                    expected_ext = ('.mp4', '.mov') if is_video else ('.jpg', '.jpeg', '.png')
                    if not latest_file.lower().endswith(expected_ext):
                        logger.error("Ekstensi file tidak sesuai dengan tipe konten")
                        continue

                    # Cek ukuran file
                    file_size = os.path.getsize(latest_file)
                    if file_size > 50 * 1024 * 1024:
                        await query.message.reply_text("⚠️ File melebihi batas 50MB")
                        os.remove(latest_file)
                        continue

                    # Konversi waktu UTC ke time zone yang ditentukan
                    local_time = story_item.date_utc.replace(tzinfo=pytz.utc).astimezone(time_zone)
                    time_format = "%d-%m-%Y %H:%M"

                    try:
                        with open(latest_file, "rb") as f:
                            if is_video:
                                await query.message.reply_video(
                                    video=f,
                                    caption=f"📹 {local_time.strftime(time_format)}",
                                    read_timeout=60,
                                    write_timeout=60
                                )
                            else:
                                await query.message.reply_photo(
                                    photo=f,
                                    caption=f"📸 {local_time.strftime(time_format)}",
                                    read_timeout=60
                                )
                            sent_count += 1
                    except Exception as send_error:
                        logger.error(f"Gagal mengirim file: {str(send_error)}")
                    finally:
                        if os.path.exists(latest_file):
                            os.remove(latest_file)

                    time.sleep(2)

                except Exception as e:
                    logger.error(f"Gagal mengunduh atau mengirim story: {str(e)}")
                    continue

            await query.message.reply_text(f"📤 Total {sent_count} story berhasil dikirim")

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"🗑️ Direktori {temp_dir} berhasil dibersihkan")

    except QueryReturnedBadRequestException as e:
        logger.error(f"Error API Instagram: {str(e)}")
        await query.message.reply_text("⚠️ Akses ditolak oleh Instagram")
    except Exception as e:
        logger.error(f"Story error: {str(e)}", exc_info=True)
        await query.message.reply_text("⚠️ Gagal mengambil story")

# ... (kode setelahnya tetap sama)

async def handle_highlights(query, username, page=0):
    try:
        profile = Profile.from_username(loader.context, username)
        highlights = list(loader.get_highlights(user=profile))

        if not highlights:
            await query.message.reply_text("🌟 Tidak ada highlights yang tersedia")
            return

        # Pagination logic
        items_per_page = 10
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        current_highlights = highlights[start_idx:end_idx]

        keyboard = []
        for highlight in current_highlights:
            title = highlight.title[:15] + "..." if len(highlight.title) > 15 else highlight.title
            keyboard.append([
                InlineKeyboardButton(
                    f"🌟 {title}",
                    callback_data=f"highlight_{highlight.unique_id}"
                )
            ])

        # Tambahkan tombol navigasi
        navigation_buttons = []
        if page > 0:
            navigation_buttons.append(
                InlineKeyboardButton("⏪ Kembali", callback_data=f"highlights_prev_{page - 1}")
            )
        if len(highlights) > end_idx:
            navigation_buttons.append(
                InlineKeyboardButton("⏩ Lanjutkan", callback_data=f"highlights_next_{page + 1}")
            )

        if navigation_buttons:
            keyboard.append(navigation_buttons)

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"Pilih highlight untuk @{username} (Halaman {page + 1}):",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Highlights error: {str(e)}", exc_info=True)
        await query.message.reply_text("⚠️ Gagal mengambil daftar highlight")

async def handle_highlight_items(query, username, highlight_id):
    temp_dir = None  # Inisialisasi variabel di scope terluar
    try:
        profile = Profile.from_username(loader.context, username)
        highlights = list(loader.get_highlights(user=profile))

        # Konversi highlight_id ke integer
        highlight_id_int = int(highlight_id)
        highlight = None

        # Cari highlight
        for h in highlights:
            if h.unique_id == highlight_id_int:
                highlight = h
                break

        if not highlight:
            await query.message.reply_text("❌ Highlight tidak ditemukan")
            return

        # Buat direktori temporary
        temp_dir = f"temp_highlight_{username}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        sent_count = 0

        # Set time zone (contoh: Asia/Jakarta untuk WIB)
        time_zone = pytz.timezone("Asia/Jakarta")

        # Ubah generator menjadi list
        highlight_items = list(highlight.get_items())

        # Kirim pesan jumlah item yang diproses
        await query.message.reply_text(f"🔄 Memproses {len(highlight_items)} item dari highlight '{highlight.title}'")

        try:
            for idx, item in enumerate(highlight_items, start=1):
                # Download item
                loader.download_storyitem(item, target=temp_dir)
                time.sleep(3)

                # Filter file media valid
                valid_extensions = ('.jpg', '.jpeg', '.png', '.mp4', '.mov')
                media_files = [
                    f for f in glob.glob(os.path.join(temp_dir, "*"))
                    if f.lower().endswith(valid_extensions)
                ]

                if not media_files:
                    logger.warning("Tidak ada file media yang valid")
                    continue

                # Ambil file terbaru
                latest_file = max(media_files, key=os.path.getmtime)

                # Validasi tipe file
                is_video = item.is_video
                expected_ext = ('.mp4', '.mov') if is_video else ('.jpg', '.jpeg', '.png')
                if not latest_file.lower().endswith(expected_ext):
                    logger.error("Ekstensi file tidak sesuai dengan tipe konten")
                    continue

                # Cek ukuran file
                file_size = os.path.getsize(latest_file)
                if file_size > 50 * 1024 * 1024:
                    await query.message.reply_text("⚠️ File melebihi batas 50MB")
                    os.remove(latest_file)
                    continue

                # Konversi waktu UTC ke time zone yang ditentukan
                local_time = item.date_utc.replace(tzinfo=pytz.utc).astimezone(time_zone)
                time_format = "%d-%m-%Y %H:%M"

                try:
                    with open(latest_file, "rb") as f:
                        if is_video:
                            await query.message.reply_video(
                                video=f,
                                caption=f"**[{idx}]**.🌟 {highlight.title} - 📹 {local_time.strftime(time_format)}",
                                parse_mode="Markdown",  # Tambahkan parse_mode di sini
                                read_timeout=60,
                                write_timeout=60
                            )
                        else:
                            await query.message.reply_photo(
                                photo=f,
                                caption=f"**[{idx}]**.🌟 {highlight.title} - 📸 {local_time.strftime(time_format)}",
                                parse_mode="Markdown",  # Tambahkan parse_mode di sini
                                read_timeout=60
                            )
                        sent_count += 1
                        logger.info(f"Berhasil mengirim {latest_file} sebagai {'video' if is_video else 'foto'}")
                except Exception as send_error:
                    logger.error(f"Gagal mengirim file: {str(send_error)}")
                finally:
                    if os.path.exists(latest_file):
                        os.remove(latest_file)

                time.sleep(1)

            await query.message.reply_text(f"✅ {sent_count} item dari highlight '{highlight.title}' berhasil dikirim")

        except Exception as e:
            logger.error(f"Error saat memproses item: {str(e)}")
            await query.message.reply_text("⚠️ Gagal memproses item highlight")

        finally:
            # Hapus direktori temporary jika ada
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Direktori {temp_dir} dihapus")

    except QueryReturnedBadRequestException as e:
        logger.error(f"Error API Instagram: {str(e)}")
        await query.message.reply_text("⚠️ Akses ditolak oleh Instagram")
    except Exception as e:
        logger.error(f"Error highlight: {str(e)}", exc_info=True)
        await query.message.reply_text("⚠️ Gagal memproses highlight")
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

async def handle_profile_info(query, username):
    try:
        profile = Profile.from_username(loader.context, username)

        info_text = (
            f"📊 Info Profil @{username}:\n"
            f"👤 Nama: {profile.full_name}\n"
            f"📝 Bio: {profile.biography}\n"
            f"✅ Terverifikasi: {'Ya' if profile.is_verified else 'Tidak'}\n"
            f"🏢 Bisnis: {'Ya' if profile.is_business_account else 'Tidak'}\n"
            f"🔗 Followers: {profile.followers:,}\n"
            f"👀 Following: {profile.followees:,}\n"
            f"📌 Post: {profile.mediacount:,}"
        )

        await query.message.reply_text(info_text)

    except Exception as e:
        logger.error(f"Profile info error: {str(e)}")
        await query.message.reply_text("⚠️ Gagal mengambil info profil")

# ========== FUNGSI PELACAKAN BERKALA ==========
async def periodic_tracking(context: ContextTypes.DEFAULT_TYPE):
    username = context.job.data.get("username")
    chat_id = context.job.data.get("chat_id")

    try:
        # Lacak followers
        await track_followers_periodic(username, chat_id, context)

        # Lacak following
        await track_following_periodic(username, chat_id, context)
    except Exception as e:
        logger.error(f"Error in periodic tracking: {str(e)}", exc_info=True)

async def track_followers_periodic(username, chat_id, context):
    try:
        profile = Profile.from_username(loader.context, username)

        if profile.is_private and not profile.followed_by_viewer:
            await context.bot.send_message(chat_id, "🔒 Profil privat - Anda belum follow akun ini")
            return

        # Ambil daftar followers saat ini
        current_followers = [follower.username for follower in profile.get_followers()]

        # Muat daftar followers sebelumnya
        previous_followers = load_data(username, "followers")

        if previous_followers:
            # Bandingkan daftar followers lama dan baru
            added, removed = find_changes(previous_followers, current_followers)

            # Kirim notifikasi perubahan
            if added or removed:
                message = "📊 Perubahan Followers:\n"
                if added:
                    message += f"➕ {len(added)} akun baru mengikuti:\n"
                    message += "\n".join([f"@{user}" for user in added]) + "\n"
                if removed:
                    message += f"➖ {len(removed)} akun berhenti mengikuti:\n"
                    message += "\n".join([f"@{user}" for user in removed]) + "\n"
                await context.bot.send_message(chat_id, message)
            else:
                await context.bot.send_message(chat_id, "📊 Tidak ada perubahan dalam daftar followers.")
        else:
            await context.bot.send_message(chat_id, "📊 Ini adalah pelacakan pertama. Data followers telah disimpan.")

        # Simpan daftar followers terbaru
        save_data(username, current_followers, "followers")

    except Exception as e:
        logger.error(f"Error tracking followers: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id, "⚠️ Gagal melacak followers")

async def track_following_periodic(username, chat_id, context):
    try:
        profile = Profile.from_username(loader.context, username)

        if profile.is_private and not profile.followed_by_viewer:
            await context.bot.send_message(chat_id, "🔒 Profil privat - Anda belum follow akun ini")
            return

        # Ambil daftar following saat ini
        current_following = [followed.username for followed in profile.get_followees()]

        # Muat daftar following sebelumnya
        previous_following = load_data(username, "following")

        if previous_following:
            # Bandingkan daftar following lama dan baru
            added, removed = find_changes(previous_following, current_following)

            # Kirim notifikasi perubahan
            if added or removed:
                message = "📊 Perubahan Following:\n"
                if added:
                    message += f"➕ {len(added)} akun baru diikuti:\n"
                    message += "\n".join([f"@{user}" for user in added]) + "\n"
                if removed:
                    message += f"➖ {len(removed)} akun berhenti diikuti:\n"
                    message += "\n".join([f"@{user}" for user in removed]) + "\n"
                await context.bot.send_message(chat_id, message)
            else:
                await context.bot.send_message(chat_id, "📊 Tidak ada perubahan dalam daftar following.")
        else:
            await context.bot.send_message(chat_id, "📊 Ini adalah pelacakan pertama. Data following telah disimpan.")

        # Simpan daftar following terbaru
        save_data(username, current_following, "following")

    except Exception as e:
        logger.error(f"Error tracking following: {str(e)}", exc_info=True)
        await context.bot.send_message(chat_id, "⚠️ Gagal melacak following")
        
# ========== PERINTAH PELACAKAN BERKALA ==========
async def start_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = context.user_data.get('current_profile')
    if not username:
        await update.message.reply_text("❌ Silakan kirim URL profil Instagram terlebih dahulu.")
        return

    chat_id = update.message.chat_id

    # Cek apakah job sudah ada
    jobs = scheduler.get_jobs()
    for job in jobs:
        if job.name == f"tracking_{username}_{chat_id}":
            await update.message.reply_text("🔍 Pelacakan sudah aktif untuk akun ini.")
            return

    # Tambahkan job baru
    scheduler.add_job(
        periodic_tracking,
        trigger=IntervalTrigger(minutes=1),  # Jadwalkan setiap 1 jam
        args=[context],
        id=f"tracking_{username}_{chat_id}",
        name=f"tracking_{username}_{chat_id}",
        kwargs={"username": username, "chat_id": chat_id},
    )

    await update.message.reply_text(f"🔍 Pelacakan untuk @{username} telah diaktifkan. Bot akan memeriksa perubahan setiap 1 jam.")

async def stop_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = context.user_data.get('current_profile')
    if not username:
        await update.message.reply_text("❌ Silakan kirim URL profil Instagram terlebih dahulu.")
        return

    chat_id = update.message.chat_id

    # Hentikan job yang sesuai
    job_id = f"tracking_{username}_{chat_id}"
    job = scheduler.get_job(job_id)
    if job:
        job.remove()
        await update.message.reply_text(f"🔍 Pelacakan untuk @{username} telah dihentikan.")
    else:
        await update.message.reply_text("❌ Tidak ada pelacakan aktif untuk akun ini.")
        
# ========== MAIN PROGRAM ==========
def main():
    application = Application.builder().token(env_vars['TOKEN_BOT']).build()

    # Tambah handler
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("start_tracking", start_tracking))
    application.add_handler(CommandHandler("stop_tracking", stop_tracking))

    logger.info("🤖 Bot started successfully")
    application.run_polling()

if __name__ == "__main__":
    main()
