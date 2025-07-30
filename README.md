# Personal Assistant Telegram Bot
+
+A comprehensive personal assistant Telegram bot with multiple features to help you stay organized, productive, and informed.
+
+## 🌟 Features
+
+### 📝 Notes & Organization
+- Create and manage personal notes
+- Tag notes for easy organization
+- Search and filter notes by tags
+- Rich text formatting support
+
+### ✅ Task Management
+- Add tasks with priorities (low, medium, high)
+- Categorize tasks (work, personal, health, etc.)
+- Track task completion
+- Due date management
+
+### 🎯 Habit Tracking
+- Create daily, weekly, or monthly habits
+- Track habit streaks
+- Mark habits as completed
+- View habit statistics
+
+### 💰 Expense Tracking
+- Log expenses with categories
+- Track spending over time
+- Generate expense summaries
+- Budget monitoring
+
+### ⏰ Reminders & Timers
+- Set custom reminders with specific times
+- Quick timer functionality
+- Recurring reminders
+- Notification system
+
+### 🌤️ Information & Utilities
+- **Weather Information**: Get current weather for any city
+- **News Updates**: Latest news from various categories
+- **Time & Date**: Current time in different timezones
+- **Calculator**: Basic mathematical calculations
+- **Quotes**: Motivational quotes
+- **Jokes**: Random jokes for entertainment
+
+### 📊 Analytics & Statistics
+- Personal usage statistics
+- Habit tracking analytics
+- Expense summaries
+- Progress tracking
+
+## 🚀 Quick Start
+
+### Prerequisites
+- Python 3.8 or higher
+- Telegram Bot Token (from @BotFather)
+- Optional: Weather API key (OpenWeatherMap)
+- Optional: News API key (NewsAPI)
+
+### Installation
+
+1. **Clone or download the bot files**
+   ```bash
+   # Make sure you have the following files:
+   # - personal_assistant_bot.py (basic version)
+   # - enhanced_assistant_bot.py (advanced version)
+   # - requirements_assistant.txt
+   # - assistant_config.env
+   ```
+
+2. **Install dependencies**
+   ```bash
+   pip install -r requirements_assistant.txt
+   ```
+
+3. **Configure the bot**
+   ```bash
+   # Edit assistant_config.env with your API keys
+   BOT_TOKEN=your_telegram_bot_token
+   WEATHER_API_KEY=your_openweathermap_api_key
+   NEWS_API_KEY=your_newsapi_key
+   ```
+
+4. **Run the bot**
+   ```bash
+   # For basic version
+   python personal_assistant_bot.py
+   
+   # For enhanced version (recommended)
+   python enhanced_assistant_bot.py
+   ```

## Telegram AI Assistant Bot

### Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up your environment variables:
   - `TELEGRAM_TOKEN`: Your Telegram bot token from BotFather
   - `OPENAI_API_KEY`: Your OpenAI API key

   You can export them in your shell:
   ```bash
   export TELEGRAM_TOKEN=your_telegram_token
   export OPENAI_API_KEY=your_openai_api_key
   ```

3. Run the bot:
   ```bash
   python bot.py
   ```

### Features
- Replies to any message with an AI-generated response using OpenAI GPT-3.5/4.

### Extending
You can add more features by editing `bot.py` and adding new command or message handlers.

## 📋 Commands Reference

### Basic Commands
+- `/start` - Start the bot and see welcome message
+- `/help` - Show all available commands
+- `/settings` - Configure your preferences

### Notes Management
+- `/note add <title> <content> [tags]` - Add a new note
+- `/note list [tags]` - List all your notes
+- `/note get <id>` - Get a specific note
+- `/note delete <id>` - Delete a note

### Task Management
+- `/task add <title> <description> <priority> [category]` - Add a new task
+- `/task list [category]` - List all tasks
+- `/task complete <id>` - Mark task as complete
+- `/task delete <id>` - Delete a task

### Habit Tracking
+- `/habit add <title> <description> [frequency]` - Add a new habit
+- `/habit list` - List all habits
+- `/habit complete <id>` - Mark habit as complete
+- `/habit stats` - View habit statistics

### Expense Tracking
+- `/expense add <amount> <description> <category>` - Add expense
+- `/expense list [days]` - List expenses
+- `/expense summary [days]` - Get expense summary

