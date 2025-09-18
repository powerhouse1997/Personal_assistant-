# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (no Chrome needed!)
RUN apt-get update && apt-get install -y \
    # We might need Node.js for cloudscraper's JavaScript challenges
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy local code to the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# The Procfile will be used by Railway to run the bot
CMD ["python", "zerochan_bot.py"]
