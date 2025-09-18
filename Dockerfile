# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*

# Add Google Chrome's official repository
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Install Google Chrome and clear cache
RUN apt-get update \
    && apt-get install -y google-chrome-stable \
    # --- ADD THIS LINE ---
    && rm -rf /root/.cache/google-chrome \
    # -------------------
    && rm -rf /var/lib/apt/lists/*

# Find, install, and make executable the matching version of ChromeDriver
RUN LATEST_CHROMEDRIVER_VERSION=$(wget -q -O - "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" | python3 -c "import json, sys; print(json.load(sys.stdin)['channels']['Stable']['version'])") \
    && echo "Downloading ChromeDriver version: $LATEST_CHROMEDRIVER_VERSION" \
    && wget -q --continue -P /tmp "https://storage.googleapis.com/chrome-for-testing-public/$LATEST_CHROMEDRIVER_VERSION/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver-linux64.zip \
    && chmod +x /usr/local/bin/chromedriver-linux64/chromedriver

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# The Procfile will be used by Railway to run the bot
CMD ["python", "zerochan_bot.py"]
