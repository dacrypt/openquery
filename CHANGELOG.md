# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2026-04-03

### Added

- **128+ sources across 18 countries** — massive expansion from v0.8.0 (112 sources):
  - `pe.bcrp` — Peru central bank exchange rates (BCRP API)
  - `pe.datos` — Peru open data catalog (datosabiertos.gob.pe, 4452+ datasets)
  - `ec.sri_establecimientos` — Ecuador SRI business establishments (188 for Petroecuador)
  - `cl.datos` — Chile open data catalog (datos.gob.cl CKAN, 10000+ datasets)
  - `cl.mindicador` — Chile economic indicators (UF, USD/CLP, EUR/CLP)
  - `ar.series` — Argentina economic time series (USD/ARS, inflation, GDP)
  - `br.ddd` — Brazil area code lookup (BrasilAPI)
  - `co.secop_integrado` — Colombia unified SECOP I+II procurement
  - `co.secop_procesos` — Colombia procurement processes
  - `co.simit_historico` — Colombia historical traffic fines
  - `co.datos_catalogo` — Colombia datos.gov.co catalog search
  - `pa.contraloria` — Panama Contraloría General news/reports
  - `mx.inegi` — Mexico INEGI geostatistical catalog (32 states, census)
  - `gt.banguat` — Guatemala Banguat exchange rates (SOAP/XML)
  - `do.datos` — Dominican Republic open data catalog
  - `uy.datos` — Uruguay open data catalog
  - `pa.inec` — Panama INEC statistics categories
- **Universal CAPTCHA middleware** (`core/captcha_middleware.py`):
  - Auto-detects reCAPTCHA v2/Enterprise, Cloudflare Turnstile, image CAPTCHAs, Imperva challenges
  - Solves using best available solver (CapSolver → LLM vision → PaddleOCR → Tesseract)
  - Wired into co.rues, co.adres, co.sisben, uy.sucive, py.ruc, ar.afip_cuit
  - Unblocked: ar.afip_cuit (LLM vision), py.ruc, uy.sucive, co.sisben

### Fixed

- `ec.sri_ruc` — No auth needed! Just param name "ruc" instead of "numeroRuc"
- `gt.banguat` — SOAP XML parsing fixed for exchange rate extraction
- `br.fipe` — Test data fixed (valid FIPE code 001267-0)
- `co.procuraduria` — Knowledge CAPTCHA recovered
- `cl.sii_rut` — Intermittent recovery with Patchright
- All 18 countries now have at least 1 working source

## [0.8.0] - 2026-04-03

### Added

- **10 new countries** — OpenQuery now covers **18 countries**, up from 8 in v0.6.0:
  - 🇧🇷 Brazil (7 sources): `br.cnpj`, `br.datajud`, `br.fipe`, `br.cep`, `br.banks`, `br.pix`, `br.corretoras`
  - 🇨🇷 Costa Rica: `cr.cedula` (TSE voter registry)
  - 🇭🇳 Honduras: `hn.rtn` (SAR tax registry + BotDetect CAPTCHA)
  - 🇸🇻 El Salvador: `sv.nit` (DGII NIT/DUI lookup)
  - 🇧🇴 Bolivia: `bo.nit` (SIN tax registry)
  - 🇩🇴 Dominican Republic: `do.rnc` (DGII)
  - 🇵🇾 Paraguay: `py.ruc` (SET/DNIT)
  - 🇬🇹 Guatemala: `gt.nit` (SAT)
  - 🇵🇦 Panama: `pa.ruc` (DGI)
  - 🇺🇾 Uruguay: `uy.sucive` (SUCIVE vehicle patent)
- **5 new Colombian sources**:
  - `co.supersociedades` — insolvency proceedings (Ley 1116)
  - `co.secop_sanciones` — contractor sanctions (datos.gov.co Socrata)
  - `co.secop_procesos` — procurement processes (datos.gov.co Socrata)
  - `co.simit_historico` — historical traffic fines (datos.gov.co Socrata)
  - `cl.superir` — Chilean bankruptcy/insolvency registry
- **1 new Argentina source**: `ar.georef` — address normalization + geocoding (datos.gob.ar API)
- **112 total sources** across 18 countries (was 92 in v0.6.0)
- **58 sources confirmed working live** (was 43 in v0.6.0)
- **Patchright stealth browser** replacing Playwright for WAF bypass
- **Real query test runner** with categorized known limitations

### Changed

- Browser engine: Playwright → Patchright (CDP leak patches)
- OFAC: dead search API → SDN XML bulk download + local search
- mx.curp: browser scraping → JSON API (gob.mx/v1/renapoCURP)
- co.pep: funcionpublica.gov.co → datos.gov.co Socrata API
- RUNT: graceful "no data" handling (captcha solver works, empty result not error)
- 30+ source URL/selector updates for changed government sites
- Browser timeout: 30s → 60s default

## [0.7.0] - 2026-04-02

