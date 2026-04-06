"""CANTV source — Venezuela phone/internet service lookup.

Queries the CANTV portal for service status, plan, and debt information
by phone number.

Source: https://www.cantv.com.ve/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ve.cantv import CantvResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

CANTV_URL = "https://www.cantv.com.ve/"


@register
class CantvSource(BaseSource):
    """Query Venezuela CANTV phone/internet service by phone number."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ve.cantv",
            display_name="CANTV — Consulta de Servicio",
            description=(
                "Venezuela CANTV telecom service lookup: service status, plan, and debt by phone number"  # noqa: E501
            ),
            country="VE",
            url=CANTV_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        phone_number = (
            input.extra.get("phone_number", "") or input.document_number.strip()
        )
        if not phone_number:
            raise SourceError("ve.cantv", "Phone number is required (use extra.phone_number or document_number)")  # noqa: E501
        return self._query(phone_number=phone_number, audit=input.audit)

    def _query(self, phone_number: str, audit: bool = False) -> CantvResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ve.cantv", "phone_number", phone_number)

        with browser.page(CANTV_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                phone_input = page.query_selector(
                    'input[name*="telefono"], input[name*="phone"], '
                    'input[id*="telefono"], input[id*="phone"], '
                    'input[placeholder*="telefono"], input[placeholder*="número"], '
                    'input[type="tel"], input[type="text"]'
                )
                if not phone_input:
                    raise SourceError("ve.cantv", "Could not find phone number input field")

                phone_input.fill(phone_number)
                logger.info("Querying CANTV for phone: %s", phone_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                submit_btn = page.query_selector(
                    'input[type="submit"], button[type="submit"], '
                    'button:has-text("Consultar"), button:has-text("Buscar"), '
                    'input[value*="Consultar"], input[value*="Buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    phone_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, phone_number)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ve.cantv", f"Query failed: {e}") from e

    def _parse_result(self, page, phone_number: str) -> CantvResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        service_status = ""
        plan = ""
        debt_amount = ""

        field_map = {
            "estado": "service_status",
            "estatus": "service_status",
            "status": "service_status",
            "plan": "plan",
            "servicio": "plan",
            "deuda": "debt_amount",
            "monto": "debt_amount",
            "saldo": "debt_amount",
        }

        for line in body_text.split("\n"):
            stripped = line.strip()
            lower = stripped.lower()
            for label, field in field_map.items():
                if label in lower and ":" in stripped:
                    value = stripped.split(":", 1)[1].strip()
                    if value:
                        if field == "service_status" and not service_status:
                            service_status = value
                        elif field == "plan" and not plan:
                            plan = value
                        elif field == "debt_amount" and not debt_amount:
                            debt_amount = value
                    break

        return CantvResult(
            queried_at=datetime.now(),
            phone_number=phone_number,
            service_status=service_status,
            plan=plan,
            debt_amount=debt_amount,
            details=body_text.strip()[:500],
        )
