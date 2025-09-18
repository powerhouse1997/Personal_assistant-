# --- FINAL SCRIPT - STABLE LOCKING & HEARTBEAT ---

import time
import json
import asyncio
import requests
import os
import atexit
from collections import deque
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram import InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
JOB_INTERVAL = 300
MAX_RETRIES = 2; RETRY_DELAY = 10; TELEGRAM_PHOTO_LIMIT = 10485760

# --- URL Lists ---
URLS_TO_SCRAPE = ["https://www.zerochan.net/", "https://yande.re/post"]
ZEROCHAN_WALLPAPER_URL = "https://www.zerochan.net/Mobile+Wallpaper"
YANDERE_WALLPAPER_URL = "https://yande.re/post?tags=rating%3Asafe+order%3Adate"

# --- Bot's Memory, Global Browser, and Lock ---
VOLUME_PATH = "/data"; WALLPAPER_MEMORY_FILE = os.path.join(VOLUME_PATH, "sent_wallpapers.json")
LOCK_FILE = os.path.join(VOLUME_PATH, "bot.lock")
sent_urls = deque(maxlen=100); last_known_images = {}; sent_wallpapers = set()
driver_instance = None
scraper_lock = asyncio.Lock()

# --- Browser Management with Heartbeat ---
def get_driver():
    global driver_instance
    # Heartbeat check
    if driver_instance:
        try:
            # A simple, non-blocking check to see if the browser is responsive
            _ = driver_instance.current_url
        except Exception as e:
            print(f"Browser heartbeat failed: {e}. Restarting instance.")
            quit_driver()
    
    if driver_instance is None:
        print("Starting new browser instance...")
        chrome_options = webdriver.ChromeOptions(); chrome_options.add_argument("--headless=new"); chrome_options.add_argument("--no-sandbox"); chrome_options.add_argument("--disable-dev-shm-usage"); chrome_options.add_argument("--disable-gpu"); chrome_options.add_argument("--disable-extensions"); chrome_options.add_argument("--disable-infobars"); chrome_options.add_argument("--disable-popup-blocking"); chrome_options.add_argument("--single-process"); chrome_options.add_argument("--blink-settings=imagesEnabled=false"); chrome_options.add_argument("--window-size=1280,1024")
        service = Service(executable_path="/usr/local/bin/chromedriver-linux64/chromedriver")
        driver_instance = webdriver.Chrome(service=service, options=chrome_options)
    return driver_instance

def quit_driver():
    global driver_instance
    if driver_instance: print("Closing browser."); driver_instance.quit(); driver_instance = None

# --- Memory & Helper Functions (Unchanged) ---
def load_sent_wallpapers():
    try:
        with open(WALLPAPER_MEMORY_FILE, 'r') as f: return set(json.load(f))
    except FileNotFoundError: print("Memory file not found."); return set()
def save_sent_wallpapers(sent_set):
    os.makedirs(VOLUME_PATH, exist_ok=True)
    with open(WALLPAPER_MEMORY_FILE, 'w') as f: json.dump(list(sent_set), f, indent=4)
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

# --- SIMPLIFIED, SYNCHRONOUS Scraping Functions ---
def get_latest_image_from_zerochan(driver, url: str):
    try:
        driver.get(url); wait = WebDriverWait(driver, 45)
        wait.until(EC.presence_of_element_located((By.ID, 'thumbs2')))
        gallery = driver.find_element(By.ID, 'thumbs2'); first_item = gallery.find_element(By.TAG_NAME, 'li')
        page_link = first_item.find_element(By.TAG_NAME, 'a').get_attribute('href'); driver.get(page_link)
        return wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a.preview"))).get_attribute('href')
    except Exception as e:
        print(f"Zerochan scraping failed for {url}. Error: {e}"); return None

def get_latest_image_from_yandere(driver, url: str):
    try:
        driver.get(url); wait = WebDriverWait(driver, 45)
        wait.until(EC.presence_of_element_located((By.ID, 'post-list-posts')))
        post_list = driver.find_element(By.ID, 'post-list-posts'); first_post = post_list.find_element(By.TAG_NAME, 'li')
        post_page_link = first_post.find_element(By.CLASS_NAME, 'thumb').get_attribute('href'); driver.get(post_page_link)
        return wait.until(EC.visibility_of_element_located((By.ID, 'highres'))).get_attribute('href')
    except Exception as e:
        print(f"Yande.re scraping failed for {url}. Error: {e}"); return None

# --- Command Handlers ---
async def start(update, context):
    await update.message.reply_text('Hello! I monitor latest images automatically.\n\nUse `/wallpaper zerochan` or `/wallpaper yandere` to get 10 new wallpapers.')

