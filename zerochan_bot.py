# --- FINAL SCRIPT - ULTRA-LIGHTWEIGHT MODE (NO SELENIUM) ---

import time
import json
import asyncio
import cloudscraper # Using cloudscraper to bypass anti-bot protection
from bs4 import BeautifulSoup # The HTML parser
import os
import atexit
import random
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
JOB_INTERVAL = 300 # 5 minutes
MAX_RETRIES = 2; RETRY_DELAY = 10; TELEGRAM_PHOTO_LIMIT = 10485760

# --- URL Sources for Random Images ---
RANDOM_SOURCES = {
    "zerochan": "https://www.zerochan.net/random",
    "yandere": "https://yande.re/post/random"
}

# --- Bot's Memory ---
VOLUME_PATH = "/data"; SENT_IMAGES_FILE = os.path.join(VOLUME_PATH, "sent_images.json")
LOCK_FILE = os.path.join(VOLUME_PATH, "bot.lock")
sent_image_ids = set()

# --- Memory & Helper Functions (requests instead of Selenium) ---
def load_sent_images():
    try:
        with open(SENT_IMAGES_FILE, 'r') as f: return set(json.load(f))
    except FileNotFoundError: print("Memory file not found."); return set()

def save_sent_images(sent_set):
    os.makedirs(VOLUME_PATH, exist_ok=True)
    with open(SENT_IMAGES_FILE, 'w') as f: json.dump(list(sent_set), f, indent=4)

def download_image_to_memory(scraper, image_url: str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0...', 'Referer': image_url}
        response = scraper.get(image_url, headers=headers, timeout=45)
        response.raise_for_status(); return response.content
    except Exception as e: print(f"Download failed: {e}"); return None

async def send_file_with_retry(scraper, context: ContextTypes.DEFAULT_TYPE, chat_id, photo_url, caption):
    image_bytes = download_image_to_memory(scraper, photo_url)
    if not image_bytes: return False
    file_size = len(image_bytes)
    for attempt in range(MAX_RETRIES):
        try:
            if file_size < TELEGRAM_PHOTO_LIMIT: await context.bot.send_photo(chat_id=chat_id, photo=image_bytes, caption=caption)
            else: await context.bot.send_document(chat_id=chat_id, document=image_bytes, filename=photo_url.split('/')[-1], caption=caption)
            return True
        except TelegramError as e: print(f"Upload attempt {attempt + 1} failed: {e}"); await asyncio.sleep(RETRY_DELAY)
    return False

# --- Core Scraping Logic (NO SELENIUM) ---
def get_random_image(scraper, source_name, random_url):
    try:
        # Try a few times to get a unique image from this source
        for _ in range(5):
            print(f"Fetching random page from {source_name}...")
            # We need to allow redirects to find the final page URL
            response = scraper.get(random_url, allow_redirects=True, timeout=30)
            response.raise_for_status()
            
            final_url = response.url
            soup = BeautifulSoup(response.text, "html.parser")
            
            full_image_url, image_id = None, None
            
            if source_name == 'zerochan':
                image_id = "z_" + final_url.split('/')[-1].split('?')[0]
                if image_id not in sent_image_ids:
                    # Find the link with class="preview"
                    link_element = soup.select_one("a.preview")
                    if link_element: full_image_url = link_element.get('href')
            
            elif source_name == 'yandere':
                image_id = "y_" + final_url.split('/')[-1]
                if image_id not in sent_image_ids:
                    # Find the link with id="highres"
                    link_element = soup.select_one("a#highres")
                    if link_element: full_image_url = link_element.get('href')

            if full_image_url:
                print(f"Found new unique image: {image_id}")
                return {'id': image_id, 'url': full_image_url}
            else:
                print(f"Found a duplicate ({image_id}) or failed to parse. Retrying...")
                time.sleep(1)

        print("Failed to find a unique image after several attempts.")
        return None
        
    except Exception as e:
        print(f"Scraping failed for {source_name}. Error: {e}")
        return None

# --- Automatic Job ---
async def send_scheduled_image(context: ContextTypes.DEFAULT_TYPE):
    print("\n--- Running Scheduled Job ---")
    scraper = cloudscraper.create_scraper() # Create one scraper for the whole job
    source_name, random_url = random.choice(list(RANDOM_SOURCES.items()))
    print(f"Selected source for this run: {source_name}")
    
    image_data = get_random_image(scraper, source_name, random_url)
    
    if image_data:
        image_id, full_image_url = image_data['id'], image_data['url']
        caption = f"A random image from {source_name.capitalize()}"
        success = await send_file_with_retry(scraper, context, TELEGRAM_CHAT_ID, full_image_url, caption)
        if success:
            print(f"Successfully sent {image_id}. Updating memory.")
            sent_image_ids.add(image_id)
            save_sent_images(sent_image_ids)
    else:
        print("Job finished: Could not find a new image to send in this run.")

# --- Main function & Cleanup ---
def main():
    os.makedirs(VOLUME_PATH, exist_ok=True)
    if os.path.exists(LOCK_FILE):
        try:
            file_age = time.time() - os.path.getmtime(LOCK_FILE)
            if file_age > JOB_INTERVAL: print(f"Stale lock file found. Deleting..."); os.remove(LOCK_FILE)
            else: print("!!! Lock file found. Exiting. !!!"); return
        except Exception as e: print(f"Could not check lock file: {e}. Exiting."); return
    with open(LOCK_FILE, 'w') as f: f.write(str(os.getpid()))
    atexit.register(cleanup)
    
    global sent_image_ids; sent_image_ids = load_sent_images()
    print(f"Loaded {len(sent_image_ids)} image IDs from memory.")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: print("CRITICAL ERROR: Missing environment variables."); return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    job_queue = application.job_queue
    job_queue.run_repeating(send_scheduled_image, interval=JOB_INTERVAL, first=5)
    
    print(f"Scheduled job running every {JOB_INTERVAL} seconds. Bot is running in lightweight mode.")
    application.run_polling()

def cleanup():
    print("Shutdown signal received. Cleaning up...")
    if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)
    print("Cleanup complete.")

if __name__ == '__main__':
    main()
