import os
import asyncio
import logging
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from huggingface_hub import InferenceClient

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")

# Initialize Hugging Face Client
client = InferenceClient(token=HF_TOKEN)
MODEL_ID = "Wan-AI/Wan2.2-I2V-A14B-Diffusers:fastest"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! I can generate videos for you.\n\n"
        "1. Send me a **Photo** with a caption to use Image-to-Video.\n"
        "2. Send me a **Text message** to use Text-to-Video."
    )

async def handle_image_to_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Notify user we are processing
    status_msg = await update.message.reply_text("⏳ Processing your image... this may take a minute.")
    
    # Download the photo
    photo_file = await update.message.photo[-1].get_file()
    image_path = f"{update.message.chat_id}_input.png"
    await photo_file.download_to_drive(image_path)
    
    prompt = update.message.caption if update.message.caption else "Cinematic motion, high quality"

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Call Hugging Face API
        video_bytes = client.image_to_video(
            image=image_data,
            model=MODEL_ID,
            parameters={"prompt": prompt}
        )

        video_path = f"{update.message.chat_id}_output.mp4"
        with open(video_path, "wb") as f:
            f.write(video_bytes)

        await update.message.reply_video(video=open(video_path, 'rb'), caption=f"Done! Prompt: {prompt}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        # Clean up files
        if os.path.exists(image_path): os.remove(image_path)
        if os.path.exists(video_path): os.remove(video_path)
        await status_msg.delete()

async def handle_text_to_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    status_msg = await update.message.reply_text("🎬 Generating video from your text...")

    try:
        # Note: Using the same model endpoint, checking if it supports direct T2V
        video_bytes = client.text_to_video(
            prompt,
            model=MODEL_ID
        )

        video_path = f"{update.message.chat_id}_t2v_output.mp4"
        with open(video_path, "wb") as f:
            f.write(video_bytes)

        await update.message.reply_video(video=open(video_path, 'rb'))
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
    finally:
        if os.path.exists(video_path): os.remove(video_path)
        await status_msg.delete()

if __name__ == '__main__':
    if not BOT_TOKEN or not HF_TOKEN:
        print("Error: BOT_TOKEN or HF_TOKEN environment variables not set.")
        exit(1)

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image_to_video))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_to_video))
    
    print("Bot is running...")
    application.run_polling()
