FROM python:3.11-slim

WORKDIR /app

# Debian's chromium is built with proprietary codecs (H.264/AAC). Playwright's
# bundled build has them on x86_64 but NOT on arm64, where jwplayer then finds
# no provider for the HLS stream and aborts before requesting the playlist.
# Using the distro package keeps every architecture on the same browser.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && apt-get install -y chromium \
    && rm -rf /var/lib/apt/lists/*

ENV CHROMIUM_PATH=/usr/bin/chromium

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000

CMD ["uvicorn","backend.main:app","--host", "0.0.0.0","--port", "8000", "--reload"]
