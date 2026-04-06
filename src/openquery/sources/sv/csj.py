"""El Salvador court cases source — CSJ.

Queries El Salvador's Corte Suprema de Justicia (CSJ) for
court case information by case number.

Source: https://www.csj.gob.sv/consulta-publica/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.sv.csj import SvCsjResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CSJ_URL = "https://www.csj.gob.sv/consulta-publica/"


@register
class SvCsjSource(BaseSource):
    """Query El Salvador CSJ court cases by case number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="sv.csj",
            display_name="CSJ — Consulta Pública El Salvador",
            description="El Salvador court cases: status, parties, chamber, rulings (CSJ)",
            country="SV",
            url=CSJ_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        case_number = input.extra.get("case_number", "") or input.document_number
        if not case_number:
            raise SourceError("sv.csj", "case_number is required")
        return self._query(case_number.strip(), audit=input.audit)

    def _query(self, case_number: str, audit: bool = False) -> SvCsjResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("sv.csj", "case_number", case_number)

        with browser.page(CSJ_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Fill case number input
                case_input = page.query_selector(
                    'input[id*="expediente"], input[name*="expediente"], '
                    'input[id*="numero"], input[name*="numero"], '
                    'input[id*="referencia"], input[name*="referencia"], '
                    'input[type="text"]'
                )
                if not case_input:
                    raise SourceError("sv.csj", "Could not find case number input field")

                case_input.fill(case_number)
                logger.info("Filled case number: %s", case_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit:
                    submit.click()
                else:
                    case_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, case_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("sv.csj", f"Query failed: {e}") from e

    def _parse_result(self, page, case_number: str) -> SvCsjResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = SvCsjResult(queried_at=datetime.now(), case_number=case_number)
        details: dict[str, str] = {}
        parties: list[str] = []

        field_map = {
            "tribunal": "court",
            "juzgado": "court",
            "sala": "court",
            "cámara": "court",
            "camara": "court",
            "estado": "status",
            "situación": "status",
            "situacion": "status",
            "resolución": "status",
            "resolucion": "status",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            for label, attr in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        setattr(result, attr, value)
                    break
            # Collect parties from lines mentioning common party labels
            if any(kw in lower for kw in ("demandante", "demandado", "parte", "actor", "imputado")):
                if ":" in stripped:
                    val = stripped.split(":", 1)[1].strip()
                    if val:
                        parties.append(val)
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if key and val:
                    details[key] = val

        result.parties = parties
        result.details = details
        return result
