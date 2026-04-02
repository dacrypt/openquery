# OpenQuery — Claude Code Guide

Unified CLI + REST API for querying 102+ public data sources across 8 countries.
Python 3.12+, managed with `uv`.

## Quick Commands

```bash
uv run pytest --tb=short -q                    # Run all unit tests
uv run pytest -m integration --tb=short        # Run integration tests (hit real services)
uv run pytest tests/test_simit.py -v           # Run specific test file
uv run ruff check src/ tests/                  # Lint
uv run ruff format src/ tests/                 # Format
uv run openquery query co.simit --cedula 123   # CLI query
uv run openquery sources                       # List all sources
uv run openquery serve                         # Start API server
```

## Architecture

```
src/openquery/
  sources/<country>/<source>.py   # Source implementation (@register decorator)
  models/<country>/<source>.py    # Pydantic response model
  core/                           # browser, captcha, cache, audit, rate_limit, llm, health
  commands/                       # CLI commands (Typer)
  server/                         # FastAPI REST API
  config.py                       # Settings (env prefix: OPENQUERY_)
  exceptions.py                   # SourceError, CaptchaError, RateLimitError, etc.
tests/
  test_<source>.py                # Unit tests per source
  conftest.py                     # Shared fixtures
```

## Adding a New Source (checklist)

1. **Model** — `src/openquery/models/<country>/<source>.py`
   - Inherit `BaseModel`, all fields with defaults
   - Include `audit: Any | None = Field(default=None, exclude=True)`
2. **Source** — `src/openquery/sources/<country>/<source>.py`
   - Decorate class with `@register`
   - Implement `meta() -> SourceMeta` and `query(input: QueryInput) -> ResultModel`
   - Raise `SourceError("source.name", "message")` on failures
3. **Register import** — Add `import openquery.sources.<country>.<source>` in `sources/__init__.py` `_ensure_loaded()`
4. **Tests** — `tests/test_<source>.py` with classes: `TestResult`, `TestSourceMeta`, `TestParseResult`
5. **README** — Update sources table
6. **CHANGELOG** — Add entry

## Source Implementation Patterns

### Browser source (most common)
```python
@register
class XxxSource(BaseSource):
    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(name="co.xxx", country="CO", ...)

    def query(self, input: QueryInput) -> XxxResult:
        from openquery.core.browser import BrowserManager
        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        with browser.sync_context() as ctx:
            page = ctx.new_page()
            # ... scraping logic ...
            return XxxResult(...)
```

### API source (no browser)
```python
def query(self, input: QueryInput) -> XxxResult:
    import httpx
    resp = httpx.get(f"https://api.example.com/{input.document_number}", timeout=15.0)
    return XxxResult(**resp.json())
```

### CAPTCHA sources
- Image CAPTCHA: use `_build_captcha_chain()` from `core/captcha.py`
- Knowledge CAPTCHA: use `build_qa_chain()` from `core/llm.py`
- reCAPTCHA v2: use solver providers (2captcha, capsolver, capmonster, anticaptcha)

## Naming Conventions

| Thing | Pattern | Example |
|-------|---------|---------|
| Source name | `<country>.<source>` | `co.simit`, `us.nhtsa_vin` |
| Source class | `<CamelCase>Source` | `SimitSource`, `NhtsaVinSource` |
| Result model | `<CamelCase>Result` | `SimitResult`, `NhtsaVinResult` |
| Source file | `sources/<country>/<snake>.py` | `sources/co/simit.py` |
| Model file | `models/<country>/<snake>.py` | `models/co/simit.py` |
| Test file | `test_<snake>.py` | `test_simit.py` |
| Test class | `Test<Feature>` | `TestSimitResult`, `TestSimitSourceMeta` |
| Country code | ISO 3166-1 alpha-2 | CO, US, PE, EC, MX, CL, AR |
| Constants | UPPER_SNAKE_CASE | `SIMIT_URL`, `MAX_RETRIES` |

## Code Style

- Always start modules with `from __future__ import annotations`
- Type hints on all function signatures
- `logger = logging.getLogger(__name__)` per module
- Lazy imports for heavy deps (inside methods, not at module level)
- Line length: 100 chars (ruff)
- Google-style docstrings
- Raise `SourceError(source_name, msg)` — never bare `Exception`

## Exception Hierarchy

```
OpenQueryError
  SourceError(source, message)
    CaptchaError(source, message)
  RateLimitError(source, retry_after)
  DocumentOCRError(source, message)
  FaceVerificationError(message)
  CacheError
```

## Testing Patterns

- **Unit tests**: mock browser with `MagicMock`, test parsing logic directly
- **Integration tests**: mark with `@pytest.mark.integration`, hit real services
- **Model tests**: default values, JSON roundtrip (`model_validate_json`/`model_dump_json`), audit exclusion
- **Never use personal data** in tests — use public/dummy identifiers only

## Commit Messages

```
feat: <description> — <context/impact>
fix: <description> — <test results>
test: <description>
docs: <description>
chore: <description>
```

Include test pass counts when relevant: `— 43/43 OK`

## Key Files

- `src/openquery/sources/base.py` — BaseSource ABC, DocumentType, QueryInput, SourceMeta
- `src/openquery/sources/__init__.py` — @register decorator, get_source(), _ensure_loaded()
- `src/openquery/core/browser.py` — BrowserManager (Patchright stealth)
- `src/openquery/core/captcha.py` — Multi-engine CAPTCHA solver chains
- `src/openquery/core/audit.py` — AuditCollector (screenshots, network, PDF evidence)
- `src/openquery/config.py` — Settings class (all env vars: OPENQUERY_*)
- `docs/adding-sources.md` — Detailed guide for new source plugins
