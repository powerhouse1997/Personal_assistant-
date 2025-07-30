import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import openai

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN')
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', 'YOUR_PERPLEXITY_API_KEY')

# Configure OpenAI client to use Perplexity API
openai.api_key = PERPLEXITY_API_KEY
openai.api_base = "https://api.perplexity.ai"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! I am your AI assistant powered by Perplexity. Ask me anything!')

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        # Use Perplexity's chat completion
        response = openai.chat.completions.create(
            model="llama-3.1-sonar-small-128k-online",
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1000
        )
        ai_message = response.choices[0].message.content.strip()
    except Exception as e:
        ai_message = f"Sorry, I couldn't process your request. Error: {e}"
    await update.message.reply_text(ai_message)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))
    app.run_polling()