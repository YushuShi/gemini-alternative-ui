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

RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
