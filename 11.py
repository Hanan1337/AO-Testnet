async def handle_stories(query, username):
    try:
        import magic
        from PIL import Image, UnidentifiedImageError

        profile = Profile.from_username(loader.context, username)
        logger.info(f"🔍 Memproses story @{username}")

        # Validasi akun privat
        if profile.is_private and not profile.followed_by_viewer:
            await query.message.reply_text("🔒 Akses ditolak")
            return

        # Ambil story
        stories = []
        for story in loader.get_stories([profile.userid]):
            story_items = list(story.get_items())
            stories.extend(story_items)
            logger.info(f"📥 Ditemukan {len(story_items)} story")

        if not stories:
            await query.message.reply_text("📭 Tidak ada story")
            return

        temp_dir = f"temp_{username}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        sent_count = 0

        for story_item in stories:
            try:
                # 1. Download story item
                loader.download_storyitem(story_item, target=temp_dir)
                time.sleep(1)

                # 2. Filter file media (abaikan metadata)
                valid_extensions = ('.jpg', '.jpeg', '.png', '.mp4', '.mov')
                media_files = [
                    f for f in glob.glob(os.path.join(temp_dir, "*")) 
                    if f.lower().endswith(valid_extensions)
                ]

                if not media_files:
                    logger.warning("🚫 Tidak ada file media yang valid")
                    continue

                # 3. Ambil file terbaru
                latest_file = max(media_files, key=os.path.getctime)
                logger.info(f"✉️ Mengirim: {os.path.basename(latest_file)}")

                # 4. Validasi MIME type
                mime_type = magic.from_file(latest_file, mime=True)
                if not mime_type.startswith(('image/', 'video/')):
                    logger.error(f"❌ Tipe file tidak didukung: {mime_type}")
                    continue

                # 5. Kirim ke Telegram
                with open(latest_file, "rb") as f:
                    if story_item.is_video:
                        await query.message.reply_video(
                            video=f,
                            caption=f"📅 {story_item.date_utc.strftime('%H:%M')}",
                            write_timeout=120
                        )
                    else:
                        await query.message.reply_photo(
                            photo=f,
                            caption=f"📅 {story_item.date_utc.strftime('%H:%M')}"
                        )
                    sent_count += 1

                # 6. Hapus file
                os.remove(latest_file)

            except Exception as e:
                logger.error(f"❌ Gagal: {str(e)}", exc_info=True)
            finally:
                # Bersihkan sisa file
                for f in glob.glob(os.path.join(temp_dir, "*")):
                    os.remove(f)

        await query.message.reply_text(f"✅ {sent_count} story berhasil dikirim")

    except Exception as e:
        logger.error(f"🚨 Error: {str(e)}", exc_info=True)
        await query.message.reply_text("⚠️ Gagal total")
    finally:
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
