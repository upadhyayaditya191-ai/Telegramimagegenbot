import os
import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from huggingface_hub import InferenceClient
from dotenv import load_dotenv  # optional (local .env ke liye)

load_dotenv()  # Render par ye line kuch nahi karegi, local testing mein help karegi

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")

if not BOT_TOKEN or not HF_TOKEN:
    logging.error("BOT_TOKEN ya HF_TOKEN set nahi hai. Environment variables check karein.")
    exit(1)

# Hugging Face Client
client = InferenceClient(token=HF_TOKEN)

# Models
I2V_MODEL = "Wan-AI/Wan2.2-I2V-A14B-Diffusers:fastest"
T2V_MODEL = "ali-vilab/i2vgen-xl"   # <-- Text-to-Video ke liye sahi model daalein (ya apna pasandida)

# -------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! Main videos generate kar sakta hoon.\n\n"
        "1. Photo bhejo caption ke saath → Image to Video\n"
        "2. Sirf text bhejo → Text to Video"
    )

# -------------------------------------------------------------------
# Image-to-Video Handler
# -------------------------------------------------------------------
async def handle_image_to_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = await update.message.reply_text("⏳ Image process ho rahi hai... (1-2 min)")

    # Image download karo
    photo_file = await update.message.photo[-1].get_file()
    image_path = f"{update.message.chat_id}_input.png"
    await photo_file.download_to_drive(image_path)

    prompt = update.message.caption if update.message.caption else "Cinematic motion, high quality"

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Blocking API call ko async thread mein daalo
        video_bytes = await asyncio.to_thread(
            client.image_to_video,
            image=image_data,
            model=I2V_MODEL,
            parameters={"prompt": prompt},
            wait_for_model=True,   # cold start ke liye wait karega
        )

        video_path = f"{update.message.chat_id}_output.mp4"
        with open(video_path, "wb") as f:
            f.write(video_bytes)

        # Telegram 50 MB limit check
        file_size = os.path.getsize(video_path)
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ Video 50 MB se badi hai. Telegram accept nahi karega.")
        else:
            await update.message.reply_video(
                video=open(video_path, 'rb'),
                caption=f"✅ Done! Prompt: {prompt}"
            )

    except Exception as e:
        logging.error(f"I2V error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        # Cleanup
        if os.path.exists(image_path):
            os.remove(image_path)
        if os.path.exists(video_path):
            os.remove(video_path)
        await status_msg.delete()

# -------------------------------------------------------------------
# Text-to-Video Handler
# -------------------------------------------------------------------
async def handle_text_to_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    status_msg = await update.message.reply_text("🎬 Text se video bana raha hoon...")

    try:
        # Blocking API call ko async thread mein daalo
        video_bytes = await asyncio.to_thread(
            client.text_to_video,
            prompt,
            model=T2V_MODEL,
            wait_for_model=True
        )

        video_path = f"{update.message.chat_id}_t2v_output.mp4"
        with open(video_path, "wb") as f:
            f.write(video_bytes)
# Size check
        file_size = os.path.getsize(video_path)
        if file_size > 50 * 1024 * 1024:
            await update.message.reply_text("❌ Video 50 MB se badi hai. Telegram accept nahi karega.")
        else:
            await update.message.reply_video(video=open(video_path, 'rb'))

    except Exception as e:
        logging.error(f"T2V error: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)
        await status_msg.delete()

# -------------------------------------------------------------------
# Main (Polling)
# -------------------------------------------------------------------
if name == 'main':
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image_to_video))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_to_video))

    print("Bot running...")
    application.run_polling()