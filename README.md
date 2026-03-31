# OpenQuery

[![CI](https://github.com/dacrypt/openquery/actions/workflows/ci.yml/badge.svg)](https://github.com/dacrypt/openquery/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/openquery)](https://pypi.org/project/openquery/)
[![Python](https://img.shields.io/pypi/pyversions/openquery)](https://pypi.org/project/openquery/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Query public data sources worldwide through a unified CLI and REST API.

OpenQuery provides a plugin-based framework for scraping government websites, public registries, and open data APIs. It handles the hard parts — browser automation, CAPTCHA solving, WAF bypass, caching, and rate limiting — so you can focus on the data.

## Features

- **Unified interface** — one CLI and one API endpoint for all data sources
- **Browser automation** — Playwright-based scraping for JavaScript-heavy sites
- **CAPTCHA solving** — local OCR (pytesseract) with optional paid service fallback
- **WAF bypass** — browser-context API calls preserve session cookies
- **Caching** — in-memory, Redis, or SQLite backends with configurable TTL
- **Rate limiting** — per-source token-bucket to respect server limits
- **REST API** — FastAPI server with auto-generated OpenAPI docs
- **Extensible** — add new data sources by implementing a single class
- **Country-organized** — sources grouped by country code (`co`, `us`, etc.)

## Built-in Sources

| Source | Country | Description | Inputs | CAPTCHA |
|--------|---------|-------------|--------|---------|
| `co.simit` | CO | Traffic fines and violations | cedula, placa | No |
| `co.runt` | CO | National vehicle registry (SOAT, RTM, ownership) | vin, placa | Yes (OCR) |

## Installation

```bash
pip install openquery
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add openquery
```

### System Dependencies

OpenQuery requires [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for CAPTCHA solving and Playwright browsers for web scraping:

```bash
# macOS
brew install tesseract
playwright install chromium

# Ubuntu/Debian
sudo apt-get install tesseract-ocr
playwright install --with-deps chromium
```

### Optional Extras

```bash
pip install "openquery[serve]"    # FastAPI server (fastapi, uvicorn)
pip install "openquery[redis]"    # Redis cache backend
pip install "openquery[captcha]"  # 2captcha paid CAPTCHA solving
```

## Quick Start

### CLI

```bash
# List available data sources
openquery sources

# Query Colombian traffic fines by cedula
openquery query co.simit --cedula 12345678

# Query Colombian vehicle registry by plate
openquery query co.runt --placa ABC123

# Query by VIN
openquery query co.runt --vin 5YJ3E1EA1PF000001

# Output raw JSON
openquery query co.simit --cedula 12345678 --json
```

### REST API

```bash
# Start the API server
openquery serve

# Or with custom host/port
openquery serve --host 127.0.0.1 --port 3000
```

Then query via HTTP:

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "source": "co.simit",
    "document_type": "cedula",
    "document_number": "12345678"
  }'
```

**Response:**

```json
{
  "ok": true,
  "source": "co.simit",
  "queried_at": "2026-03-31T10:30:00Z",
  "cached": false,
  "latency_ms": 4523,
  "data": {
    "comparendos": 0,
    "multas": 0,
    "total_deuda": 0.0,
    "paz_y_salvo": true
  }
}
```

**API Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/query` | Query a data source |
| `GET` | `/api/v1/sources` | List available sources |
| `GET` | `/api/v1/health` | Health check and cache stats |
| `GET` | `/docs` | Interactive API documentation |

### Docker

```bash
docker compose up
```

This starts the API server with Redis caching on port 8000.

## Configuration

All settings use environment variables with the `OPENQUERY_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENQUERY_API_KEY` | _(none)_ | API key for server authentication |
| `OPENQUERY_CACHE_BACKEND` | `memory` | Cache backend: `memory`, `redis`, `sqlite` |
| `OPENQUERY_CACHE_TTL_DEFAULT` | `3600` | Default cache TTL in seconds |
| `OPENQUERY_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `OPENQUERY_BROWSER_HEADLESS` | `true` | Run browser in headless mode |
| `OPENQUERY_BROWSER_TIMEOUT` | `30.0` | Browser operation timeout in seconds |
| `OPENQUERY_RATE_LIMIT_DEFAULT_RPM` | `10` | Default requests per minute per source |
| `OPENQUERY_CAPTCHA_SOLVER` | `ocr` | CAPTCHA solver: `ocr`, `2captcha`, `chained` |
| `OPENQUERY_TWO_CAPTCHA_API_KEY` | _(none)_ | 2captcha.com API key |
| `OPENQUERY_LOG_LEVEL` | `INFO` | Logging level |

## Adding a New Source

Create a new source by implementing the `BaseSource` class:

```python
# src/openquery/sources/us/nhtsa.py
from pydantic import BaseModel
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta


class NhtsaResult(BaseModel):
    manufacturer: str = ""
    model: str = ""
    year: int = 0
    recalls: list[dict] = []


@register
class NhtsaSource(BaseSource):
    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nhtsa",
            display_name="NHTSA Vehicle Safety",
            description="US vehicle safety recalls and VIN decoding",
            country="US",
            url="https://vpic.nhtsa.dot.gov/api/",
            supported_inputs=[DocumentType.VIN],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=30,
        )

    def query(self, input: QueryInput) -> NhtsaResult:
        import httpx
        resp = httpx.get(
            f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevin/{input.document_number}",
            params={"format": "json"},
        )
        data = resp.json()
        # Parse and return NhtsaResult...
```

The `@register` decorator automatically makes the source available in the CLI, API, and source listing.

## Architecture

```
openquery/
├── core/           # Infrastructure (browser, captcha, cache, rate limiting)
├── sources/        # Data source plugins, organized by country
│   ├── base.py     # BaseSource ABC — implement this to add sources
│   ├── co/         # Colombia (SIMIT, RUNT)
│   └── us/         # United States (future)
├── models/         # Pydantic response models, organized by country
├── server/         # FastAPI REST API
└── commands/       # Typer CLI commands
```

## Development

```bash
git clone https://github.com/dacrypt/openquery.git
cd openquery
uv sync --all-extras
playwright install chromium

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

[MIT](LICENSE)
