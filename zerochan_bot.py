# --- FINAL SCRIPT - STABLE SEQUENTIAL DISCOVERY (ONE IMAGE PER RUN) ---

import time
import json
import asyncio
import requests
import os
import atexit
import random
from collections import deque
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
JOB_INTERVAL = 300 # 5 minutes
MAX_RETRIES = 2; RETRY_DELAY = 10; TELEGRAM_PHOTO_LIMIT = 10485760

# --- URL Sources for Wallpapers ---
WALLPAPER_SOURCES = {
    "zerochan": "https://www.zerochan.net/Mobile+Wallpaper",
    "yandere": "https://yande.re/post?tags=rating%3Asafe+order%3Adate"
}

# --- Bot's Memory ---
VOLUME_PATH = "/data"; SENT_IMAGES_FILE = os.path.join(VOLUME_PATH, "sent_images.json")
LOCK_FILE = os.path.join(VOLUME_PATH, "bot.lock")
sent_image_ids = set()

# --- Browser, Memory, and Helper Functions ---
def create_driver():
    """Creates a new, single-use browser instance for a task."""
    print("Starting new browser instance...")
    chrome_options = webdriver.ChromeOptions(); chrome_options.add_argument("--headless=new"); chrome_options.add_argument("--no-sandbox"); chrome_options.add_argument("--disable-dev-shm-usage"); chrome_options.add_argument("--disable-gpu"); chrome_options.add_argument("--single-process"); chrome_options.add_argument("--blink-settings=imagesEnabled=false"); chrome_options.add_argument("--window-size=1280,1024")
    service = Service(executable_path="/usr/local/bin/chromedriver-linux64/chromedriver")
    return webdriver.Chrome(service=service, options=chrome_options)

def load_sent_images():
    try:
        with open(SENT_IMAGES_FILE, 'r') as f: return set(json.load(f))
    except FileNotFoundError: print("Memory file not found."); return set()

def save_sent_images(sent_set):
    os.makedirs(VOLUME_PATH, exist_ok=True)
    with open(SENT_IMAGES_FILE, 'w') as f: json.dump(list(sent_set), f, indent=4)

def download_image_to_memory(image_url: str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0...', 'Referer': image_url}
        response = requests.get(image_url, headers=headers, timeout=45)
        response.raise_for_status(); return response.content
    except requests.RequestException as e: print(f"Download failed: {e}"); return None

async def send_file_with_retry(context: ContextTypes.DEFAULT_TYPE, chat_id, photo_url, caption):
    image_bytes = download_image_to_memory(photo_url)
    if not image_bytes: return False
    file_size = len(image_bytes)
    for attempt in range(MAX_RETRIES):
        try:
            if file_size < TELEGRAM_PHOTO_LIMIT: await context.bot.send_photo(chat_id=chat_id, photo=image_bytes, caption=caption)
            else: await context.bot.send_document(chat_id=chat_id, document=image_bytes, filename=photo_url.split('/')[-1], caption=caption)
            return True
        except TelegramError as e: print(f"Upload attempt {attempt + 1} failed: {e}"); await asyncio.sleep(RETRY_DELAY)
    return False

# --- Core Scraping Logic ---
def find_first_new_image(source_name, base_url):
    driver = None
    try:
        driver = create_driver()
        wait = WebDriverWait(driver, 45)
        
        current_page = 1
        max_pages_to_check = 10 # Safety limit

        while current_page <= max_pages_to_check:
            print(f"--- Browsing page {current_page} of {source_name} ---")
            
            page_candidates = []
            if source_name == 'zerochan':
                driver.get(f"{base_url}?p={current_page}")
                wait.until(EC.presence_of_element_located((By.ID, 'thumbs2')))
                gallery = driver.find_element(By.ID, 'thumbs2'); list_items = gallery.find_elements(By.TAG_NAME, 'li')
                for item in list_items:
                    page_url = item.find_element(By.TAG_NAME, 'a').get_attribute('href')
                    image_id = "z_" + page_url.split('/')[-1]
                    page_candidates.append({'id': image_id, 'url': page_url})
            
            elif source_name == 'yandere':
                driver.get(f"{base_url}&page={current_page}")
                wait.until(EC.presence_of_element_located((By.ID, 'post-list-posts')))
                gallery = driver.find_element(By.ID, 'post-list-posts'); list_items = gallery.find_elements(By.TAG_NAME, 'li')
                for item in list_items:
                    page_url = item.find_element(By.CLASS_NAME, 'thumb').get_attribute('href')
                    image_id = "y_" + page_url.split('/')[-1]
                    page_candidates.append({'id': image_id, 'url': page_url})

            if not page_candidates:
                print("No more images found on this page. Stopping search."); break

            for candidate in page_candidates:
                if candidate['id'] not in sent_image_ids:
                    print(f"Found new image: {candidate['id']}. Processing...")
                    driver.get(candidate['url'])
                    full_image_url = None
                    if source_name == 'zerochan': full_image_url = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a.preview"))).get_attribute('href')
                    elif source_name == 'yandere': full_image_url = wait.until(EC.visibility_of_element_located((By.ID, 'highres'))).get_attribute('href')
                    
                    if full_image_url:
                        return {'id': candidate['id'], 'url': full_image_url} # Return the very first new one we find
            
            print("No new images on this page. Checking next page...")
            current_page += 1
            time.sleep(2) # Small delay before loading next page
        
        print("Could not find any new images after checking several pages.")
        return None
        
    except Exception as e:
        print(f"Scraping failed for {source_name}. Error: {e}")
        return None
    finally:
        if driver: driver.quit()

# --- Automatic Job ---
async def send_scheduled_image(context: ContextTypes.DEFAULT_TYPE):
    print("\n--- Running Scheduled Job ---")
    
    # Pick a random source to browse
    source_name, base_url = random.choice(list(WALLPAPER_SOURCES.items()))
    print(f"Selected source for this run: {source_name}")
    
    image_data = find_first_new_image(source_name, base_url)
    
    if image_data:
        image_id, full_image_url = image_data['id'], image_data['url']
        caption = f"A new wallpaper from {source_name.capitalize()}"
        
        success = await send_file_with_retry(context, TELEGRAM_CHAT_ID, full_image_url, caption)
        
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
    print(f"Loaded {len(sent_image_ids)} previously sent image IDs from memory.")
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: print("CRITICAL ERROR: Missing environment variables."); return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Simple start command for user feedback
    async def start(update, context):
        await update.message.reply_text('Hello! This bot is running in automated mode and will post a new wallpaper every 5 minutes.')
    application.add_handler(CommandHandler("start", start))

    job_queue = application.job_queue
    job_queue.run_repeating(send_scheduled_image, interval=JOB_INTERVAL, first=5)
    
    print(f"Scheduled job running every {JOB_INTERVAL} seconds. Bot is running in automated sequential mode.")
    application.run_polling()

def cleanup():
    print("Shutdown signal received. Cleaning up...")
    if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)
    print("Cleanup complete.")

if __name__ == '__main__':
    main()
