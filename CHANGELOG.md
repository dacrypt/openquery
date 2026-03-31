# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/dacrypt/openquery/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/dacrypt/openquery/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dacrypt/openquery/releases/tag/v0.1.0
