# --- FINAL SCRIPT - PREPARED FOR RAILWAY HOSTING ---

import time
import json
import asyncio
import requests
import os # <-- IMPORTANT
from collections import deque
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram import InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# --- Configuration (READ FROM ENVIRONMENT VARIABLES) ---
# Railway will provide these values. DO NOT hardcode them here.
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

MAX_RETRIES = 3; RETRY_DELAY = 10; JOB_INTERVAL = 90

# --- URL Lists ---
URLS_TO_SCRAPE = [
    "https://www.zerochan.net/",
    "https://www.zerochan.net/Genshin+Impact",
    "https://www.zerochan.net/Honkai%3A+Star+Rail"
]
MOBILE_WALLPAPER_URL = "https://www.zerochan.net/Mobile+Wallpaper"

# --- Bot's Memory (USES RAILWAY'S PERSISTENT VOLUME) ---
# Railway will mount a persistent volume at /data
VOLUME_PATH = "/data"
WALLPAPER_MEMORY_FILE = os.path.join(VOLUME_PATH, "sent_wallpapers.json")
sent_urls = deque(maxlen=50); last_known_images = {}; sent_wallpapers = set()
driver_instance = None

# --- Browser Management ---
def get_driver():
    global driver_instance
    if driver_instance is None:
        print("Starting new browser instance...")
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox") # CRUCIAL for Linux containers
        chrome_options.add_argument("--disable-dev-shm-usage") # CRUCIAL for Linux containers
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        service = Service() # Dockerfile will ensure chromedriver is in PATH
        driver_instance = webdriver.Chrome(service=service, options=chrome_options)
    return driver_instance

def quit_driver():
    global driver_instance
    if driver_instance:
        print("Closing the shared browser instance.")
        driver_instance.quit()
        driver_instance = None

# --- Memory Functions ---
def load_sent_wallpapers():
    try:
        with open(WALLPAPER_MEMORY_FILE, 'r') as f: return set(json.load(f))
    except FileNotFoundError: print("Memory file not found. Starting fresh."); return set()

def save_sent_wallpapers(sent_set):
    # Ensure the /data directory exists
    os.makedirs(VOLUME_PATH, exist_ok=True)
    with open(WALLPAPER_MEMORY_FILE, 'w') as f: json.dump(list(sent_set), f, indent=4)

# --- Helper Functions (Unchanged) ---
def download_image_to_memory(image_url: str):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 ...', 'Referer': 'https://www.zerochan.net/'}
        response = requests.get(image_url, headers=headers, timeout=20)
        response.raise_for_status(); return response.content
    except requests.RequestException as e: print(f"Download failed: {e}"); return None

