
import os
import logging
import yt_dlp
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes, PicklePersistence

# --- الإعدادات الأساسية ---
TELEGRAM_BOT_TOKEN = "7434977676:AAEuSVIPcd_DWlR89bOqLapeBHJJJYfPLw0"
ADMIN_CHAT_ID = 6595593335
DOWNLOADS_DIR = 'downloads'

if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# --- مُعرفات الملصقات ---
STICKER_CHECKING = "CAACAgIAAxkBAANLaGG8G3WB8oYtSEPG3qeskmF3iasAAkMBAALNGzAIgL6J2IEDvZM2BA"
STICKER_LOADING = "CAACAgQAAxkBAANNaGI5ERnUEr1O1p_YIrEf6sSU6jkAAkIBAALNGzAIBAKArStvO742BA"
STICKER_ERROR = "CAACAgIAAxkBAANJaGG8ES30HxcNrhDsIbig-PiuxxcAAmMAA9vbfgABjJ0FPedCg-c2BA"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def get_clean_formats(url: str) -> dict:
    ydl_opts = {'quiet': True, 'nocheckcertificate': True}
    
    cookie_file = 'cookies.txt'
    if os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file
        logger.info("Using cookies file for getting formats.")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    
    videos = []
    audios = []
    
    for f in info.get('formats', []):
        format_id = f.get('format_id')
        if not format_id:
            continue

        if f.get('vcodec') != 'none':
            height = f.get('height')
            if height:
                note = " (مدمج)" if f.get('acodec') != 'none' else ""
                label = f"🎬 {height}p{note}"
                final_format_id = format_id if note else f"{format_id}+bestaudio/best"
                videos.append({'label': label, 'id': final_format_id, 'height': height})

        if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
            abr = f.get('abr')
            if abr:
                label = f"🎵 {int(float(abr))}k"
                audios.append({'label': label, 'id': format_id, 'abr': abr})

    unique_videos = list({v['label']: v for v in videos}.values())
    unique_audios = list({a['label']: a for a in audios}.values())
    unique_videos.sort(key=lambda x: x['height'], reverse=True)
    if unique_audios:
        unique_audios.sort(key=lambda x: int(float(x['abr'])), reverse=True)
        unique_audios.append({'label': '🎵 MP3 (تحويل)', 'id': 'bestaudio_to_mp3'})
        
    return {'videos': unique_videos, 'audios': unique_audios}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    welcome_message = (
        f"<b>»»°^°«« | مرحباً بك عزيزي {user.mention_html()}</b>\n\n"
        "<b>»»°^°«« | أنا بوت Video Downloads، لتحميل الوسائط من مختلف المنصات 📲</b>\n"
        "<b>»»°^°«« | فقط أرسل أي رابط من: يوتيوب، إنستغرام، تيك توك، وغيرها، وسأقوم بتحميله لك بأعلى جودة متاحة 🎬</b>\n\n"
        "<b>»»°^°«« | 🚀 أرسل الرابط الآن وابدأ التنزيل فوراً!</b>"
    )
    
    try:
        bot_photos = await context.bot.get_user_profile_photos(context.bot.id, limit=1)
        if bot_photos.total_count > 0:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=bot_photos.photos[0][-1].file_id,
                caption=welcome_message,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_html(welcome_message)
    except Exception as e:
        logger.error(f"Could not send welcome photo: {e}")
        await update.message.reply_html(welcome_message)


