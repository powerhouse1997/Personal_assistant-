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
    """
    Fetches a webpage, optionally filters by a keyword in the page body, 
    and then extracts video links from it.
    """
    video_links = []
    try:
        response = requests.get(url, timeout=10)
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
    return video_links

# --- Scheduled Job ---
async def check_for_new_videos(context: ContextTypes.DEFAULT_TYPE):
    """Checks for new videos based on subscriptions and filters."""
    data = load_data()
    subscriptions = data.get("subscriptions", {})
    
    for chat_id, subs in list(subscriptions.items()):
        for sub_info in subs:
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
                    await context.bot.send_message(chat_id=chat_id, text=message)
                    sent_videos_for_url.append(video_link)
    save_data(data)


# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    await update.message.reply_text(
        "Hi! I'm a video link sharing bot.\n\n"
        "Commands:\n"
        "/subscribe <URL> <ActressName> - Get updates for an actress from a URL.\n"
        "/unsubscribe <URL> - Stop getting updates for a URL.\n"
        "/list - See your current subscriptions.\n\n"
        "You can also send me a URL directly to check for videos once (without filter)."
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribes a chat to a URL with an actress name filter."""
    chat_id = str(update.effective_chat.id)
    try:
        url = context.args[0]
        actress_name = " ".join(context.args[1:])
        
        if not actress_name:
            await update.message.reply_text("Please provide an actress name. Usage: /subscribe <URL> <ActressName>")
            return

        if not (url.startswith('http://') or url.startswith('https://')):
            await update.message.reply_text("Please provide a valid URL.")
            return

        data = load_data()
        subscriptions_for_chat = data.setdefault("subscriptions", {}).setdefault(chat_id, [])
        sub_exists = any(sub.get("url") == url and sub.get("filter") == actress_name for sub in subscriptions_for_chat)

        if not sub_exists:
            subscriptions_for_chat.append({"url": url, "filter": actress_name})
            save_data(data)
            await update.message.reply_text(f"You are now subscribed to '{actress_name}' on {url}")
        else:
            await update.message.reply_text("You are already subscribed to this actress on this URL.")

    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /subscribe <URL> <ActressName>")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribes a chat from a URL."""
    chat_id = str(update.effective_chat.id)
    try:
        url_to_remove = context.args[0]
        data = load_data()
        if chat_id in data.get("subscriptions", {}):
            initial_len = len(data["subscriptions"][chat_id])
            data["subscriptions"][chat_id] = [sub for sub in data["subscriptions"][chat_id] if sub.get("url") != url_to_remove]
            
            if len(data["subscriptions"][chat_id]) < initial_len:
                if not data["subscriptions"][chat_id]:
                    del data["subscriptions"][chat_id]
                save_data(data)
                await update.message.reply_text(f"You have unsubscribed from all filters on {url_to_remove}")
            else:
                await update.message.reply_text("You are not subscribed to this URL.")
        else:
            await update.message.reply_text("You have no subscriptions.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /unsubscribe <URL>")

async def list_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lists all active subscriptions for the chat."""
    chat_id = str(update.effective_chat.id)
    data = load_data()
    if chat_id in data.get("subscriptions", {}) and data["subscriptions"][chat_id]:
        message = "You are subscribed to:\n"
        for sub in data["subscriptions"][chat_id]:
            message += f"- URL: {sub.get('url')}\n  Filter: '{sub.get('filter')}'\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("You have no active subscriptions.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles non-command messages, expecting a URL for a one-time check."""
    message_text = update.message.text
    if message_text.startswith('http://') or message_text.startswith('https://'):
        await update.message.reply_text("Processing your link (one-time check, no filter)...")
        video_links = extract_video_links(message_text)

        if video_links:
            response_message = "Here are the video links I found:\n\n"
            for link in video_links:
                response_message += f"- {link}\n"
        else:
            response_message = "Sorry, I couldn't find any direct video links on that page."

        await update.message.reply_text(response_message)
    else:
        await update.message.reply_text("Please send me a valid URL or use a command.")

async def main() -> None:
    """Start the bot and the scheduler."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return
        
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("list", list_subscriptions))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_for_new_videos, 'interval', hours=1, args=[application])
    scheduler.start()

    logger.info("Starting bot...")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
