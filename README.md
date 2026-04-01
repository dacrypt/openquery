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
- **Multi-engine CAPTCHA solving** — PaddleOCR (100%), EasyOCR+Tesseract voting (90%), with cloud and paid fallbacks
- **LLM-powered knowledge CAPTCHAs** — Ollama (local), HuggingFace, Anthropic, OpenAI fallback chain
- **Audit & evidence** — screenshots, network logs, and PDF evidence reports for compliance
- **WAF bypass** — browser-context API calls preserve session cookies
- **Caching** — in-memory, Redis, or SQLite backends with configurable TTL
- **Rate limiting** — per-source token-bucket to respect server limits
- **REST API** — FastAPI server with auto-generated OpenAPI docs
- **Extensible** — add new data sources by implementing a single class
- **Country-organized** — sources grouped by country code (`co`, `us`, etc.)

## Built-in Sources

| Source | Country | Description | Inputs | Browser |
|--------|---------|-------------|--------|---------|
| `co.simit` | CO | Traffic fines and violations | cedula, placa | Yes |
| `co.runt` | CO | Vehicle registry (SOAT, RTM, ownership) | vin, placa, cedula | Yes |
| `co.procuraduria` | CO | Disciplinary records | cedula | Yes |
| `co.policia` | CO | Criminal background | cedula | Yes |
| `co.adres` | CO | Health system enrollment (EPS) | cedula | Yes |
| `co.pico_y_placa` | CO | Driving restrictions (Bogota/Medellin/Cali) | placa | No |
| `co.peajes` | CO | Toll road tariffs (ANI) | custom | No |
| `co.combustible` | CO | Fuel prices by city/station | custom | No |
| `co.estaciones_ev` | CO | EV charging stations | custom | No |
| `co.siniestralidad` | CO | Road crash hotspots (ANSV) | custom | No |
| `co.vehiculos` | CO | National vehicle fleet data | placa, custom | No |
| `co.fasecolda` | CO | Vehicle reference prices (insurance) | custom | Yes |
| `co.recalls` | CO | Vehicle safety recalls (SIC) | custom | Yes |

## Installation

```bash
pip install openquery
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add openquery
```

### System Dependencies

Playwright browsers are required for web scraping:

```bash
playwright install chromium
```

### CAPTCHA Engines (pick one or more)

OpenQuery auto-detects installed OCR engines and builds an optimal solver chain:

| Engine | Accuracy | Speed | Install |
|--------|----------|-------|---------|
| **PaddleOCR** (recommended) | 100% | ~130ms | `pip install "openquery[paddleocr]"` |
| EasyOCR + Tesseract (voting) | 90% | ~500ms | `pip install "openquery[easyocr]"` + `brew install tesseract` |
| Tesseract alone | 80% | ~390ms | `brew install tesseract` (included by default) |

For knowledge-based CAPTCHAs (Procuraduria), you need at least one LLM backend:

| Backend | Cost | Setup |
|---------|------|-------|
| **Ollama** (recommended) | Free | `ollama pull llama3.2:1b` |
| HuggingFace Inference | Free | Set `HF_TOKEN` env var |
| Anthropic | Paid | Set `ANTHROPIC_API_KEY` env var |
| OpenAI | Paid | Set `OPENAI_API_KEY` env var |

### Optional Extras

```bash
pip install "openquery[paddleocr]"   # PaddleOCR — best CAPTCHA accuracy (100%)
pip install "openquery[easyocr]"     # EasyOCR — good accuracy (85%), combines with Tesseract for 90%
pip install "openquery[huggingface]" # HuggingFace Inference API (OCR + QA)
pip install "openquery[serve]"       # FastAPI server (fastapi, uvicorn)
pip install "openquery[redis]"       # Redis cache backend
pip install "openquery[captcha]"     # 2captcha paid CAPTCHA solving (last resort)
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

# Disciplinary records
openquery query co.procuraduria --cedula 12345678

# Criminal background
openquery query co.policia --cedula 12345678

# Health system enrollment
openquery query co.adres --cedula 12345678

# Pico y placa — is my plate restricted today?
openquery query co.pico_y_placa --placa ABC123

# Toll tariffs
openquery query co.peajes --custom peaje --extra '{"peaje": "ALVARADO"}'

# Fuel prices in Bogota
openquery query co.combustible --custom fuel --extra '{"municipio": "BOGOTA"}'

# EV charging stations in Medellin
openquery query co.estaciones_ev --custom ev --extra '{"ciudad": "Medellin"}'

# Road crash hotspots
openquery query co.siniestralidad --custom stats --extra '{"departamento": "CUNDINAMARCA"}'

# Vehicle fleet lookup by plate
openquery query co.vehiculos --placa ABC123

# Output raw JSON
openquery query co.simit --cedula 12345678 --json

# Generate audit evidence (screenshots + PDF report)
openquery query co.runt --placa ABC123 --audit --audit-dir ./evidence
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
| `OPENQUERY_LOG_LEVEL` | `INFO` | Logging level |
| `TWO_CAPTCHA_API_KEY` | _(none)_ | 2captcha.com API key (paid fallback) |
| `HF_TOKEN` | _(none)_ | HuggingFace token (free OCR + QA) |
| `ANTHROPIC_API_KEY` | _(none)_ | Anthropic API key (paid QA fallback) |
| `OPENAI_API_KEY` | _(none)_ | OpenAI API key (paid QA fallback) |

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
├── core/
│   ├── browser.py    # Playwright browser management
│   ├── captcha.py    # Multi-engine CAPTCHA solvers (PaddleOCR, EasyOCR, Tesseract, voting)
│   ├── llm.py        # LLM QA chain (Ollama, HuggingFace, Anthropic, OpenAI)
│   ├── audit.py      # Evidence capture (screenshots, network logs, PDF reports)
│   ├── cache.py      # Caching backends (memory, Redis, SQLite)
│   └── rate_limit.py # Token-bucket rate limiting
├── sources/          # Data source plugins, organized by country
│   ├── base.py       # BaseSource ABC — implement this to add sources
│   ├── co/           # Colombia (SIMIT, RUNT, Procuraduria, Policia, ADRES)
│   └── us/           # United States (future)
├── models/           # Pydantic response models, organized by country
├── server/           # FastAPI REST API
└── commands/         # Typer CLI commands
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

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Installation, first query, engine setup |
| [Sources Guide](docs/sources.md) | All 13 Colombian sources with field reference |
| [CAPTCHA Guide](docs/captcha.md) | OCR engines, voting, LLM backends, benchmarks |
| [Audit Guide](docs/audit.md) | Evidence capture, PDF reports, compliance |
| [API Guide](docs/api.md) | REST endpoints, authentication, deployment |
| [Adding Sources](docs/adding-sources.md) | Step-by-step guide to create new source plugins |
| [Changelog](CHANGELOG.md) | Version history |

## License

[MIT](LICENSE)
