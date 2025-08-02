
import os
import telebot
import google.generativeai as genai
from features.web_search import search as web_search_func

# It's best practice to get the token from an environment variable
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("Please set the BOT_TOKEN environment variable.")

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set the GEMINI_API_KEY environment variable.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'hello'])
def send_welcome(message):
    bot.reply_to(message, "Howdy, how are you doing?")

@bot.message_handler(commands=['ask'])
def ask_gemini(message):
    prompt = message.text.split('/ask', 1)[1].strip()
    if not prompt:
        bot.reply_to(message, "Please provide a prompt after the /ask command.")
        return
    try:
        response = model.generate_content(prompt)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"An error occurred: {e}")

@bot.message_handler(commands=['search'])
def search_tavily(message):
    query = message.text.split('/search', 1)[1].strip()
    if not query:
        bot.reply_to(message, "Please provide a search query after the /search command.")
        return
    try:
        results = web_search_func(query)
        if isinstance(results, str): # Error case
            bot.reply_to(message, results)
            return

        response_text = ""
        for result in results[:5]: # Show top 5 results
            response_text += f"Title: {result['title']}\n"
            response_text += f"URL: {result['url']}\n"
            response_text += f"Snippet: {result['content']}\n\n"

        if not response_text:
            response_text = "No results found."

        if len(response_text) > 4096:
            response_text = response_text[:4090] + "..."

        bot.reply_to(message, response_text)

    except Exception as e:
        bot.reply_to(message, f"An error occurred during the search: {e}")

@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    bot.reply_to(message, message.text)

print("Bot is running...")
bot.infinity_polling()