### Added

- **7 new countries** — OpenQuery now covers **14 countries** (was 8), **98 sources** (was 92):
  - 🇧🇷 **Brazil**: `br.cnpj` — business registry via BrasilAPI (REST API, no auth, no CAPTCHA)
  - 🇨🇷 **Costa Rica**: `cr.cedula` — voter registry via TSE (ASP.NET, no CAPTCHA)
  - 🇩🇴 **Dominican Republic**: `do.rnc` — tax registry via DGII
  - 🇵🇾 **Paraguay**: `py.ruc` — tax registry via SET/DNIT
  - 🇬🇹 **Guatemala**: `gt.nit` — tax registry via SAT
  - 🇭🇳 **Honduras**: `hn.rtn` — tax registry via SAR (BotDetect CAPTCHA + OCR)
  - Plus `co.supersociedades` (insolvency) and `cl.superir` (bankruptcy) from v0.6.0
- **Patchright stealth browser** — replaced Playwright with Patchright (drop-in replacement) to bypass WAF/bot detection:
  - Patches Chrome DevTools Protocol leaks that WAFs use to detect automation
  - Stealth args: `--disable-blink-features=AutomationControlled`
  - Realistic user-agent (Chrome 131), viewport (1920x1080), locale (es-CO)
  - Falls back to Playwright if Patchright not installed
- **reCAPTCHA infrastructure** — config fields for CapSolver, CapMonster, AntiCaptcha API keys
- **Real query test runner** — `tests/e2e/run_real_queries.py` with:
  - 98 public data queries across 14 countries
  - Known status categorization (WAF_BLOCKED, AUTH_REQUIRED, SITE_DOWN, etc.)
  - Auto-generated `docs/test_results.md` with failure analysis
  - Live success rate tracking and accountability reporting
- **2 new Colombian sources**: `co.supersociedades` (insolvency), `cl.superir` (bankruptcy)

### Changed

- **Browser timeout** increased from 30s to 60s default for slow government sites
- **30+ source URL/selector updates** — government sites that changed their HTML structure
- **OFAC** converted from dead search API to SDN XML search (bulk download + local search)
- **mx.curp** converted from browser scraping to direct JSON API (gob.mx/v1/renapoCURP)
- **co.pep** switched to datos.gov.co Socrata API (bypasses SSL issues on funcionpublica.gov.co)
- **3 Socrata dataset IDs** updated: tarifas_energia, rnt_turismo, licencias_salud
- **8 DNS/URL fixes**: RUNT, RUAF, RETHUS, retencion_vehiculos, servir_sanciones, sat_efos
- **Mass selector migration**: `wait_for_selector('input[type="text"]')` → `wait_for_load_state("networkidle")` across 34 source files

### Fixed

- `intl.onu` — added `follow_redirects=True` for UN sanctions XML download
- `co.contraloria` — navigate to iframe URL at cfiscal.contraloria.gov.co
- `co.copnia` — new URL tramites.copnia.gov.co with ASP.NET MVC selectors
- `co.snr` — URL updated to /app/inicio.dma with PrimeFaces selectors
- `cl.sii_rut` — updated to use `input.rut-form` selector
- `ar.afip_cuit` — navigate to iframe URL, added CAPTCHA OCR
- `co.retencion_vehiculos` — Angular Material selectors for Barranquilla portal

## [0.6.0] - 2026-04-01

### Added

- **Health monitoring & circuit breaker** — per-source health tracking with CLOSED/OPEN/HALF_OPEN state machine
  - `GET /api/v1/sources/health` — detailed per-source health report
  - Enhanced `GET /api/v1/health` — now includes source health summary
  - CLI: `openquery health` — source status table
  - Circuit breaker auto-blocks failing sources after configurable threshold
  - `OPENQUERY_CIRCUIT_BREAKER_THRESHOLD` and `OPENQUERY_CIRCUIT_BREAKER_COOLDOWN` settings
- **Document OCR extraction** — extract structured data from ID document images
  - 5 country pipelines: Colombian cedula, Mexican INE, Peruvian DNI, Chilean carnet, Passport MRZ
  - Reuses PaddleOCR engine (already in project for CAPTCHA solving)
  - `POST /api/v1/ocr/extract` — REST API endpoint
  - CLI: `openquery ocr --type co.cedula photo.jpg`
  - Optional `passporteye` dependency for passport MRZ parsing
- **Face verification** — 1:1 face comparison with liveness detection
  - DeepFace with ArcFace backend (99.4% accuracy on LFW)
  - Built-in anti-spoofing (Silent-Face-Anti-Spoofing)
  - `POST /api/v1/face/verify` — REST API endpoint
  - CLI: `openquery face-verify photo.jpg selfie.jpg`
  - Optional `deepface` dependency: `pip install 'openquery[deepface]'`