async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text
    context.user_data['last_url'] = url
    
    msg = await update.message.reply_sticker(sticker=STICKER_CHECKING)
    
    try:
        formats = get_clean_formats(url)
        keyboard = []
        
        video_buttons = [InlineKeyboardButton(v['label'], callback_data=json.dumps({'type': 'video', 'id': v['id']})) for v in formats['videos']]
        for i in range(0, len(video_buttons), 2):
            keyboard.append(video_buttons[i:i+2])
            
        audio_buttons = [InlineKeyboardButton(a['label'], callback_data=json.dumps({'type': 'audio', 'id': a['id']})) for a in formats['audios']]
        for i in range(0, len(audio_buttons), 2):
            keyboard.append(audio_buttons[i:i+2])

        if not keyboard:
            await msg.delete()
            await update.message.reply_text("عذرًا، لم أتمكن من العثور على أي صيغ تحميل مدعومة لهذا الرابط.")
            return

        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.delete()
        await update.message.reply_text('✅ <b>تم الفحص بنجاح!</b>\nاختر الصيغة المطلوبة من فضلك:', reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Error getting formats for URL {url}: {e}")
        await msg.delete()
        await update.message.reply_sticker(sticker=STICKER_ERROR)
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"⚠️ <b>عطل (فحص الرابط)</b>\n<b>المستخدم:</b> {update.effective_user.mention_html()}\n<b>الرابط:</b> {url}\n<b>الخطأ:</b> <pre>{e}</pre>",
            parse_mode='HTML'
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if 'last_url' not in context.user_data:
        await query.edit_message_text(text="عذرًا، انتهت صلاحية هذا الطلب. الرجاء إرسال الرابط مرة أخرى.")
        return
        
    url = context.user_data['last_url']
    data = json.loads(query.data)
    format_id = data.get('id')
    download_type = data.get('type')

    await query.message.delete()
    msg = await context.bot.send_sticker(chat_id=query.message.chat_id, sticker=STICKER_LOADING)

    try:
        output_template = os.path.join(DOWNLOADS_DIR, '%(title).40s - [%(id)s].%(ext)s')
        
        ydl_opts = {'outtmpl': output_template, 'noplaylist': True, 'format': format_id}
        
        is_mp3_conversion = (format_id == 'bestaudio_to_mp3')
        
        if is_mp3_conversion:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
        elif download_type == 'video':
            ydl_opts['merge_output_format'] = 'mp4'

        cookie_file = 'cookies.txt'
        if os.path.exists(cookie_file):
            ydl_opts['cookiefile'] = cookie_file
            logger.info("Using cookies file for downloading.")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            base_filename = ydl.prepare_filename(info)

            if is_mp3_conversion:
                final_filename, _ = os.path.splitext(base_filename)
                final_filename += '.mp3'
            elif download_type == 'video':
                final_filename, _ = os.path.splitext(base_filename)
                final_filename += '.mp4'
            else:
                final_filename = base_filename
        
        if os.path.exists(final_filename):
            await msg.delete()
            
            caption_text = f"👤 تم التحميل بواسطة: @{context.bot.username}"
            if download_type == 'audio' or is_mp3_conversion:
                await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(final_filename, 'rb'), caption=caption_text, write_timeout=180)
            else:
                await context.bot.send_video(chat_id=query.message.chat_id, video=open(final_filename, 'rb'), caption=caption_text, supports_streaming=True, write_timeout=180)
            
            os.remove(final_filename)
        else:
            raise FileNotFoundError(f"الملف الناتج لم يتم العثور عليه: {final_filename}")

    except Exception as e:
        logger.error(f"Error during download for user {query.from_user.id}: {e}")
        await msg.delete()
        await context.bot.send_sticker(chat_id=query.message.chat_id, sticker=STICKER_ERROR)
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"💣 <b>عطل (أثناء التحميل)</b>\n<b>المستخدم:</b> {query.from_user.mention_html()}\n<b>الرابط:</b> {url}\n<b>الصيغة:</b> {format_id}\n<b>الخطأ:</b> <pre>{e}</pre>",
            parse_mode='HTML'
        )
    finally:
        if 'last_url' in context.user_data:
            del context.user_data['last_url']

def main() -> None:
    persistence = PicklePersistence(filepath="bot_persistence")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).persistence(persistence).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    application.add_handler(CallbackQueryHandler(button_handler))

    print("The Dynamic, Polished, & Persistent Bot v15.0 is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
