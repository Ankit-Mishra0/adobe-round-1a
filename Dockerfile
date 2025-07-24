
FROM --platform=linux/amd64 python:3.9-slim-bookworm


WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libharfbuzz-dev \
    libfreetype6-dev \
    libfontconfig1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x scraper_pdf.sh
CMD ["/bin/bash", "scraper_pdf.sh"]