### Reminders & Timers
+- `/reminder add <title> <time>` - Set a reminder
+- `/reminder list` - List all reminders
+- `/timer <minutes>` - Set a timer
+- `/reminder delete <id>` - Delete a reminder

### Information & Utilities
+- `/weather [city]` - Get weather information
+- `/news [category]` - Get latest news
+- `/time [timezone]` - Get current time
+- `/calc <expression>` - Calculator
+- `/quote` - Get a motivational quote
+- `/joke` - Get a random joke

### Analytics
+- `/stats` - View your statistics
+- `/progress` - Track your progress

## 🔧 Configuration

### Environment Variables

Edit `assistant_config.env`:

```env
# Required
BOT_TOKEN=your_telegram_bot_token

# Optional APIs
WEATHER_API_KEY=your_openweathermap_api_key
NEWS_API_KEY=your_newsapi_key
OPENAI_API_KEY=your_openai_api_key

# Database
DB_PATH=personal_assistant.db

# Bot Settings
DEFAULT_TIMEZONE=UTC
DEFAULT_LANGUAGE=en

# Feature Flags
ENABLE_WEATHER=true
ENABLE_QUOTES=true
ENABLE_CALCULATOR=true
ENABLE_NOTES=true
ENABLE_TASKS=true
ENABLE_REMINDERS=true
ENABLE_TIMERS=true
```

### Getting API Keys

1. **Telegram Bot Token**
   - Message @BotFather on Telegram
   - Use `/newbot` command
   - Follow instructions to create your bot
   - Copy the token provided

2. **Weather API Key (Optional)**
   - Sign up at [OpenWeatherMap](https://openweathermap.org/api)
   - Get your free API key
   - Add to `WEATHER_API_KEY` in config

3. **News API Key (Optional)**
   - Sign up at [NewsAPI](https://newsapi.org/)
   - Get your free API key
   - Add to `NEWS_API_KEY` in config

## 📊 Database Structure

The bot uses SQLite database with the following tables:

+- **users**: User preferences and settings
+- **notes**: Personal notes with tags
+- **tasks**: Task management with priorities
+- **habits**: Habit tracking with streaks
+- **expenses**: Expense tracking with categories
+- **reminders**: Scheduled reminders

## 🎯 Usage Examples

### Setting up your preferences
```
+/settings timezone America/New_York
+/settings location New York
+/settings language en
```

### Creating a note
```
+/note add Meeting Notes Discussed project timeline with team
```

### Adding a task
```
+/task add Review code high work
```

### Setting a habit
```
+/habit add Exercise Daily workout routine daily
```

### Tracking an expense
```
+/expense add 25.50 Lunch food
```

### Setting a reminder
```
+/reminder add Team meeting 2024-01-15 14:30
```

### Getting weather
```
+/weather London
```

## 🔒 Security & Privacy

+- All data is stored locally in SQLite database
+- No data is shared with third parties
+- User preferences are stored per user ID
+- API keys are kept secure in environment variables

## 🛠️ Troubleshooting

### Common Issues

1. **Bot not responding**
   - Check if BOT_TOKEN is correct
   - Ensure bot is running without errors
   - Check logs for error messages

2. **Weather not working**
   - Verify WEATHER_API_KEY is set correctly
   - Check if city name is valid
   - Ensure internet connection

3. **Database errors**
   - Check file permissions for database
   - Ensure sufficient disk space
   - Restart bot to recreate database if needed

### Logs

The bot creates detailed logs in the console. Check for:
+- Connection errors
+- API rate limiting
+- Database errors
+- Invalid command usage

## 🤝 Contributing

Feel free to contribute to this project by:
+- Reporting bugs
+- Suggesting new features
+- Improving documentation
+- Adding new commands

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

+- Telegram Bot API
+- OpenWeatherMap for weather data
+- NewsAPI for news updates
+- Quotable API for quotes
+- Official Joke API for jokes

## 📞 Support

If you need help or have questions:
1. Check the `/help` command in the bot
2. Review this README
3. Check the logs for error messages
4. Ensure all dependencies are installed

---

**Happy organizing and staying productive! 🚀**
