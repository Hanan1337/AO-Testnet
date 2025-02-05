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
                                read_timeout=60,
                                write_timeout=60
                            )
                        else:
                            await query.message.reply_photo(
                                photo=f,
                                caption=f"**[{idx}]**.🌟 {highlight.title} - 📸 {local_time.strftime(time_format)}",
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
