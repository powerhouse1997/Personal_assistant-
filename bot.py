# bot.py

import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update, Bot
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
                # If file is corrupt or empty, start fresh
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
        # Add a user-agent header to look like a normal browser
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=15, headers=headers)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        soup = BeautifulSoup(response.text, 'html.parser')

        if filter_keyword:
            body_text = soup.body.get_text().lower()
            if filter_keyword.lower() not in body_text:
                return [] # Return empty if filter keyword is not on the page

        # Find all video tags and their sources
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
    return list(dict.fromkeys(video_links)) # Return unique links

# --- Scheduled Job ---
async def check_for_new_videos(context: ContextTypes.DEFAULT_TYPE):
    """Checks for new videos based on subscriptions and filters."""
    bot = context.bot
    data = load_data()
    subscriptions = data.get("subscriptions", {})
    
    # Iterate over a copy of items to allow modification during loop
    for chat_id, subs in list(subscriptions.items()):
        for sub_info in list(subs):
            url = sub_info.get("url")
            actress_name = sub_info.get("filter")
            
            logger.info(f"Checking {url} for new videos of '{actress_name}' for chat {chat_id}")
            latest_videos = extract_video_links(url, filter_keyword=actress_name)
            
            # Ensure the structure for sent videos exists
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

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    await update.message.reply_text(
        "Hi! I'm a video link sharing bot.\n\n"
        "Commands:\n"
        "/subscribe <URL> <ActressName> - Get updates for an actress from a URL.\n"
        "/unsubscribe <URL> - Stop getting updates for a URL.\n"
        "/list - See your current subscriptions.\n"
        "/recent <ActressName> - Get recent videos for a subscribed actress.\n\n"
        "You can also send me a URL directly to check for videos once (without filter)."
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribes a chat to a URL with an actress name filter."""
    chat_id = str(update.effective_chat.id)
    try:
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /subscribe <URL> <ActressName>")
            return

        url = context.args[0]
        actress_name = " ".join(context.args[1:])
        
        if not (url.startswith('http://') or url.startswith('https://')):
            await update.message.reply_text("Please provide a valid URL starting with http:// or https://")
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
    """Unsubscribes a chat from all filters associated with a URL."""
    chat_id = str(update.effective_chat.id)
    try:
        url_to_remove = context.args[0]
        data = load_data()
        if chat_id in data.get("subscriptions", {}):
            initial_len = len(data["subscriptions"][chat_id])
            data["subscriptions"][chat_id] = [sub for sub in data["subscriptions"][chat_id] if sub.get("url") != url_to_remove]
            
            if len(data["subscriptions"][chat_id]) < initial_len:
                if not data["subscriptions"][chat_id]:
                    del data["subscriptions"][chat_id] # Clean up empty list
                save_data(data)
                await update.message.reply_text(f"You have unsubscribed from all filters on {url_to_remove}")
            else:
                await update.message.reply_text("You were not subscribed to this URL.")
        else:
            await update.message.reply_text("You have no subscriptions.")
    except IndexError:
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

async def get_recent_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a list of recently found videos for a subscribed actress."""
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
    """Handles a direct URL message for a one-time check."""
    url = update.message.text
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("This doesn't look like a valid URL. Please send a full URL starting with http:// or https://")
        return
        
    await update.message.reply_text(f"Checking {url} for videos...")
    video_links = extract_video_links(url) # No filter keyword
    
    if video_links:
        message = f"Found {len(video_links)} video(s) on {url}:\n\n"
        message += "\n".join(video_links)
    else:
        message = f"Sorry, I couldn't find any direct video links on {url}."
        
    await update.message.reply_text(message)

def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- Scheduler Setup ---
    scheduler = AsyncIOScheduler()
    # Pass the application context to the job
    scheduler.add_job(check_for_new_videos, 'interval', minutes=30, args=[application])
    scheduler.start()

    # --- Handlers ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe))
    application.add_handler(CommandHandler("list", list_subscriptions))
    application.add_handler(CommandHandler("recent", get_recent_videos))
    
    # This handler must be last
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_direct_url))

    # Run the bot
    logger.info("Bot is starting...")
    application.run_polling()


if __name__ == '__main__':
    main()
