# Contributing to OpenQuery

Thanks for your interest in contributing! This document provides guidelines to make the process smooth.

## Development Setup

```bash
git clone https://github.com/dacrypt/openquery.git
cd openquery
uv sync --all-extras
playwright install chromium
```

## Running Tests

```bash
# Unit tests
uv run pytest

# With coverage
uv run pytest --cov=openquery

# Integration tests (hits real external services)
uv run pytest -m integration
```

## Code Quality

```bash
# Lint
uv run ruff check src/ tests/

# Auto-fix
uv run ruff check --fix src/ tests/
```

## Adding a New Data Source

This is the most common type of contribution. To add a new source:

1. **Create the model** in `src/openquery/models/<country>/` with a Pydantic `BaseModel`
2. **Create the source** in `src/openquery/sources/<country>/` implementing `BaseSource`
3. **Register it** with the `@register` decorator
4. **Add tests** in `tests/test_<source>.py`
5. **Update the README** source table

See [README.md](README.md#adding-a-new-source) for a complete example.

### Source Guidelines

- Use `BrowserManager` for browser automation — don't manage Playwright directly
- Use `CaptchaSolver` for CAPTCHA handling — don't implement solving inline
- Include a `SourceMeta` with accurate `rate_limit_rpm` to be respectful to servers
- Return typed Pydantic models, not raw dicts
- Add both unit tests (mocked) and integration tests (marked with `@pytest.mark.integration`)

## Pull Requests

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Ensure tests pass: `uv run pytest`
4. Ensure linting passes: `uv run ruff check src/ tests/`
5. Write a clear PR description explaining what and why

## Reporting Bugs

Open an issue with:

- Steps to reproduce
- Expected vs actual behavior
- OpenQuery version (`openquery --version`)
- Python version and OS

## Suggesting Sources

If you know of a useful public data source, open an issue with:

- Source name and URL
- What data it provides
- Whether it requires CAPTCHA or authentication
- Country/region it covers
