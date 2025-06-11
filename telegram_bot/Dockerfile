FROM python:3.11-slim

WORKDIR /app

COPY telegram_bot/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY database/ ./database/
COPY services/ ./services/
COPY telegram_bot/ ./telegram_bot/
COPY utils/ ./utils/

ENV PYTHONPATH=/app

CMD ["python", "telegram_bot/bot.py"]
