async def handle_stories(query, username):
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        
        if profile.is_private and not profile.followed_by_viewer:
            await query.message.reply_text("🔒 Profil privat - Anda belum follow akun ini")
            return

        # Dapatkan dan urutkan story
        stories = []
        for story in loader.get_stories([profile.userid]):
            stories.extend(story.get_items())
        
        stories.sort(key=lambda x: x.date_utc)
        
        if not stories:
            await query.message.reply_text("📭 Tidak ada story yang tersedia")
            return

        temp_dir = f"temp_{username}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)

        try:
            sent_count = 0
            logger.info(f"🔄 Memproses {len(stories)} story untuk @{username}")

            for story_item in stories:
                new_path = None
                try:
                    # Download story tanpa parameter filename_prefix
                    loader.download_storyitem(story_item, temp_dir)
                    
                    # Cari file terbaru yang bukan .txt atau .xz
                    list_of_files = [
                        f for f in os.listdir(temp_dir) 
                        if not f.endswith(('.txt', '.xz'))
                    ]
                    
                    if not list_of_files:
                        logger.warning("⚠️ Tidak ada file media yang ditemukan")
                        continue
                        
                    # Ambil file terakhir yang dimodifikasi
                    latest_file = max(
                        list_of_files,
                        key=lambda f: os.path.getctime(os.path.join(temp_dir, f))
                    )
                    original_path = os.path.join(temp_dir, latest_file)
                    
                    # Tentukan ekstensi
                    if story_item.is_video:
                        file_ext = ".mp4"
                    else:
                        file_ext = ".jpg"
                    
                    # Buat nama file baru
                    timestamp = int(story_item.date_utc.timestamp())
                    new_filename = f"story_{timestamp}_{username}{file_ext}"
                    new_path = os.path.join(temp_dir, new_filename)
                    os.rename(original_path, new_path)
                    
                    # Kirim ke Telegram
                    with open(new_path, 'rb') as f:
                        if story_item.is_video:
                            await query.message.reply_video(
                                video=f,
                                caption=f"📹 {story_item.date_utc.strftime('%d-%m-%Y %H:%M')}",
                                filename=new_filename,
                                read_timeout=30
                            )
                        else:
                            await query.message.reply_photo(
                                photo=f,
                                caption=f"📸 {story_item.date_utc.strftime('%d-%m-%Y %H:%M')}",
                                filename=new_filename,
                                read_timeout=30
                            )
                    sent_count += 1
                    logger.info(f"✅ Berhasil mengirim {new_filename}")

                except Exception as e:
                    logger.error(f"Gagal mengirim story: {str(e)}")
                    continue
                
                finally:
                    # Hapus file setelah dikirim
                    if new_path and os.path.exists(new_path):
                        os.remove(new_path)
                    time.sleep(2)

            await query.message.reply_text(f"📤 Total {sent_count} story berhasil dikirim")

        finally:
            # Bersihkan direktori
            if os.path.exists(temp_dir):
                for f in os.listdir(temp_dir):
                    os.remove(os.path.join(temp_dir, f))
                os.rmdir(temp_dir)
                logger.info(f"🗑️ Direktori {temp_dir} berhasil dibersihkan")

    except Exception as e:
        logger.error(f"Story error: {str(e)}", exc_info=True)
        await query.message.reply_text("⚠️ Gagal mengambil story")
