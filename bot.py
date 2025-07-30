import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime, timedelta
import asyncio
from fastapi import FastAPI, Request
from telegram.ext import ApplicationBuilder

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store reminders and notes (in-memory for simplicity)
reminders = {}
notes = {}

# FastAPI app for webhook
app = FastAPI()

# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hello! I'm your personal assistant bot. Use /help to see what I can do!"
    )

# Command: /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "I'm your personal assistant! Available commands:\n"
        "/start - Greet and start the bot\n"
        "/help - Show this help message\n"
        "/setreminder <minutes> <message> - Set a reminder (e.g., /setreminder 10 Call mom)\n"
        "/listreminders - List all your reminders\n"
        "/addnote <note> - Add a new note\n"
        "/listnotes - List all your notes\n"
        "/deletenote <index> - Delete a note by index\n"
        "/ask <question> - Ask the AI a question\n"
        "Send any message, and I'll echo it back!"
    )
    await update.message.reply_text(help_text)

# Command: /setreminder
async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /setreminder <minutes> <message>")
        return

    try:
        minutes = int(args[0])
        reminder_message = " ".join(args[1:])
        remind_time = datetime.now() + timedelta(minutes=minutes)

        if user_id not in reminders:
            reminders[user_id] = []
        reminders[user_id].append((remind_time, reminder_message))

        await update.message.reply_text(
            f"Reminder set for {minutes} minute(s) from now: {reminder_message}"
        )

        # Schedule reminder
        await schedule_reminder(context, user_id, reminder_message, minutes)
    except ValueError:
        await update.message.reply_text("Please provide a valid number of minutes.")

# Command: /listreminders
async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in reminders or not reminders[user_id]:
        await update.message.reply_text("You have no reminders set.")
        return

    response = "Your reminders:\n"
    for i, (time, msg) in enumerate(reminders[user_id], 1):
        response += f"{i}. {msg} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    await update.message.reply_text(response)

# Command: /addnote
async def add_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /addnote <note content>")
        return

    note_content = " ".join(args)
    if user_id not in notes:
        notes[user_id] = []
    notes[user_id].append(note_content)
    await update.message.reply_text(f"Note added: {note_content}")

# Command: /listnotes
async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in notes or not notes[user_id]:
        await update.message.reply_text("You have no notes.")
        return

    response = "Your notes:\n"
    for i, note in enumerate(notes[user_id], 1):
        response += f"{i}. {note}\n"
    await update.message.reply_text(response)

# Command: /deletenote
async def delete_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /deletenote <index>")
        return

    try:
        index = int(args[0]) - 1
        if user_id not in notes or index < 0 or index >= len(notes[user_id]):
            await update.message.reply_text("Invalid note index.")
            return

        deleted_note = notes[user_id].pop(index)
        await update.message.reply_text(f"Deleted note: {deleted_note}")
    except ValueError:
        await update.message.reply_text("Please provide a valid note index.")

# Command: /ask (AI feature)
async def ask_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /ask <question>")
        return

    question = " ".join(args)
    # Simulate AI response (mocked for simplicity, as no external AI API is integrated)
    responses = [
        f"Interesting question about '{question}'! Here's a quick thought: it depends on the context, but generally, I'd suggest exploring more details.",
        f"Hmm, regarding '{question}', I'd say it's a complex topic, but a good starting point is to break it down into smaller parts.",
        f"For '{question}', my knowledge suggests looking into related resources or asking for specifics to give a clearer answer."
    ]
    ai_response = random.choice(responses)
    await update.message.reply_text(ai_response)

# Schedule reminder job
async def schedule_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str, minutes: int) -> None:
    await asyncio.sleep(minutes * 60)
    await context.bot.send_message(chat_id=user_id, text=f"Reminder: {message}")
    # Clean up expired reminders
    if user_id in reminders:
        reminders[user_id] = [(t, m) for t, m in reminders[user_id] if t > datetime.now()]

# Handle non-command messages
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"You said: {update.message.text}")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
    await update.message.reply_text("An error occurred. Please try again.")

# Webhook endpoint
@app.post("/webhook")
async def webhook(request: Request) -> None:
    update = Update.de_json(await request.json(), bot)
    await application.process_update(update)

# Initialize bot and application
bot = None
application = None

def main() -> None:
    global bot, application
    # Get environment variables
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

    # Initialize application
    application = ApplicationBuilder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("setreminder", set_reminder))
    application.add_handler(CommandHandler("listreminders", list_reminders))
    application.add_handler(CommandHandler("addnote", add_note))
    application.add_handler(CommandHandler("listnotes", list_notes))
    application.add_handler(CommandHandler("deletenote", delete_note))
    application.add_handler(CommandHandler("ask", ask_ai))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error_handler)

if __name__ == "__main__":
    import uvicorn
    main()
    # Get port from environment variable or default to 8000
    port = int(os.getenv("PORT", 8000))
    # Run FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=port)
