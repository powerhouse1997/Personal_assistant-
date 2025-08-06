# bot.py

import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import json
import os
import asyncio

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_FILE = "bot_data.json"

# --- Data Handling ---
def load_data():
    """Loads subscriptions and sent videos from a JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"subscriptions": {}, "sent_videos": {}}
    return {"subscriptions": {}, "sent_videos": {}}

def save_data(data):
    """Saves data to a JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- Helper Function to Extract Video Links ---
def extract_video_links(url: str, filter_keyword: str = None) -> list[str]:
    video_links = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        if filter_keyword:
            body_text = soup.body.get_text().lower()
            if filter_keyword.lower() not in body_text:
                return []
        for video_tag in soup.find_all('video'):
            if video_tag.has_attr('src'):
                video_links.append(video_tag['src'])
            for source_tag in video_tag.find_all('source'):
                if source_tag.has_attr('src'):
                    video_links.append(source_tag['src'])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
    except Exception as e:
        logger.error(f"An error occurred during scraping: {e}")
    return list(dict.fromkeys(video_links))

# --- Scheduled Job ---
async def check_for_new_videos(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    data = load_data()
    subscriptions = data.get("subscriptions", {})
    for chat_id, subs in list(subscriptions.items()):
        for sub_info in list(subs):
            url = sub_info.get("url")
            actress_name = sub_info.get("filter")
            logger.info(f"Checking {url} for new videos of '{actress_name}' for chat {chat_id}")
            latest_videos = extract_video_links(url, filter_keyword=actress_name)
            sent_videos_for_url = data.setdefault("sent_videos", {}).setdefault(url, [])
            new_videos = [video for video in latest_videos if video not in sent_videos_for_url]
            if new_videos:
                logger.info(f"Found {len(new_videos)} new videos on {url} for chat {chat_id}")
                for video_link in new_videos:
                    message = f"New video of '{actress_name}' found on {url}:\n{video_link}"
                    try:
                        await bot.send_message(chat_id=chat_id, text=message)
                        sent_videos_for_url.append(video_link)
                    except Exception as e:
                        logger.error(f"Failed to send message to chat {chat_id}: {e}")
    save_data(data)

# --- Telegram Bot Handlers (No changes here) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hi! I'm a video link sharing bot...")
# ... (all other handler functions like subscribe, unsubscribe, etc. remain the same)
# ...
async def get_recent_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    try:
        actress_name_query = " ".join(context.args)
        if not actress_name_query:
            await update.message.reply_text("Usage: /recent <ActressName>")
            return
        data = load_data()
        subscriptions = data.get("subscriptions", {}).get(chat_id, [])
        sent_videos = data.get("sent_videos", {})
        found_video_links = []
        matching_subs = [sub for sub in subscriptions if sub.get("filter", "").lower() == actress_name_query.lower()]
        if not matching_subs:
            await update.message.reply_text(f"You are not subscribed to '{actress_name_query}'. Use /subscribe first.")
            return
        for sub in matching_subs:
            url = sub.get("url")
            if url in sent_videos:
                found_video_links.extend(sent_videos[url])
        if found_video_links:
            unique_links = list(dict.fromkeys(found_video_links))
            message = f"Recently found videos for '{actress_name_query}':\n\n"
            message += "\n".join(unique_links)
            await update.message.reply_text(message)
        else:
            await update.message.reply_text(f"You are subscribed to '{actress_name_query}', but no videos have been found and sent yet.")
    except Exception as e:
        logger.error(f"Error in /recent command: {e}")
        await update.message.reply_text("An unexpected error occurred while fetching recent videos.")

async def handle_direct_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.message.text
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("This doesn't look like a valid URL. Please send a full URL starting with http:// or https://")
        return
    await update.message.reply_text(f"Checking {url} for videos...")
    video_links = extract_video_links(url)
    if video_links:
        message = f"Found {len(video_links)} video(s) on {url}:\n\n"
        message += "\n".join(video_links)
    else:
        message = f"Sorry, I couldn't find any direct video links on {url}."
    await update.message.reply_text(message)

# --- MODIFIED: post_init now also stores the scheduler ---
async def post_init(application: Application) -> None:
    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(check_for_new_videos, 'interval', minutes=30, job_defaults={'misfire_grace_time': 300})
    scheduler.start()
    # Store the scheduler in the bot_data so we can access it in main() for shutdown
    application.bot_data["scheduler"] = scheduler
    logger.info("Scheduler started and stored in bot_data.")

# --- MODIFIED: main function uses manual startup and shutdown ---
async def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("list", list_subscriptions))
    application.add_handler(CommandHandler("recent", get_recent_videos))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_direct_url))

    # --- Manual startup and shutdown ---
    try:
        logger.info("Initializing application...")
        await application.initialize()
        logger.info("Starting updater...")
        await application.updater.start_polling()
        logger.info("Starting application...")
        await application.start()
        logger.info("Bot is now running. Press Ctrl-C to stop.")
        
        # Keep the script running until interrupted
        while True:
            await asyncio.sleep(3600) # Sleep for a long time
            
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
        
    finally:
        logger.info("Shutting down...")
        # Retrieve the scheduler from bot_data for shutdown
        if application.bot_data.get("scheduler"):
            logger.info("Shutting down scheduler...")
            application.bot_data["scheduler"].shutdown()

        if application.updater.running:
             logger.info("Stopping updater...")
             await application.updater.stop()
        if application.running:
            logger.info("Stopping application...")
            await application.stop()
            
        logger.info("Shutting down application...")
        await application.shutdown()
        logger.info("Shutdown complete.")


if __name__ == '__main__':
    asyncio.run(main())
