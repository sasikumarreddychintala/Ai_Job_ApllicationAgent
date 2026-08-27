# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install essential system utilities and libraries for Playwright & PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    wget \
    ca-certificates \
    fonts-liberation \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium & system browser dependencies for headless automation
RUN playwright install --with-deps chromium

# Copy project files
COPY . .

# Create required persistent data directories
RUN mkdir -p data/logs data/tailored_resumes data/master_resume

# Expose Web Dashboard Port
EXPOSE 8000

# Default command to run the full application (Web UI + Multi-Agent Engine + Telegram Bot)
CMD ["sh", "-c", "python agent.py --ui --port ${PORT:-8000}"]
