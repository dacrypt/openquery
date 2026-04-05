"""CURP source — Mexican population registry (RENAPO).

Queries the Mexican CURP validation system via the official gob.mx web portal.
gob.mx is protected by Akamai bot-challenge and requires a real browser session.
The JSON API (https://www.gob.mx/v1/renapoCURP/consulta) only accepts requests
from within the browser page context (not from external XHR/fetch calls), so we
interact with the form directly and parse the rendered DOM result.

Flow:
1. Navigate to https://www.gob.mx/curp/ — Akamai challenge resolves automatically
2. Fill the CURP input and submit the form
3. Wait for the result section to appear or an error modal
4. Extract data from the rendered DOM table
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.mx.curp import CurpResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PAGE_URL = "https://www.gob.mx/curp/"
CHALLENGE_TITLE = "Challenge Validation"
CHALLENGE_TIMEOUT_MS = 30000


@register
class CurpSource(BaseSource):
    """Query Mexican CURP population registry via browser form interaction."""

    def __init__(self, timeout: float = 60.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="mx.curp",
            display_name="CURP — Consulta de CURP",
            description="Mexican CURP validation: personal data and birth certificate status",
            country="MX",
            url=PAGE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        curp = input.extra.get("curp", "") or input.document_number
        if not curp:
            raise SourceError("mx.curp", "CURP is required (pass via extra.curp)")
        return self._query(curp.upper().strip())

    def _query(self, curp: str) -> CurpResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        logger.info("Querying CURP via browser form for: %s", curp)

        try:
            with browser.page(PAGE_URL, wait_until="load") as page:
                # Wait for Akamai challenge to resolve
                try:
                    page.wait_for_function(
                        f"() => document.title !== '{CHALLENGE_TITLE}'",
                        timeout=CHALLENGE_TIMEOUT_MS,
                    )
                except Exception:
                    raise SourceError("mx.curp", "Akamai challenge did not resolve in time")

                # Fill CURP field
                curp_input = page.wait_for_selector("input#curpinput", timeout=10000)
                if not curp_input:
                    raise SourceError("mx.curp", "CURP input field not found")
                curp_input.fill(curp)

                # Submit
                submit_btn = page.wait_for_selector("#searchButton", timeout=5000)
                if not submit_btn:
                    raise SourceError("mx.curp", "Search button not found")
                submit_btn.click()

                # Wait for result: results section visible or error/alert shown
                _result_selector = ".alert-danger, .alert-warning, .modal.in"
                try:
                    page.wait_for_function(
                        "() => {"
                        "  const r = document.querySelector('.results');"
                        f"  const a = document.querySelector('{_result_selector}');"
                        "  return (r && r.offsetParent !== null) || a;"
                        "}",
                        timeout=15000,
                    )
                except Exception:
                    page.wait_for_timeout(6000)

                return self._parse_result(page, curp)

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("mx.curp", f"Query failed: {e}") from e

    def _parse_result(self, page, curp: str) -> CurpResult:
        """Parse result from the DOM after form submission."""
        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        if "datos ingresados no son correctos" in body_lower:
            return CurpResult(queried_at=datetime.now(), curp=curp, estatus="No encontrado")

        if "servicio no está disponible" in body_lower:
            raise SourceError("mx.curp", "RENAPO service temporarily unavailable")

        data = self._extract_table_data(page)

        if not data and "descargar curp" not in body_lower:
            return CurpResult(queried_at=datetime.now(), curp=curp, estatus="No encontrado")

        return CurpResult(
            queried_at=datetime.now(),
            curp=data.get("curp", curp),
            nombre=data.get("nombre(s)", ""),
            apellido_paterno=data.get("primer apellido", ""),
            apellido_materno=data.get("segundo apellido", ""),
            fecha_nacimiento=data.get("fecha de nacimiento", ""),
            sexo=data.get("sexo", ""),
            estado_nacimiento=data.get("entidad de nacimiento", ""),
            estatus=data.get("estatus curp", data.get("estatus", "")),
            documento_probatorio=data.get("documento probatorio", ""),
        )

    def _extract_table_data(self, page) -> dict[str, str]:
        """Extract label/value pairs from the result table rows."""
        try:
            rows = page.query_selector_all("table tr, .results tr")
            data: dict[str, str] = {}
            for row in rows:
                cells = row.query_selector_all("td")
                if len(cells) >= 2:
                    label = cells[0].inner_text().strip().rstrip(":").lower()
                    value = cells[1].inner_text().strip()
                    if label and value:
                        data[label] = value
            return data
        except Exception as e:
            logger.debug("Table extraction failed: %s", e)
            return {}
