# Adding New Sources

This guide walks through creating a new data source plugin for OpenQuery.

## Architecture Overview

Every source consists of 3 parts:

```
src/openquery/
  models/<country>/<source>.py    # Pydantic response model
  sources/<country>/<source>.py   # Source implementation (scraping logic)
tests/
  test_<source>.py                # Unit tests
```

## Step 1: Create the Response Model

Define a Pydantic model for the data your source returns:

```python
# src/openquery/models/mx/sat.py
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any

class SatResult(BaseModel):
    """Mexican SAT (tax authority) RFC validation result."""

    rfc: str = ""
    nombre: str = ""
    situacion: str = ""           # Active, cancelled, etc.
    regimen_fiscal: str = ""
    fecha_alta: str = ""
    es_valido: bool = False

    # Audit field (always include this for audit support)
    audit: Any | None = Field(default=None, exclude=True)
```

Key points:
- Use `Field(default=...)` for all fields to avoid required-field errors
- Include `audit: Any | None = Field(default=None, exclude=True)` for audit support
- The `exclude=True` ensures audit data is not serialized in JSON responses

## Step 2: Create the Source

```python
# src/openquery/sources/mx/sat.py
"""Mexican SAT RFC validation source."""

from __future__ import annotations

import logging
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta
from openquery.models.mx.sat import SatResult

logger = logging.getLogger(__name__)


@register
class SatSource(BaseSource):
    """Query Mexican SAT for RFC validation."""

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.sat",
            display_name="SAT RFC Validation",
            description="Mexican tax authority RFC lookup",
            country="MX",
            url="https://www.sat.gob.mx/",
            supported_inputs=[DocumentType.RFC],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> SatResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        with browser.sync_context() as ctx:
            page = ctx.new_page()

            # Navigate
            page.goto("https://www.sat.gob.mx/consulta-rfc")
            page.wait_for_load_state("networkidle")

            # Fill form
            page.fill("#rfc-input", input.document_number)
            page.click("#btn-consultar")

            # Wait for result
            page.wait_for_selector(".resultado", timeout=15000)

            # Parse
            nombre = page.text_content(".resultado .nombre") or ""
            situacion = page.text_content(".resultado .situacion") or ""

            return SatResult(
                rfc=input.document_number,
                nombre=nombre.strip(),
                situacion=situacion.strip(),
                es_valido="activo" in situacion.lower(),
            )
```

### The `@register` decorator

This single decorator:
- Registers the source in the global registry
- Makes it available via `openquery query mx.sat`
- Makes it available via the REST API
- Makes it appear in `openquery sources`

OpenQuery now auto-discovers source modules under `src/openquery/sources/<country>/`,
so you no longer need to maintain a long manual import list for each new source file.
The `@register` decorator is still required because discovery imports modules and the
decorator adds the source class to the runtime registry.

Wave 1 source work should keep the America inventory snapshot in sync with contributor guidance.
The America inventory contract lives in `docs/americas-source-inventory.json`, and it applies only
to Americas-country sources. Callable `INTL` runtime connectors remain outside that America
inventory contract until a separate global inventory exists.

### Don't forget `__init__.py`

```python
# src/openquery/sources/mx/__init__.py
"""Mexican data sources."""
```

## Step 3: Add Audit Support

Wrap the query logic with audit capture:

```python
def query(self, input: QueryInput) -> SatResult:
    from openquery.core.browser import BrowserManager

    browser = BrowserManager(headless=self._headless, timeout=self._timeout)
    audit = getattr(input, "audit", False)
    collector = None

    with browser.sync_context() as ctx:
        page = ctx.new_page()

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector(source="mx.sat", document=input.document_number)
            collector.attach(page)

        # ... scraping logic ...

        if collector:
            collector.screenshot(page, "form_filled")

        # ... submit and get result ...

        if collector:
            collector.screenshot(page, "result")

        result = SatResult(rfc=input.document_number, ...)

        if collector:
            record = collector.build_record(page, result_data=result.model_dump())
            collector.generate_pdf(page, record)
            result.audit = record

        return result
```

## Step 4: Add Tests

```python
# tests/test_sat.py
"""Unit tests for SAT source."""

from __future__ import annotations
import pytest
from openquery.models.mx.sat import SatResult
from openquery.sources.mx.sat import SatSource


class TestSatResult:
    def test_default_values(self):
        r = SatResult(rfc="XAXX010101000")
        assert r.es_valido is False
        assert r.nombre == ""

    def test_round_trip_json(self):
        r = SatResult(rfc="XAXX010101000", nombre="Test", es_valido=True)
        restored = SatResult.model_validate_json(r.model_dump_json())
        assert restored.rfc == "XAXX010101000"
        assert restored.es_valido is True

    def test_audit_excluded_from_dump(self):
        r = SatResult(rfc="XAXX010101000")
        r.audit = {"some": "data"}
        dumped = r.model_dump()
        assert "audit" not in dumped


class TestSatSourceMeta:
    def test_meta(self):
        source = SatSource()
        meta = source.meta()
        assert meta.name == "mx.sat"
        assert meta.country == "MX"
        assert meta.requires_browser is True
```

## Step 5: Add CAPTCHA Support (if needed)

If the source uses image CAPTCHAs:

```python
from openquery.sources.co.runt import _build_captcha_chain

solver = _build_captcha_chain()
captcha_text = solver.solve(image_bytes)
```

If the source uses knowledge/text CAPTCHAs:

```python
from openquery.core.llm import build_qa_chain

qa = build_qa_chain()
answer = qa.answer("What is 5 + 3?")
```

## Step 6: Update Documentation

1. Add to the sources table in `README.md`
2. Add a section in `docs/sources.md`
3. Update `docs/americas-source-inventory.json` if the source is part of the America inventory
4. Keep `docs/test_results.md` separate as a live accountability report, not the inventory source of truth
5. Add to the CHANGELOG

### Wave 1 verification note

Wave 1 intentionally does **not** add a new repo-wide typecheck gate. Keep the baseline verification
contract to the documented `ruff` + `pytest` + live accountability workflow, and record the
typecheck deferral in the same wave's ADR/docs update instead of adding a new `mypy`/`pyright`
command now.

## API Sources (no browser)

For sources that have a REST API (no browser needed):

```python
@register
class NhtsaSource(BaseSource):
    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="us.nhtsa",
            requires_browser=False,  # No Playwright needed
            ...
        )

    def query(self, input: QueryInput) -> NhtsaResult:
        import httpx
        resp = httpx.get(
            f"https://api.example.com/lookup/{input.document_number}",
            timeout=15.0,
        )
        data = resp.json()
        return NhtsaResult(**data)
```

## Checklist

- [ ] Model in `src/openquery/models/<country>/`
- [ ] Source in `src/openquery/sources/<country>/` with `@register`
- [ ] `__init__.py` in new country directory
- [ ] Audit support (screenshots, evidence)
- [ ] Tests in `tests/`
- [ ] README sources table updated
- [ ] `docs/sources.md` section added
- [ ] CHANGELOG entry
