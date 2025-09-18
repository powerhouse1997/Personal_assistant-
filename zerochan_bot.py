import logging
import requests
import os
import time
from telegram import Update, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- Basic Configuration ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
YANDERE_API_URL = 'https://yande.re/post.json'

# --- Scraper Configuration ---
SAVE_PATH = 'downloads/'
PIC_TYPE_URL = 'sample_url' # 'sample_url' is safer to avoid large file sizes

# --- Helper function to check for existing files ---
def get_donwloaded_list():
    """Gets a list of already downloaded file IDs. Less critical now, but good for resuming."""
    downloaded_list = []
    if not os.path.exists(SAVE_PATH):
        os.makedirs(SAVE_PATH)
    for file_name in os.listdir(SAVE_PATH):
        if os.path.splitext(file_name)[1] in ['.jpg', '.png', '.jpeg']:
            downloaded_list.append(os.path.splitext(file_name)[0])
    return downloaded_list

# --- Core Scraper, Sender, and Deleter Logic ---

async def run_crawl_send_delete_logic(update: Update, context: ContextTypes.DEFAULT_TYPE, score_threshold: int, start_page: int, end_page: int):
    """
    Crawls Yande.re, downloads, sends to chat, and then deletes the local file.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    downloaded_list = get_donwloaded_list()
    total_sent_count = 0
    chat_id = update.effective_chat.id
    
    # NEW: Lists to manage the current album batch
    media_group_items = []
    paths_in_current_group = [] # Stores file paths for deletion after sending

    await context.bot.send_message(chat_id=chat_id, text=f"Found {len(downloaded_list)} existing images. Starting crawl...")

    for page in range(start_page, end_page + 1):
        try:
            progress_message = await context.bot.send_message(chat_id=chat_id, text=f"Processing Page: {page}...")
            
            params = {'page': page, 'limit': 100}
            response = requests.get(YANDERE_API_URL, params=params, headers=headers, timeout=20)
            response.raise_for_status()
            posts = response.json()

            if not posts:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=progress_message.message_id, text=f"Page {page} is empty. Stopping.")
                break

            for post in posts:
                post_id = str(post.get('id'))
                score = post.get('score', 0)
                image_url = post.get(PIC_TYPE_URL)

                if score >= score_threshold and post_id not in downloaded_list and image_url:
                    try:
                        file_ext = os.path.splitext(image_url.split('?')[0])[1]
                        file_name = f"{post_id}{file_ext}"
                        file_path = os.path.join(SAVE_PATH, file_name)

                        # 1. Download
                        img_response = requests.get(image_url, headers=headers, timeout=30)
                        img_response.raise_for_status()
                        with open(file_path, 'wb') as f:
                            f.write(img_response.content)
                        
                        # 2. Add to send queue and deletion queue
                        media_group_items.append(InputMediaPhoto(media=open(file_path, 'rb')))
                        paths_in_current_group.append(file_path) # Add path for future deletion
                        
                        total_sent_count += 1
                        downloaded_list.append(post_id)

                        # 3. Send and Delete when album is full
                        if len(media_group_items) == 10:
                            await context.bot.send_media_group(chat_id=chat_id, media=media_group_items)
                            
                            # NEW: Delete the sent files
                            logging.info(f"Album sent. Deleting {len(paths_in_current_group)} files.")
                            for path in paths_in_current_group:
                                try:
                                    os.remove(path)
                                except Exception as e:
                                    logging.error(f"Failed to delete file {path}: {e}")
                            
                            media_group_items = []
                            paths_in_current_group = []
                            time.sleep(1)

                    except Exception as e:
                        logging.error(f"An error occurred with image {post_id}: {e}")
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_message.message_id,
                text=f"Finished Page {page}. Found {len(paths_in_current_group)} new images in current batch."
            )
            time.sleep(1)

        except Exception as e:
            logging.error(f"An error occurred on page {page}: {e}")
            await context.bot.send_message(chat_id=chat_id, text=f"An error occurred on page {page}. Skipping.")
            continue

    # After the loops, send and delete any remaining photos
    if media_group_items:
        await context.bot.send_media_group(chat_id=chat_id, media=media_group_items)
        logging.info(f"Final album sent. Deleting {len(paths_in_current_group)} files.")
        for path in paths_in_current_group:
            try:
                os.remove(path)
            except Exception as e:
                logging.error(f"Failed to delete file {path}: {e}")

    return total_sent_count

# --- Telegram Bot Command Handlers (Unchanged) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start and /help commands."""
    help_text = (
        "Welcome! This bot downloads images from Yande.re and sends them to you.\n\n"
        "**Usage:**\n"
        "`/crawl <min_score> <start_page> <end_page>`\n\n"
        "**Example:** `/crawl 150 1 3`"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def crawl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /crawl command. Parses arguments and starts the scraper."""
    chat_id = update.effective_chat.id
    try:
        if len(context.args) != 3:
            await update.message.reply_text("Usage: /crawl <min_score> <start_page> <end_page>")
            return

        score = int(context.args[0])
        start_page = int(context.args[1])
        end_page = int(context.args[2])

        if start_page <= 0 or end_page < start_page:
            await update.message.reply_text("Invalid page range.")
            return

        await update.message.reply_text(f"✅ Task accepted! Crawling pages {start_page}-{end_page} for score >= {score}.")
        
        sent_count = await run_crawl_send_delete_logic(update, context, score, start_page, end_page)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎉 Crawl finished! 🎉\n\nSent a total of {sent_count} new images."
        )

    except (IndexError, ValueError):
        await update.message.reply_text("Invalid arguments. Please use three numbers.")
    except Exception as e:
        logging.error(f"A critical error occurred in crawl_command: {e}")
        await context.bot.send_message(chat_id=chat_id, text=f"A critical error occurred: {e}")

# --- Main Bot Execution ---

def main():
    """Main function to set up and run the bot."""
    TOKEN = os.environ.get('BOT_TOKEN')
    if not TOKEN:
        # Fallback for local testing if environment variable is not set
        TOKEN = '7853195961:AAFYxGjDa2yUtIGviUR29KBApXXpXXxoTss' 
        if TOKEN == '7853195961:AAFYxGjDa2yUtIGviUR29KBApXXpXXxoTss':
            print("ERROR: BOT_TOKEN environment variable not set and no fallback token provided!")
            return
    
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler(['start', 'help'], start_command))
    application.add_handler(CommandHandler('crawl', crawl_command))

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
