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
- **Document OCR** — extract structured data from ID documents (cedula, INE, DNI, carnet, passport)
- **Face verification** — 1:1 face comparison with liveness detection (DeepFace/ArcFace)
- **Health monitoring** — per-source circuit breaker with automatic failover
- **Dashboard** — web UI for source browsing, querying, and health monitoring
- **Extensible** — add new data sources by implementing a single class
- **Country-organized** — sources grouped by country code (`co`, `us`, etc.)

## Built-in Sources — 98 sources across 14 countries

### Colombia (73 sources)

#### Antecedentes y Justicia
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.policia` | Criminal background (Policía Nacional) | cedula | Yes |
| `co.procuraduria` | Disciplinary records (Procuraduría) | cedula | Yes |
| `co.contraloria` | Fiscal responsibility (Contraloría) | cedula, nit, pasaporte | Yes |
| `co.rnmc` | Police corrective measures (RNMC) | cedula, pasaporte | Yes |
| `co.consulta_procesos` | Judicial processes (Rama Judicial) | cedula, nit | Yes |
| `co.tutelas` | Constitutional protection actions (Tutelas) | cedula, nit | Yes |
| `co.jep` | Transitional justice (JEP) | cedula | Yes |
| `co.inpec` | Prison population (INPEC) | cedula | Yes |

#### Identidad y Registro Civil
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.estado_cedula` | Cédula status (Registraduría) | cedula | Yes |
| `co.estado_tramite_cedula` | ID card processing status | cedula | Yes |
| `co.defuncion` | Cédula vigency — alive/deceased | cedula | Yes |
| `co.puesto_votacion` | Voting station lookup | cedula | Yes |
| `co.registro_civil` | Civil registry certificate | cedula | Yes |
| `co.nombre_completo` | Full name lookup by document | cedula | Yes |
| `co.libreta_militar` | Military service status | cedula | Yes |
| `co.migracion_ppt` | PPT temporary protection permit | custom | Yes |
| `co.estado_cedula_extranjeria` | Foreign ID card status (Migración) | custom | Yes |
| `co.validar_policia` | Police officer validation | custom | Yes |

#### Compliance y AML
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.pep` | Politically Exposed Persons (SIGEP) | cedula | No |
| `co.proveedores_ficticios` | DIAN fictitious providers | nit | No |
| `co.rne` | Do Not Call registry (RNE/CRC) | custom | No |

#### Seguridad Social
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.adres` | Health system enrollment (EPS/BDUA) | cedula | Yes |
| `co.colpensiones` | Pension affiliation (Colpensiones) | cedula | Yes |
| `co.fopep` | Pensioners payroll (FOPEP) | cedula | Yes |
| `co.ruaf` | Unified affiliates registry (SISPRO) | cedula | Yes |
| `co.rethus` | Health workforce registry (RETHUS) | cedula | Yes |
| `co.soi` | Social security payments (SOI/PILA) | cedula, nit | Yes |
| `co.seguridad_social` | Integrated social security status | cedula, nit | Yes |
| `co.afiliados_compensado` | Compensation fund affiliation | cedula | Yes |
| `co.sisben` | Socioeconomic classification (SISBEN) | cedula | Yes |

#### Empresas y Comercio
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.dian_rut` | Tax registry status (DIAN RUT) | cedula, nit | Yes |
| `co.rues` | Business registry (RUES/Confecámaras) | cedula, nit | Yes |
| `co.secop` | Public procurement (SECOP) | nit | No |
| `co.cufe_dian` | Electronic invoice verification (CUFE) | custom | Yes |
| `co.einforma` | Business intelligence (eInforma) | nit | Yes |
| `co.camara_comercio_medellin` | Medellín Chamber of Commerce | nit, custom | Yes |
| `co.directorio_empresas` | Business directory (datos.gov.co) | nit, custom | No |
| `co.empresas_google` | Business search (Google Maps) | custom | Yes |
| `co.supersociedades` | Insolvency proceedings (Ley 1116) | nit, cedula, custom | Yes |

#### Propiedad e Inmuebles
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.snr` | Property owner index (SNR) | cedula, nit | Yes |
| `co.certificado_tradicion` | Property title certificate (SNR) | custom | Yes |
| `co.garantias_mobiliarias` | Movable collateral registry | cedula | Yes |
| `co.cambio_estrato` | Socioeconomic stratum certification | cedula | Yes |

