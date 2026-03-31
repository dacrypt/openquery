# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/dacrypt/openquery/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dacrypt/openquery/releases/tag/v0.1.0