# --- MODIFIED: Wallpaper Command to use centralized lock ---
async def get_wallpaper(update, context):
    source = "zerochan"
    if context.args and context.args[0].lower() in ['yandere', 'yande.re']: source = 'yandere'
    await update.message.reply_text(f'Browsing {source} for up to 10 new wallpapers, this may take a while...')
    
    async with scraper_lock: # Acquire lock for the entire operation
        try:
            driver = get_driver(); wait = WebDriverWait(driver, 45)
            # ... (rest of the logic is identical, but now it has exclusive browser access)
            collected_images, newly_sent_ids, current_page, max_pages_to_check = [], [], 1, 10
            while len(collected_images) < 10 and current_page <= max_pages_to_check:
                page_candidates=[];print(f"--- Searching page {current_page} of {source} ---")
                if source=='zerochan':driver.get(f"{ZEROCHAN_WALLPAPER_URL}?p={current_page}");wait.until(EC.presence_of_element_located((By.ID,'thumbs2')));gallery=driver.find_element(By.ID,'thumbs2');list_items=gallery.find_elements(By.TAG_NAME,'li')
                else:driver.get(f"{YANDERE_WALLPAPER_URL}&page={current_page}");wait.until(EC.presence_of_element_located((By.ID,'post-list-posts')));gallery=driver.find_element(By.ID,'post-list-posts');list_items=gallery.find_elements(By.TAG_NAME,'li')
                for item in list_items:
                    if source=='zerochan':page_url=item.find_element(By.TAG_NAME,'a').get_attribute('href');image_id="z_"+page_url.split('/')[-1]
                    else:page_url=item.find_element(By.CLASS_NAME,'thumb').get_attribute('href');image_id="y_"+page_url.split('/')[-1]
                    page_candidates.append({'id':image_id,'url':page_url})
                if not page_candidates:print("No more images found.");break
                new_found_on_page=0;skipped_on_page=0
                for candidate in page_candidates:
                    if len(collected_images)>=10:break
                    image_id,page_url=candidate['id'],candidate['url']
                    if image_id in sent_wallpapers:skipped_on_page+=1;continue
                    try:
                        new_found_on_page+=1;driver.get(page_url);full_image_url=None
                        if source=='zerochan':full_image_url=wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,"a.preview"))).get_attribute('href')
                        else:full_image_url=wait.until(EC.visibility_of_element_located((By.ID,'highres'))).get_attribute('href')
                        image_bytes=download_image_to_memory(full_image_url)
                        if image_bytes and len(image_bytes)<TELEGRAM_PHOTO_LIMIT:collected_images.append(InputMediaPhoto(media=image_bytes));newly_sent_ids.append(image_id)
                        elif image_bytes:await send_file_with_retry(context,update.effective_chat.id,full_image_url,"This wallpaper was too large for an album.");sent_wallpapers.add(image_id)
                    except Exception as e:print(f"Could not process item {image_id}. Skipping. Error: {e}")
                print(f"Page {current_page} Summary: Found {new_found_on_page} new, Skipped {skipped_on_page} duplicates.")
                current_page+=1;time.sleep(2)
            if collected_images:
                send_success=False
                for attempt in range(MAX_RETRIES):
                    try:await context.bot.send_media_group(chat_id=update.effective_chat.id,media=collected_images);send_success=True;break
                    except TelegramError as e:print(f"Album send attempt {attempt + 1} failed: {e}");await asyncio.sleep(RETRY_DELAY)
                if send_success:await update.message.reply_text(f"Here are {len(collected_images)} new wallpapers from {source}!");sent_wallpapers.update(newly_sent_ids)
            if newly_sent_ids or len(collected_images) > 0:save_sent_wallpapers(sent_wallpapers)
            if len(collected_images) == 0:await update.message.reply_text("I browsed the first few pages but couldn't find any new wallpapers.")
        except Exception as e:
            print(f"Critical error in get_wallpaper: {e}");await update.message.reply_text("Sorry, a critical error occurred.");quit_driver()

# --- MODIFIED: Automatic Job to use centralized lock ---
async def send_scheduled_image(context: ContextTypes.DEFAULT_TYPE):
    print("\n--- Running Scheduled Job ---")
    async with scraper_lock: # Acquire lock for the entire job
        try:
            driver = get_driver() # Get the single browser instance
            for url in URLS_TO_SCRAPE:
                try:
                    print(f"\nChecking URL: {url}"); latest_image_url = None
                    if "zerochan.net" in url: latest_image_url = get_latest_image_from_zerochan(driver, url)
                    elif "yande.re" in url: latest_image_url = get_latest_image_from_yandere(driver, url)
                    else: print(f"Warning: No scraper for {url}."); continue
                    
                    if not latest_image_url: raise ValueError("Scraping returned no URL.")
                    last_seen_url = last_known_images.get(url)
                    if latest_image_url != last_seen_url and latest_image_url not in sent_urls:
                        print(f"NEW IMAGE FOUND on {url}!")
                        # We release the lock before sending, as this can be slow and doesn't use the browser
                        # This is an advanced optimization to let other commands run while we upload
                        asyncio.create_task(send_and_update_memory(context, latest_image_url, url))
                    else: print("No new image found.")
                    time.sleep(3)
                except Exception as e: print(f"Job failed for URL: {url}. Reason: {e}. MOVING TO NEXT URL."); continue
        except Exception as e:
            print(f"Critical error in scheduled job: {e}"); quit_driver()

async def send_and_update_memory(context, image_url, source_url):
    """A helper to send and update memory outside the main lock."""
    success = await send_file_with_retry(context, TELEGRAM_CHAT_ID, image_url, f"New image from: {source_url}")
    if success:
        last_known_images[source_url] = image_url
        sent_urls.append(image_url)

# --- Main function & Cleanup ---
def main():
    os.makedirs(VOLUME_PATH, exist_ok=True)
    if os.path.exists(LOCK_FILE): print("!!! Lock file found. Exiting. !!!"); return
    with open(LOCK_FILE, 'w') as f: f.write(str(os.getpid()))
    atexit.register(cleanup)
    global sent_wallpapers; sent_wallpapers = load_sent_wallpapers()
    print(f"Loaded {len(sent_wallpapers)} wallpaper IDs from memory.")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: print("CRITICAL ERROR: Missing environment variables."); return
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start)); application.add_handler(CommandHandler("wallpaper", get_wallpaper))
    job_queue = application.job_queue; job_queue.run_repeating(send_scheduled_image, interval=JOB_INTERVAL, first=5)
    print(f"Scheduled job running. Bot is running.")
    application.run_polling()
def cleanup():
    print("Shutdown signal received. Cleaning up...")
    quit_driver()
    if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)
    print("Cleanup complete.")
if __name__ == '__main__':
    main()