#### Vehículos y Tránsito
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.simit` | Traffic fines and violations (SIMIT) | cedula, placa | Yes |
| `co.runt` | Vehicle registry (RUNT) | vin, placa, cedula | Yes |
| `co.runt_conductor` | Driver information (RUNT) | cedula | Yes |
| `co.runt_soat` | Mandatory insurance status (SOAT) | placa | Yes |
| `co.runt_rtm` | Technical inspection status (RTM) | placa | Yes |
| `co.comparendos_transito` | Detailed traffic violations | cedula, placa | Yes |
| `co.fasecolda` | Vehicle reference prices (insurance) | custom | Yes |
| `co.recalls` | Vehicle safety recalls (SIC) | custom | Yes |
| `co.retencion_vehiculos` | Impounded vehicles | placa | Yes |
| `co.pico_y_placa` | Driving restrictions (13 cities) | placa | No |
| `co.peajes` | Toll road tariffs | custom | No |
| `co.combustible` | Fuel prices by city/station | custom | No |
| `co.estaciones_ev` | EV charging stations | custom | No |
| `co.siniestralidad` | Road crash hotspots (ANSV) | custom | No |
| `co.vehiculos` | National vehicle fleet data | placa, custom | No |

#### Vivienda y Servicios
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.mi_casa_ya` | Housing subsidies (Mi Casa Ya) | cedula | Yes |
| `co.tarifas_energia` | Electricity tariffs (SUI) | custom | No |

#### Turismo
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.rnt_turismo` | National tourism registry (RNT) | nit | No |

#### Salud
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.licencias_salud` | Health service providers (REPS) | nit | No |

#### Consejos Profesionales (11 sources)
| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `co.copnia` | Engineering (COPNIA) | cedula, nit | Yes |
| `co.conaltel` | Electrical technology (CONALTEL) | cedula | Yes |
| `co.consejo_mecanica` | Mechanical/Electronic engineering | cedula | Yes |
| `co.cpae` | Business administration (CPAE) | cedula | Yes |
| `co.cpip` | Petroleum engineering (CPIP) | cedula | Yes |
| `co.cpiq` | Chemical engineering (CPIQ) | cedula | Yes |
| `co.cpnaa` | Architecture (CPNAA) | cedula, pasaporte | Yes |
| `co.cpnt` | Topography (CPNT) | cedula | Yes |
| `co.cpbiol` | Biology (CPBiol) | cedula | Yes |
| `co.veterinario` | Veterinary medicine (COMVEZCOL) | cedula | Yes |
| `co.urna` | Law professionals (CSJ) | cedula, nit | Yes |

### United States (5 sources)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `us.ofac` | OFAC SDN sanctions list (US Treasury) | cedula, nit, pasaporte, custom | No |
| `us.nhtsa_vin` | VIN decode (NHTSA vPIC) | vin | No |
| `us.nhtsa_recalls` | Vehicle safety recalls (NHTSA) | custom | No |
| `us.nhtsa_complaints` | Vehicle safety complaints (NHTSA) | custom | No |
| `us.epa_fuel_economy` | EPA fuel economy ratings | custom | No |

### Ecuador (6 sources)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `ec.sri_ruc` | Tax registry RUC (SRI) | custom | No |
| `ec.ant_citaciones` | Traffic fines (ANT) | cedula, placa, custom | No |
| `ec.cne_padron` | Voter registry (CNE) | cedula | Yes |
| `ec.funcion_judicial` | Judicial processes (Función Judicial) | cedula, custom | Yes |
| `ec.supercias` | Company registry (Superintendencia) | custom | Yes |
| `ec.senescyt` | Professional degrees (SENESCYT) | cedula, custom | Yes |

### Peru (5 sources)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `pe.sunat_ruc` | Tax registry RUC (SUNAT) | custom | Yes |
| `pe.poder_judicial` | Judicial case search (CEJ) | custom | Yes |
| `pe.osce_sancionados` | Sanctioned gov contractors (OSCE) | custom | Yes |
| `pe.sunarp_vehicular` | Vehicle registry (SUNARP) | placa | Yes |
| `pe.servir_sanciones` | Public servant sanctions (SERVIR) | custom | Yes |

