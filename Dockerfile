FROM python:3.11-slim

WORKDIR /app

# Reflex installs bun by downloading and unzipping it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "reflex run --env prod --single-port --backend-host 0.0.0.0 --frontend-port $PORT"]
