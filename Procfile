# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for Chrome and other tools
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    # Add Google Chrome's official repository
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    # Install Chrome and ChromeDriver
    && apt-get update \
    && apt-get install -y \
    google-chrome-stable \
    # Clean up APT caches to keep the image small
    && rm -rf /var/lib/apt/lists/*

# Find the latest stable version of ChromeDriver
RUN LATEST_CHROMEDRIVER_VERSION=$(wget -q -O - "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" | python3 -c "import json, sys; print(json.load(sys.stdin)['channels']['Stable']['version'])") \
    && echo "Latest Stable ChromeDriver version is: $LATEST_CHROMEDRIVER_VERSION" \
    # Download and install the matching ChromeDriver
    && wget -q --continue -P /tmp "https://storage.googleapis.com/chrome-for-testing-public/$LATEST_CHROMEDRIVER_VERSION/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver-linux64.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver-linux64.zip

# Copy local code to the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Tell Docker what command to run when the container starts
# The Procfile will override this, but it's good practice.
CMD ["python", "zerochan_bot.py"]
