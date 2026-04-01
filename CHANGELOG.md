# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] - 2026-03-31

### Fixed

- **co.combustible**: correct Socrata field names (`bandera`, `direccion`, `precio`) and use `starts_with()` for municipio/departamento matching to handle suffixed values like `"BOGOTA  D.C."`
- **co.estaciones_ev**: add Unicode accents to `tipo_de_estacion` filter (`Estación`), fix field name mappings (`estaci_n`, `direcci_n`, `est_ndar_cargador`), use `starts_with()` for accent-insensitive city matching
- **co.vehiculos**: normalize plate input with `upper().strip()` before querying

## [0.3.0] - 2026-03-31

### Added

- **8 new Colombian vehicle/transport sources**:
  - `co.pico_y_placa` — driving restriction calculator for Bogota, Medellin, Cali (pure logic, no network)
  - `co.peajes` — toll road tariffs from ANI via datos.gov.co Socrata API
  - `co.combustible` — fuel prices by city/station via datos.gov.co
  - `co.estaciones_ev` — EV charging stations map via datos.gov.co
  - `co.siniestralidad` — road crash hotspots via ANSV/datos.gov.co
  - `co.vehiculos` — national vehicle fleet data (plate/brand lookup) via datos.gov.co
  - `co.fasecolda` — vehicle reference prices for insurance (browser-based)
  - `co.recalls` — vehicle safety recall campaigns from SIC (browser-based)
- 5 Socrata API sources require zero browser automation (httpx only)
- Pico y Placa includes 2026 Colombian holiday calendar
- 195 tests (up from 144)

## [0.2.0] - 2026-03-31

### Added

- **3 new Colombian sources**: `co.procuraduria` (disciplinary records), `co.policia` (criminal background), `co.adres` (health system enrollment)
- **PaddleOCR solver** — PP-OCRv5 engine achieving 100% accuracy at ~130ms per CAPTCHA
- **EasyOCR solver** — CRNN-based engine, 85% accuracy standalone
- **VotingSolver** — character-level majority voting across multiple OCR engines (90% combined with EasyOCR+Tesseract)
- **Auto-detection captcha chain** — automatically builds optimal solver chain based on installed engines: PaddleOCR > VotingSolver(EasyOCR+Tesseract) > HuggingFace OCR > 2Captcha
- **LLM QA system** (`core/llm.py`) for knowledge-based CAPTCHAs (Procuraduria)
  - `OllamaQA` — local CPU inference via HTTP, zero Python deps (uses httpx)
  - `HuggingFaceQA` — free-tier cloud inference with `HF_TOKEN`
  - `AnthropicQA` / `OpenAIQA` — paid API fallbacks
  - `ChainedQA` — try backends in order, first success wins
- **Audit & evidence system** (`core/audit.py`, `models/audit.py`)
  - Screenshot capture at key stages (form filled, result, errors)
  - Network request/response logging with timing
  - PDF evidence report generation via Playwright
  - SHA-256 result hashing for integrity verification
  - CLI flags: `--audit` and `--audit-dir`
  - REST API: `audit: true` field in query request/response
- **OCR benchmarking suite** (`tests/e2e/bench_ocr_engines.py`) — compare Tesseract, PaddleOCR, EasyOCR, docTR across real captchas
- **Captcha diagnostics tests** — 19 tests covering confusion matrices, pipeline comparison, confidence calibration, position analysis, ensemble voting
- Optional dependencies: `paddleocr`, `easyocr`, `huggingface`
- 144 unit tests (up from 29)

### Changed

- RUNT source uses auto-detected solver chain instead of hardcoded OCRSolver
- Procuraduria LLM solving refactored from inline httpx calls to composable QASolver chain
- RUNT source now supports cedula input type in addition to VIN and plate

### Fixed

- Procuraduria tests updated for new QA chain architecture

## [0.1.0] - 2026-03-31

### Added

- Core framework with `BaseSource` plugin architecture
- `BrowserManager` for Playwright-based scraping with WAF bypass
- CAPTCHA solving: `OCRSolver` (pytesseract), `TwoCaptchaSolver`, `ChainedSolver`
- Cache backends: in-memory (cachetools), Redis, SQLite
- Per-source token-bucket rate limiter
- Retry with exponential backoff
- **co.simit** — Colombian traffic fines (SIMIT) via Playwright DOM scraping
- **co.runt** — Colombian vehicle registry (RUNT) with CAPTCHA and Imperva WAF bypass
- FastAPI REST API with `/api/v1/query`, `/api/v1/sources`, `/api/v1/health`
- API key authentication middleware
- Typer CLI: `openquery query`, `openquery sources`, `openquery serve`
- Pydantic models for all response types
- Configuration via environment variables (`OPENQUERY_*`)
- Docker and docker-compose support with Redis
- 29 unit tests

[Unreleased]: https://github.com/dacrypt/openquery/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/dacrypt/openquery/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/dacrypt/openquery/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dacrypt/openquery/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dacrypt/openquery/releases/tag/v0.1.0
