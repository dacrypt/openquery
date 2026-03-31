FROM python:3.12-slim

# System dependencies for tesseract OCR and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system ".[serve]"

# Install Playwright browsers
RUN playwright install --with-deps chromium

EXPOSE 8000

CMD ["openquery", "serve", "--host", "0.0.0.0", "--port", "8000"]
