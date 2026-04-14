FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY project/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY .env /app/.env
COPY project/support_bot.py /app/support_bot.py
COPY project/models.py /app/models.py
COPY project/ticket_state.py /app/ticket_state.py
COPY project/issues.json /app/issues.json
COPY project/config /app/config
COPY project/repo /app/repo
COPY project/service /app/service
COPY project/kb /app/kb
COPY project/data /app/data
COPY project/tests /app/tests

CMD ["python", "support_bot.py"]