### Chile (4 sources)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `cl.sii_rut` | Tax registry RUT (SII) | custom | Yes |
| `cl.pjud` | Judicial case search (PJUD) | custom | Yes |
| `cl.fiscalizacion` | Traffic infractions | placa | Yes |
| `cl.superir` | Insolvency/bankruptcy (Superir) | custom | Yes |

### Mexico (4 sources)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `mx.curp` | Population registry CURP (RENAPO) | custom | Yes |
| `mx.sat_efos` | SAT blacklist EFOS/EDOS | custom | Yes |
| `mx.siem` | Business directory SIEM | custom | Yes |
| `mx.repuve` | Stolen vehicle check (REPUVE) | placa, vin | Yes |

### Argentina (3 sources)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `ar.afip_cuit` | Tax registry CUIT/CUIL (AFIP) | custom | Yes |
| `ar.pjn` | Federal judiciary cases (PJN) | custom | Yes |
| `ar.dnrpa` | Vehicle registration (DNRPA) | placa | Yes |

### Brazil (1 source)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `br.cnpj` | Business registry CNPJ (BrasilAPI) | nit, custom | No |

### Costa Rica (1 source)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `cr.cedula` | Voter registry cédula (TSE) | cedula, custom | Yes |

### Dominican Republic (1 source)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `do.rnc` | Tax registry RNC (DGII) | cedula, nit, custom | Yes |

### Paraguay (1 source)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `py.ruc` | Tax registry RUC (SET/DNIT) | custom | Yes |

### Guatemala (1 source)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `gt.nit` | Tax registry NIT (SAT) | nit, custom | Yes |

### Honduras (1 source)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `hn.rtn` | Tax registry RTN (SAR) | custom | Yes |

### International (2 sources)

| Source | Description | Inputs | Browser |
|--------|-------------|--------|---------|
| `intl.onu` | UN Security Council sanctions list | cedula, nit, pasaporte, custom | No |
| `intl.ship_tracking` | Global vessel position tracking | custom | No |

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
pip install "openquery[serve]"       # FastAPI server + dashboard (fastapi, uvicorn)
pip install "openquery[redis]"       # Redis cache backend
pip install "openquery[captcha]"     # 2captcha paid CAPTCHA solving (last resort)
pip install "openquery[deepface]"    # Face verification (DeepFace + ArcFace)
pip install "openquery[passport]"    # Passport MRZ reading (passporteye)
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

# Source health status
openquery health

# Extract data from ID document photo
openquery ocr --type co.cedula cedula_photo.jpg

# Face verification (compare ID photo vs selfie)
openquery face-verify id_photo.jpg selfie.jpg
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
| `GET` | `/api/v1/sources/health` | Detailed per-source health report |
| `POST` | `/api/v1/ocr/extract` | Extract data from ID document image |
| `POST` | `/api/v1/face/verify` | Face verification (1:1 comparison) |
| `GET` | `/dashboard` | Web dashboard UI |
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
│   ├── co/           # Colombia (72 sources)
│   ├── ec/           # Ecuador (6 sources)
│   ├── pe/           # Peru (5 sources)
│   ├── cl/           # Chile (3 sources)
│   ├── mx/           # Mexico (4 sources)
│   ├── ar/           # Argentina (3 sources)
│   ├── us/           # United States (5 sources)
│   └── intl/         # International (2 sources)
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
| [Sources Guide](docs/sources.md) | All 102 sources across 8 countries with field reference |
| [CAPTCHA Guide](docs/captcha.md) | OCR engines, voting, LLM backends, benchmarks |
| [Audit Guide](docs/audit.md) | Evidence capture, PDF reports, compliance |
| [API Guide](docs/api.md) | REST endpoints, authentication, deployment |
| [Adding Sources](docs/adding-sources.md) | Step-by-step guide to create new source plugins |
| [Test Results](docs/test_results.md) | Real query results against live government services |
| [Competitors](docs/competitors.md) | Competitive landscape analysis (15 tools compared) |
| [Changelog](CHANGELOG.md) | Version history |

## License

[MIT](LICENSE)
