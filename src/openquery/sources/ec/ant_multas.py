"""ANT Multas source — Ecuador traffic fines by plate or cedula.

Queries Ecuador's ANT (Agencia Nacional de Transito) for pending traffic fines
(multas/citaciones) by plate or cedula number.

Flow:
1. Navigate to the ANT consultation portal
2. Enter plate or cedula
3. Submit and parse fines, amounts, and license points

Source: https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/clp_criterio_consulta.jsp
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ec.ant_multas import AntMultasResult, Multa
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ANT_MULTAS_URL = (
    "https://consultaweb.ant.gob.ec/PortalWEB/paginas/clientes/clp_criterio_consulta.jsp"
)


@register
class AntMultasSource(BaseSource):
    """Query Ecuador traffic fines from ANT portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ec.ant_multas",
            display_name="ANT — Multas de Transito",
            description="Ecuador pending traffic fines, amounts, and license points from ANT",
            country="EC",
            url=ANT_MULTAS_URL,
            supported_inputs=[DocumentType.PLATE, DocumentType.CEDULA],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.PLATE, DocumentType.CEDULA):
            raise SourceError(
                "ec.ant_multas", f"Only plate or cedula supported, got: {input.document_type}"
            )

        search_value = input.document_number.strip()
        if not search_value:
            raise SourceError("ec.ant_multas", "Plate or cedula number is required")

        return self._query(search_value, input.document_type, audit=input.audit)

    def _query(
        self, search_value: str, doc_type: DocumentType, audit: bool = False
    ) -> AntMultasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("ec.ant_multas", doc_type.value, search_value)

        with browser.page(ANT_MULTAS_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Try to select search type (plate vs cedula) if a dropdown/radio is present
                if doc_type == DocumentType.PLATE:
                    type_selector = page.query_selector(
                        'select[name*="tipo"], select[id*="tipo"], '
                        'input[value*="placa"], input[value*="PLACA"]'
                    )
                    if type_selector:
                        tag = type_selector.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            type_selector.select_option(label="Placa")
                        else:
                            type_selector.click()
                else:
                    type_selector = page.query_selector(
                        'input[value*="cedula"], input[value*="CEDULA"], '
                        'input[value*="identificacion"]'
                    )
                    if type_selector:
                        type_selector.click()

                # Fill search input
                search_input = page.query_selector(
                    'input[id*="placa"], input[name*="placa"], '
                    'input[id*="cedula"], input[name*="cedula"], '
                    'input[id*="identificacion"], input[name*="identificacion"], '
                    'input[id*="criterio"], input[name*="criterio"], '
                    'input[type="text"]'
                )
                if not search_input:
                    raise SourceError("ec.ant_multas", "Could not find search input field")

                search_input.fill(search_value)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'button:has-text("Consultar"), button:has-text("Buscar")'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    search_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("ec.ant_multas", f"Query failed: {e}") from e

    def _parse_result(self, page, search_value: str) -> AntMultasResult:
        body_text = page.inner_text("body")

        multas: list[Multa] = []
        total_amount = ""
        points_balance = ""
        details: dict[str, str] = {}

        # Parse key-value pairs from body text
        for line in body_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()

            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key_s = key.strip()
                val_s = val.strip()

                if not key_s or not val_s:
                    continue

                details[key_s] = val_s

                if any(k in lower for k in ("total", "valor total", "monto total")):
                    total_amount = val_s
                elif any(k in lower for k in ("puntos", "saldo puntos", "licencia")):
                    points_balance = val_s

        # Parse table rows for fines
        rows = page.query_selector_all("table tr")
        header_skipped = False
        for row in rows:
            cells = row.query_selector_all("td")
            if not cells:
                # Could be a header row
                header_skipped = False
                continue

            # Skip header rows (th-only rows already skipped above)
            if not header_skipped:
                header_skipped = True
                # Check if this row looks like data (has enough cells)
                if len(cells) < 2:
                    continue

            cell_texts = [c.inner_text().strip() for c in cells]

            if len(cell_texts) >= 2:
                # Map columns heuristically: numero, fecha, tipo, monto, estado, puntos
                multa = Multa(
                    numero=cell_texts[0] if len(cell_texts) > 0 else "",
                    fecha=cell_texts[1] if len(cell_texts) > 1 else "",
                    tipo=cell_texts[2] if len(cell_texts) > 2 else "",
                    monto=cell_texts[3] if len(cell_texts) > 3 else "",
                    estado=cell_texts[4] if len(cell_texts) > 4 else "",
                    puntos=cell_texts[5] if len(cell_texts) > 5 else "",
                    placa=search_value,
                )
                # Only add if numero looks non-empty and non-header
                if multa.numero and multa.numero.lower() not in (
                    "numero",
                    "número",
                    "citacion",
                    "citación",
                    "#",
                    "no.",
                ):
                    multas.append(multa)

        # Try to extract total amount from details if not found yet
        if not total_amount:
            for key, val in details.items():
                if "total" in key.lower():
                    total_amount = val
                    break

        if not points_balance:
            for key, val in details.items():
                if "punto" in key.lower():
                    points_balance = val
                    break

        return AntMultasResult(
            search_value=search_value,
            total_multas=len(multas),
            total_amount=total_amount,
            points_balance=points_balance,
            multas=multas,
            details=details,
        )