- **Dashboard UI** — web-based SPA at `/dashboard`
  - Source browser with filtering by country and search
  - Query form with real-time results
  - Query history log
  - Auto-refreshing health status indicators
  - Vanilla HTML/CSS/JS (zero build dependencies)
  - Dark theme, responsive design
- **2 new insolvency/financial sources**:
  - `co.supersociedades` — Colombian insolvency proceedings (Ley 1116, Superintendencia de Sociedades)
  - `cl.superir` — Chilean bankruptcy/insolvency registry (Superintendencia de Insolvencia)
- **Competitive landscape analysis** — `docs/competitors.md` with 15-tool comparison matrix
- **61 new tests** — 579 unit tests total (up from 495)

## [0.5.0] - 2026-04-01

### Added

- **27 new data sources** across 6 countries — total now **100 sources in 8 countries**
- **6 new Colombian sources** closing coverage gaps:
  - `co.estado_cedula_extranjeria` — foreign national ID status (Migración Colombia)
  - `co.validar_policia` — police officer validation (Policía Nacional)
  - `co.rne` — Do Not Call registry (CRC, Ley 2300/2023)
  - `co.camara_comercio_medellin` — Medellín Chamber of Commerce business registry
  - `co.directorio_empresas` — business directory via datos.gov.co open data API
  - `co.empresas_google` — business search via Google Maps scraping
- **Ecuador (6 sources)** — first LATAM expansion:
  - `ec.sri_ruc` — SRI tax registry (REST API)
  - `ec.ant_citaciones` — ANT traffic fines (AJAX JSON API)
  - `ec.cne_padron` — CNE voter registry / identity verification
  - `ec.funcion_judicial` — judicial process search (e-SATJE)
  - `ec.supercias` — Superintendencia de Compañías business registry
  - `ec.senescyt` — professional degree verification
- **Peru (5 sources)**:
  - `pe.sunat_ruc` — SUNAT tax registry
  - `pe.poder_judicial` — judicial case search (CEJ)
  - `pe.osce_sancionados` — sanctioned government contractors (OSCE)
  - `pe.sunarp_vehicular` — vehicle registry (SUNARP)
  - `pe.servir_sanciones` — public servant sanctions (SERVIR)
- **Chile (3 sources)**:
  - `cl.sii_rut` — SII tax registry (Situación Tributaria)
  - `cl.pjud` — Poder Judicial case search
  - `cl.fiscalizacion` — traffic infractions
- **Mexico (4 sources)**:
  - `mx.curp` — CURP population registry (RENAPO)
  - `mx.sat_efos` — SAT EFOS/EDOS blacklist (facturas falsas)
  - `mx.siem` — SIEM business directory
  - `mx.repuve` — REPUVE stolen vehicle check
- **Argentina (3 sources)**:
  - `ar.afip_cuit` — AFIP CUIT/CUIL tax registry
  - `ar.pjn` — federal judiciary case search (PJN)
  - `ar.dnrpa` — vehicle registration lookup (DNRPA)
- **495 unit tests** (up from 392) — 0 regressions

## [0.4.0] - 2026-03-31

### Added

- 73 sources across 3 countries (CO, US, INTL)
- `--custom` and `--extra` CLI flags

## [0.3.2] - 2026-03-31

### Added

- **392 unit tests** (up from 195) — 73% line coverage
- 15 new test files covering previously untested modules:
  - `test_rate_limit.py` — token bucket rate limiter, thread safety
  - `test_retry.py` — exponential backoff, delay caps, exception filtering
  - `test_exceptions.py` — full exception hierarchy
  - `test_config.py` — Settings defaults and env var overrides
  - `test_sources_base.py` — DocumentType, QueryInput, SourceMeta, BaseSource
  - `test_browser.py` — BrowserManager with mocked Playwright
  - `test_socrata_sources.py` — all 5 API sources with mocked httpx
  - `test_browser_sources.py` — policia/adres parse logic, fasecolda/recalls validation
  - `test_api_extended.py` — query endpoint (cache, rate-limit, errors), health, sources
  - `test_cache_extended.py` — SQLiteCache, create_cache factory
  - `test_cli.py` — version, sources, query commands
  - `test_auth.py` — API key middleware (enabled/disabled/bypass)
  - `test_sources_registry.py` — register, get_source, list_sources
  - `test_models_extended.py` — all model JSON roundtrips
  - `test_fasecolda_recalls_logic.py` — browser source logic (mocked)
- `pytest-cov` dev dependency for coverage reporting

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

[Unreleased]: https://github.com/dacrypt/openquery/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/dacrypt/openquery/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/dacrypt/openquery/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/dacrypt/openquery/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/dacrypt/openquery/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/dacrypt/openquery/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/dacrypt/openquery/compare/v0.3.2...v0.4.0
[0.3.2]: https://github.com/dacrypt/openquery/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/dacrypt/openquery/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/dacrypt/openquery/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dacrypt/openquery/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dacrypt/openquery/releases/tag/v0.1.0