async def send_photo_with_retry(context: ContextTypes.DEFAULT_TYPE, chat_id, photo_url, caption):
    image_bytes = download_image_to_memory(photo_url)
    if not image_bytes: return False
    for attempt in range(MAX_RETRIES):
        try: await context.bot.send_photo(chat_id=chat_id, photo=image_bytes, caption=caption); return True
        except TelegramError as e:
            print(f"Upload attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1: await asyncio.sleep(RETRY_DELAY)
    return False

# --- Scraping & Command Functions (Logic is the same, just removed hardcoded paths) ---
def get_latest_image_from_url(url: str):
    try:
        driver = get_driver()
        driver.get(url)
        wait = WebDriverWait(driver, 30)
        wait.until(EC.presence_of_element_located((By.ID, 'thumbs2')))
        gallery = driver.find_element(By.ID, 'thumbs2'); first_item = gallery.find_element(By.TAG_NAME, 'li')
        page_link = first_item.find_element(By.TAG_NAME, 'a').get_attribute('href'); driver.get(page_link)
        image_link_element = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a.preview")))
        return image_link_element.get_attribute('href')
    except Exception as e:
        print(f"Scraping failed for {url}. Restarting browser. Error: {e}")
        quit_driver()
        return None

async def start(update, context):
    await update.message.reply_text(f'Hello! I am monitoring {len(URLS_TO_SCRAPE)} URLs automatically.')

async def get_image(update, context):
    await update.message.reply_text(f'Fetching latest image...')
    image_url = get_latest_image_from_url(URLS_TO_SCRAPE[0])
    if image_url: await send_photo_with_retry(context, update.effective_chat.id, image_url, "Here is the latest image!")
    else: await update.message.reply_text('Sorry, could not retrieve an image.')

async def get_wallpaper(update, context):
    await update.message.reply_text('Searching for up to 10 NEW mobile wallpapers...')
    try:
        driver = get_driver(); wait = WebDriverWait(driver, 30)
        driver.get(MOBILE_WALLPAPER_URL); wait.until(EC.presence_of_element_located((By.ID, 'thumbs2')))
        list_items = driver.find_element(By.ID, 'thumbs2').find_elements(By.TAG_NAME, 'li')[:40]
        new_wallpaper_pages = []
        for item in list_items:
            page_url = item.find_element(By.TAG_NAME, 'a').get_attribute('href'); image_id = page_url.split('/')[-1]
            if image_id not in sent_wallpapers: new_wallpaper_pages.append(page_url)
            if len(new_wallpaper_pages) >= 10: break
        if new_wallpaper_pages:
            media_group, newly_sent_ids = [], []
            for page_url in new_wallpaper_pages:
                try:
                    driver.get(page_url)
                    full_image_url = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a.preview"))).get_attribute('href')
                    image_bytes = download_image_to_memory(full_image_url)
                    if image_bytes: media_group.append(InputMediaPhoto(media=image_bytes)); newly_sent_ids.append(page_url.split('/')[-1])
                except Exception as e: print(f"Failed to process page {page_url}. SKIPPING. Error: {e}")
            if media_group:
                send_success = False
                for attempt in range(MAX_RETRIES):
                    try: await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media_group); send_success = True; break
                    except TelegramError as e: print(f"Album send attempt {attempt + 1} failed: {e}"); await asyncio.sleep(RETRY_DELAY)
                if send_success:
                    await update.message.reply_text(f"Here are {len(media_group)} new wallpapers!"); sent_wallpapers.update(newly_sent_ids); save_sent_wallpapers(sent_wallpapers)
        else: await update.message.reply_text("No new wallpapers found.")
    except Exception as e:
        print(f"Critical error in get_wallpaper: {e}"); await update.message.reply_text("Sorry, an error occurred.")
        quit_driver()

async def send_scheduled_image(context: ContextTypes.DEFAULT_TYPE):
    print("\n--- Running Scheduled Job ---")
    for url in URLS_TO_SCRAPE:
        try:
            print(f"\nChecking URL: {url}"); latest_image_url = get_latest_image_from_url(url)
            if not latest_image_url: raise ValueError("Scraping returned no URL.")
            last_seen_url = last_known_images.get(url)
            if latest_image_url != last_seen_url and latest_image_url not in sent_urls:
                print(f"NEW IMAGE FOUND on {url}!")
                success = await send_photo_with_retry(context, TELEGRAM_CHAT_ID, latest_image_url, f"New image from: {url}")
                if success: last_known_images[url] = latest_image_url; sent_urls.append(latest_image_url)
            else: print("No new image found.")
        except Exception as e: print(f"Job failed for URL: {url}. Reason: {e}. MOVING TO NEXT URL."); continue

# --- Main function ---
def main():
    global sent_wallpapers; sent_wallpapers = load_sent_wallpapers()
    print(f"Loaded {len(sent_wallpapers)} wallpaper IDs from memory.")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("CRITICAL ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in environment variables.")
        return
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start)); application.add_handler(CommandHandler("get_image", get_image)); application.add_handler(CommandHandler("wallpaper", get_wallpaper))
    job_queue = application.job_queue; job_queue.run_repeating(send_scheduled_image, interval=JOB_INTERVAL, first=5)
    print(f"Scheduled job running every {JOB_INTERVAL} seconds. Bot is running.")
    application.run_polling()

if __name__ == '__main__':
    try:
        main()
    finally:
        quit_driver()
