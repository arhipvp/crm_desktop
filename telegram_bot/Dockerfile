FROM python:3.11-slim

WORKDIR /app

# Install system libraries required by PySide6 and other packages
RUN apt-get update \
    && apt-get install -y libegl1 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from the main project and bot specific files
COPY requirements.txt ./
COPY telegram_bot/requirements.txt ./telegram_requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r telegram_requirements.txt

# Copy application source
COPY database/ ./database/
COPY services/ ./services/
COPY telegram_bot/ ./telegram_bot/
COPY utils/ ./utils/

ENV PYTHONPATH=/app

CMD ["python", "telegram_bot/bot.py"]
