"""Brazil ANTT RNTRC source — carrier registry (RNTRC).

Queries ANTT's public portal for carrier registration status, RNTRC number,
transport type, and enabled/disabled status. Browser-based form with a simple
checkbox anti-bot guard (no image/audio CAPTCHA).

Portal: https://consultapublica.antt.gov.br/Site/ConsultaRNTRC.aspx
"""

from __future__ import annotations

import logging

from openquery.exceptions import SourceError
from openquery.models.br.antt_rntrc import AnttRntrcResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

ANTT_URL = "https://consultapublica.antt.gov.br/Site/ConsultaRNTRC.aspx"

# Selectors
_SEL_RADIO_TRANSPORTADOR = "#Corpo_rbTipoConsulta_0"  # Por Transportador
_SEL_RADIO_VEICULO = "#Corpo_rbTipoConsulta_2"         # Por Veículo
_SEL_RNTRC_INPUT = "#Corpo_txtRNTRC"
_SEL_CPF_CNPJ_INPUT = "#Corpo_txtCPFCNPJ"
_SEL_CHECKBOX = "input[type='checkbox']"
_SEL_BUTTON = "#Corpo_btnConsultar"
_SEL_RESULT_TABLE = (
    "table.resultado, table[id*='Grid'], table[id*='grid'], "
    "table[id*='Result'], table"
)


@register
class AnttRntrcSource(BaseSource):
    """Query Brazil ANTT carrier registry (RNTRC) from the public portal."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="br.antt_rntrc",
            display_name="ANTT RNTRC — Registro Nacional de Transportadores Rodoviários de Cargas",
            description=(
                "Brazil ANTT carrier registry: registration status, RNTRC number, "
                "transport type, enabled/disabled status. Accepts CNPJ, CPF, RNTRC, or plate."
            ),
            country="BR",
            url=ANTT_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> AnttRntrcResult:
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "br.antt_rntrc",
                "Use DocumentType.CUSTOM with extra={'search_type': 'cnpj|cpf|rntrc|plate', "
                "'search_value': '<value>'}",
            )

        search_type = input.extra.get("search_type", "").lower().strip()
        search_value = (
            input.extra.get("search_value", "")
            or input.document_number
        ).strip()

        if not search_value:
            raise SourceError("br.antt_rntrc", "search_value is required")
        if search_type not in ("cnpj", "cpf", "rntrc", "plate", ""):
            raise SourceError(
                "br.antt_rntrc",
                f"Invalid search_type '{search_type}'. Use: cnpj, cpf, rntrc, plate",
            )

        # Default to rntrc if numeric only, else try to infer
        if not search_type:
            clean = search_value.replace(".", "").replace("/", "").replace("-", "")
            if clean.isdigit() and len(clean) == 14:
                search_type = "cnpj"
            elif clean.isdigit() and len(clean) == 11:
                search_type = "cpf"
            elif clean.isdigit():
                search_type = "rntrc"
            else:
                search_type = "plate"

        return self._query(search_type, search_value, audit=input.audit)

    def _query(
        self, search_type: str, search_value: str, audit: bool = False
    ) -> AnttRntrcResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("br.antt_rntrc", search_type, search_value)

        with browser.page(ANTT_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=20000)
                page.wait_for_timeout(1000)

                # Select search mode: plate → Por Veículo, otherwise Por Transportador
                if search_type == "plate":
                    radio = page.query_selector(_SEL_RADIO_VEICULO)
                    if radio:
                        radio.click()
                        page.wait_for_timeout(1000)
                else:
                    radio = page.query_selector(_SEL_RADIO_TRANSPORTADOR)
                    if radio:
                        radio.click()
                        page.wait_for_timeout(500)

                # Fill search fields
                if search_type in ("cnpj", "cpf"):
                    field = page.query_selector(_SEL_CPF_CNPJ_INPUT)
                    if not field:
                        # Fallback: first visible text input
                        field = page.query_selector("input[type='text']")
                    if field:
                        field.fill(search_value)
                elif search_type == "rntrc":
                    field = page.query_selector(_SEL_RNTRC_INPUT)
                    if not field:
                        field = page.query_selector("input[type='text']")
                    if field:
                        field.fill(search_value)
                else:
                    # plate — after switching to Por Veículo the form changes
                    field = page.query_selector("input[type='text']")
                    if field:
                        field.fill(search_value)

                logger.info(
                    "ANTT RNTRC query: type=%s value=%s", search_type, search_value[:4] + "***"
                )

                # Tick the "Eu não sou um robô" checkbox
                checkbox = page.query_selector(_SEL_CHECKBOX)
                if checkbox and not checkbox.is_checked():
                    checkbox.click()
                    page.wait_for_timeout(500)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                btn = page.query_selector(_SEL_BUTTON)
                if btn:
                    btn.click()
                else:
                    if field:
                        field.press("Enter")

                page.wait_for_load_state("networkidle", timeout=15000)
                page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page, search_type, search_value)

                if collector:
                    result.audit = collector.generate_pdf(page, result.model_dump_json())

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("br.antt_rntrc", f"Query failed: {e}") from e

    def _parse_result(
        self, page, search_type: str, search_value: str
    ) -> AnttRntrcResult:
        from datetime import datetime

        body_text = page.inner_text("body")
        result = AnttRntrcResult(
            queried_at=datetime.now(),
            search_type=search_type,
            search_value=search_value,
        )

        # Try table-based parsing first
        rows = page.query_selector_all("table tr")
        details: dict[str, str] = {}

        if rows:
            headers: list[str] = []
            data_row: list[str] = []

            for row in rows:
                cells = row.query_selector_all("td, th")
                cell_texts = [c.inner_text().strip() for c in cells]
                if not any(cell_texts):
                    continue
                # Identify header row by looking for known column names
                lower_row = " ".join(cell_texts).lower()
                if any(k in lower_row for k in ("rntrc", "transportador", "situação", "situacao")):
                    if not headers:
                        headers = cell_texts
                        continue
                if headers and not data_row:
                    data_row = cell_texts
                    break

            if headers and data_row:
                for h, v in zip(headers, data_row):
                    h_lower = h.lower()
                    details[h] = v
                    if "rntrc" in h_lower:
                        result.rntrc_number = v
                    elif any(k in h_lower for k in ("nome", "razão", "razao", "transportador")):
                        result.carrier_name = v
                    elif any(k in h_lower for k in ("situação", "situacao", "status")):
                        result.status = v
                    elif any(k in h_lower for k in ("tipo", "espécie", "especie", "modal")):
                        result.transport_type = v

        # Fallback: line-by-line text parsing
        if not result.rntrc_number and not result.carrier_name:
            field_patterns = {
                "rntrc": "rntrc_number",
                "nome": "carrier_name",
                "razão social": "carrier_name",
                "razao social": "carrier_name",
                "situação": "status",
                "situacao": "status",
                "tipo": "transport_type",
                "espécie": "transport_type",
                "modal": "transport_type",
            }
            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                for label, field in field_patterns.items():
                    if label in lower and ":" in stripped:
                        value = stripped.split(":", 1)[1].strip()
                        if value:
                            setattr(result, field, value)
                            details[label] = value
                        break

        result.details = details
        return result
