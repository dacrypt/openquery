"""OSIPTEL licensed operators source — Peru.

Queries OSIPTEL for licensed telecom operators by name.

URL: https://www.osiptel.gob.pe/
Input: operator name (custom)
Returns: licensed operators list
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.osiptel_operadores import OsiptelOperadoresResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OSIPTEL_URL = "https://www.osiptel.gob.pe/empresas-operadoras/"


@register
class OsiptelOperadoresSource(BaseSource):
    """Query OSIPTEL licensed telecom operators by name."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.osiptel_operadores",
            display_name="OSIPTEL — Operadores Licenciados",
            description="Peru OSIPTEL telecom regulator: licensed operator lookup by name",
            country="PE",
            url=OSIPTEL_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        search_term = input.extra.get("operator_name", input.document_number).strip()
        if not search_term:
            raise SourceError(
                "pe.osiptel_operadores",
                "Provide an operator name (extra.operator_name or document_number)",
            )
        return self._fetch(search_term, audit=input.audit)

    def _fetch(self, search_term: str, audit: bool = False) -> OsiptelOperadoresResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)

        try:
            logger.info("Querying OSIPTEL operators: search_term=%s", search_term)

            with browser.sync_context() as ctx:
                page = ctx.new_page()
                page.goto(OSIPTEL_URL, wait_until="domcontentloaded", timeout=self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                search_input = page.query_selector(
                    "input[type='search'], input[type='text'], input[placeholder*='operador' i]"
                )
                if search_input:
                    search_input.fill(search_term)
                    submit = page.query_selector("button[type='submit'], input[type='submit']")
                    if submit:
                        submit.click()
                    else:
                        search_input.press("Enter")
                    page.wait_for_load_state("networkidle", timeout=self._timeout * 1000)

                body_text = page.inner_text("body")
                body_lower = body_text.lower()

                operator_name = ""
                service_type = ""
                license_status = ""

                for line in body_text.split("\n"):
                    line_stripped = line.strip()
                    if search_term.lower() in line_stripped.lower() and not operator_name:
                        operator_name = line_stripped
                    if any(k in line_stripped.lower() for k in ["servicio", "telefonía", "internet"]):  # noqa: E501
                        if not service_type:
                            service_type = line_stripped

                if "concesionari" in body_lower or "autorizado" in body_lower:
                    license_status = "Concesionado"
                elif "no encontr" in body_lower:
                    license_status = "No encontrado"
                else:
                    license_status = "Consultado"

            return OsiptelOperadoresResult(
                queried_at=datetime.now(),
                search_term=search_term,
                operator_name=operator_name,
                service_type=service_type,
                license_status=license_status,
                details=f"OSIPTEL operators query for: {search_term}",
            )

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("pe.osiptel_operadores", f"Query failed: {e}") from e
