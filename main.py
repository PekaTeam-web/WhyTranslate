
import logging
import os
import time
from telegram.ext import Updater, MessageHandler, Filters
from googletrans import Translator, TranslatorError
from PIL import Image
import pytesseract
import io

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)

translator = Translator()

# ID Channel
PRIVATE_CHANNEL_ID = -1002818654591  # @whyteddy_news

MAX_CAPTION_LENGTH = 1024 # Telegram caption limit

def handle_forwarded_message(update, context):
    """Menerjemahkan pesan yang diteruskan (teks atau gambar dengan caption) dan meneruskannya ke channel pribadi."""
    logger.info(f"Menerima pesan dari {update.message.chat.id}")
    if update.message and update.message.forward_from_chat:
        original_text = None
        forwarded_from_chat_name = update.message.forward_from_chat.title or "Channel Tidak Dikenal"

        # Prioritaskan caption jika ada gambar dengan caption
        if update.message.photo and update.message.caption:
            original_text = update.message.caption
            logger.info("Mendeteksi gambar dengan caption.")
        elif update.message.text:
            original_text = update.message.text
            logger.info("Mendeteksi pesan teks.")
        elif update.message.photo:
            # Jika ada gambar tanpa caption, gunakan OCR
            logger.info("Mendeteksi gambar tanpa caption, mencoba OCR.")
            file_id = update.message.photo[-1].file_id
            new_file = context.bot.get_file(file_id)
            photo_bytes = new_file.download_as_bytearray()
            
            # Gunakan Pillow untuk membuka gambar dari byte
            image = Image.open(io.BytesIO(photo_bytes))
            
            # Ekstrak teks menggunakan Tesseract OCR
            try:
                original_text = pytesseract.image_to_string(image)
                if not original_text.strip(): # Jika OCR tidak menemukan teks
                    original_text = "(Tidak ada teks yang terdeteksi dalam gambar)"
                    logger.info("OCR tidak mendeteksi teks dalam gambar.")
                else:
                    logger.info("OCR berhasil mendeteksi teks.")
            except Exception as e:
                logger.error(f"Gagal melakukan OCR pada gambar: {e}")
                original_text = f"(Gagal melakukan OCR: {e})"

        if original_text:
            translated_text = ""
            try:
                # Menerjemahkan ke bahasa Indonesia (deteksi bahasa otomatis)
                translated_text = translator.translate(original_text, dest='id').text                
                logger.info("Pesan berhasil diterjemahkan.")
            except TranslatorError as e:
                logger.error(f"Gagal menerjemahkan dengan googletrans: {e}")
                translated_text = f"[Terjemahan gagal: {e}]"
            except Exception as e:
                logger.error(f"Gagal menerjemahkan (umum): {e}")
                translated_text = f"[Terjemahan gagal: {e}]"

            try:
                # Format pesan yang akan dikirim
                message_template = f"📰 Pesan Diteruskan dari {forwarded_from_chat_name}:\n\n🔤 Asli:\n{{original}}\n\n🇮🇩 Terjemahan (ID):\n{{translated}}"
                
                # Coba format pesan lengkap
                full_message = message_template.format(original=original_text, translated=translated_text)
                
                # Periksa panjang pesan dan potong jika terlalu panjang
                if len(full_message) > MAX_CAPTION_LENGTH:
                    logger.warning("Pesan terlalu panjang, memotongnya.")
                    # Prioritaskan terjemahan dan potong teks asli jika perlu
                    header_len = len(f"📰 Pesan Diteruskan dari {forwarded_from_chat_name}:\n\n🔤 Asli:\n")
                    translated_len = len(f"\n\n🇮🇩 Terjemahan (ID):\n{translated_text}")
                    
                    available_len_for_original = MAX_CAPTION_LENGTH - header_len - translated_len - len("...(dipotong)")
                    
                    if available_len_for_original > 0:
                        truncated_original_text = original_text[:available_len_for_original] + "...(dipotong)"
                    else:
                        truncated_original_text = "...(dipotong)"
                    
                    full_message = message_template.format(original=truncated_original_text, translated=translated_text)

                    # Jika masih terlalu panjang, potong terjemahan juga
                    if len(full_message) > MAX_CAPTION_LENGTH:
                        # Ini adalah skenario ekstrem, mungkin hanya terjemahan yang dikirim
                        full_message = f"🇮🇩 Terjemahan (ID):\n{translated_text}"
                        if len(full_message) > MAX_CAPTION_LENGTH:
                            full_message = full_message[:MAX_CAPTION_LENGTH - len("...(dipotong)")] + "...(dipotong)"

                # Kirim ke channel target
                if update.message.photo: # Jika ada foto, kirim foto dengan caption terjemahan
                    file_id = update.message.photo[-1].file_id
                    context.bot.send_photo(chat_id=PRIVATE_CHANNEL_ID, photo=file_id, caption=full_message)
                    logger.info("Gambar dengan caption terjemahan berhasil dikirim.")
                else: # Jika hanya teks, kirim teks
                    context.bot.send_message(chat_id=PRIVATE_CHANNEL_ID, text=full_message)
                    logger.info("Pesan teks terjemahan berhasil dikirim.")
                
            except Exception as e:
                logger.error(f"Gagal meneruskan pesan ke Telegram: {e}")
                # Kirim pesan error ke channel pribadi
                error_message = f"❌ Gagal meneruskan pesan:\n\n{original_text}\n\nError: {str(e)}"
                context.bot.send_message(chat_id=PRIVATE_CHANNEL_ID, text=error_message)
    elif update.message and update.message.text: # Jika bukan pesan yang diteruskan, balas saja
        update.message.reply_text("Silakan teruskan pesan yang ingin Anda terjemahkan kepada saya.")
        logger.info("Menerima pesan non-terusan teks.")
    elif update.message and update.message.photo: # Jika hanya foto tanpa teks yang diteruskan, balas saja
        update.message.reply_text("Silakan teruskan pesan yang berisi teks atau gambar dengan teks yang jelas.")
        logger.info("Menerima pesan non-terusan foto.")

def main():
    """Menjalankan bot."""
    # Token bot Telegram dari environment variable atau hardcode
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7235261978:AAFaS8Dg7IDDmSc8JI7IAqX2bPJywLRl3xU")
    
    # Membuat updater dan dispatcher
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Menambahkan handler untuk semua jenis pesan (teks dan foto) yang diteruskan
    dispatcher.add_handler(MessageHandler(Filters.forwarded & (Filters.text | Filters.photo | Filters.caption), handle_forwarded_message))
    dispatcher.add_handler(MessageHandler(~Filters.forwarded & (Filters.text | Filters.photo | Filters.caption), handle_forwarded_message))

    # Mulai bot
    updater.start_polling()
    logger.info("Bot dimulai. Menunggu pesan yang diteruskan...")
    
    # Menggunakan idle() untuk menjaga bot tetap berjalan
    updater.idle()

if __name__ == '__main__':
    main()

