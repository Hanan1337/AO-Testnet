async def handle_stories(query, username):
    try:
        # Mendapatkan profil Instagram
        profile = instaloader.Profile.from_username(loader.context, username)
        
        # Cek status privasi
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
        
        # Mengunduh story ke dalam memori menggunakan BytesIO
        temp_file = io.BytesIO()
        loader.download_storyitem(story, target=temp_file)
        
        # Menentukan posisi pointer ke awal sebelum pengiriman
        temp_file.seek(0)

        # Kirim file ke Telegram
        if story.is_video:
            await query.message.reply_video(
                video=temp_file,
                caption=f"📹 Story @{username}",
                supports_streaming=True
            )
        else:
            await query.message.reply_photo(
                photo=temp_file,
                caption=f"📸 Story @{username}"
            )

        # Tidak perlu menghapus file, karena tidak disimpan ke disk

    except Exception as e:
        logger.error(f"Story error: {str(e)}")
        await query.message.reply_text("⚠️ Gagal mengambil story")
