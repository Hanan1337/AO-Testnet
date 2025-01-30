async def handle_stories(query, username):
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        
        if profile.is_private and not profile.followed_by_viewer:
            await query.message.reply_text("🔒 Profil privat - Anda belum follow akun ini")
            return

        # Dapatkan story menggunakan metode terbaru
        stories = []
        for story in loader.get_stories([profile.userid]):
            stories.extend(story.get_items())
        
        if not stories:
            await query.message.reply_text("📭 Tidak ada story yang tersedia")
            return

        # Ambil story pertama
        story = stories[0]
        temp_file = f"temp_story_{username}_{int(time.time())}.{'mp4' if story.is_video else 'jpg'}"
        loader.download_storyitem(story, temp_file)

        # Kirim ke Telegram
        with open(temp_file, 'rb') as f:
            if story.is_video:
                await query.message.reply_video(
                    video=f,
                    caption=f"📹 Story @{username}",
                    supports_streaming=True
                )
            else:
                await query.message.reply_photo(
                    photo=f,
                    caption=f"📸 Story @{username}"
                )

        # Pastikan `temp_file` adalah file, bukan direktori
        if os.path.isfile(temp_file):
            os.remove(temp_file)

    except Exception as e:
        logger.error(f"Story error: {str(e)}")
        await query.message.reply_text("⚠️ Gagal mengambil story")
