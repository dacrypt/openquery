"""SUI electricity tariffs source — live data from Superservicios portal.

Queries SUI (Sistema Único de Información de Servicios Públicos) for
current electricity tariffs by operator and/or estrato.

Protected by Imperva/Incapsula — BrowserManager handles challenge automatically.

Flow:
1. Navigate to SUI tariffs page (Imperva challenge auto-resolved)
2. Wait for page content to fully load
3. Look for filter/search form and fill operator/estrato if available
4. Submit and parse results table
5. Fall back to body text parsing if no structured table found

Usage:
    openquery query co.sui_tarifas --custom search -e '{"ciudad":"Bogota","estrato":"3"}'
    openquery query co.sui_tarifas --custom search -e '{"operador":"ENEL"}'
    openquery query co.sui_tarifas --custom search -e '{"estrato":"2"}'

URL: https://sui.superservicios.gov.co/content/tarifas-energia-electrica
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.sui_tarifas import SuiTarifa, SuiTarifasResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

SUI_URL = "https://sui.superservicios.gov.co/content/tarifas-energia-electrica"

# Map common city names to operator codes used in SUI
_CITY_TO_OPERATOR = {
    "bogota": "ENEL",
    "bogotá": "ENEL",
    "cundinamarca": "ENEL",
    "cali": "EMCALI",
    "medellin": "EPM",
    "medellín": "EPM",
    "antioquia": "EPM",
    "barranquilla": "ELECTRICARIBE",
    "cartagena": "ELECTRICARIBE",
    "bucaramanga": "ESSA",
    "santander": "ESSA",
    "pereira": "CHEC",
    "manizales": "CHEC",
    "caldas": "CHEC",
    "ibague": "ENERTOLIMA",
    "ibagué": "ENERTOLIMA",
    "tolima": "ENERTOLIMA",
    "pasto": "CEDENAR",
    "narino": "CEDENAR",
    "nariño": "CEDENAR",
    "cucuta": "CENS",
    "cúcuta": "CENS",
    "norte de santander": "CENS",
}


@register
class SuiTarifasSource(BaseSource):
    """Query SUI electricity tariffs from Superservicios portal."""

    def __init__(self, timeout: float = 60.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.sui_tarifas",
            display_name="SUI — Tarifas de Energía Eléctrica (Live)",
            description=(
                "Live electricity tariffs from SUI (Superservicios) portal "
                "by operator, city, and estrato"
            ),
            country="CO",
            url=SUI_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query electricity tariffs by ciudad, operador, and/or estrato."""
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "co.sui_tarifas",
                f"Unsupported input type: {input.document_type}",
            )

        ciudad = input.extra.get("ciudad", "").strip()
        operador = input.extra.get("operador", "").strip()
        estrato = input.extra.get("estrato", "").strip()

        if not ciudad and not operador and not estrato:
            raise SourceError(
                "co.sui_tarifas",
                "Provide extra['ciudad'] (e.g. 'Bogota'), "
                "extra['operador'] (e.g. 'ENEL'), or extra['estrato'] (1-6)",
            )

        # Resolve city to operator if operator not specified
        if ciudad and not operador:
            operador = _CITY_TO_OPERATOR.get(ciudad.lower(), ciudad)

        return self._fetch(
            ciudad=ciudad,
            operador=operador,
            estrato=estrato,
            audit=input.audit,
        )

    def _fetch(
        self,
        ciudad: str,
        operador: str,
        estrato: str,
        audit: bool = False,
    ) -> SuiTarifasResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector("co.sui_tarifas", "operador", operador or ciudad)

        try:
            logger.info(
                "Querying SUI tarifas: ciudad=%s operador=%s estrato=%s",
                ciudad,
                operador,
                estrato,
            )

            with browser.page(SUI_URL, wait_until="domcontentloaded") as page:
                if collector:
                    collector.attach(page)

                # Imperva challenge — wait for it to resolve
                timeout_ms = int(self._timeout * 1000)
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
                page.wait_for_timeout(3000)

                if collector:
                    collector.screenshot(page, "page_loaded")

                # Try to interact with filter form if present
                self._try_fill_filters(page, operador, estrato)

                if collector:
                    collector.screenshot(page, "after_filter")

                # Parse results
                result = self._parse_result(page, ciudad, operador, estrato)

                if collector:
                    collector.screenshot(page, "result")
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("co.sui_tarifas", f"Query failed: {e}") from e

    def _try_fill_filters(self, page, operador: str, estrato: str) -> None:
        """Try to fill the operator/estrato filter form if one exists."""
        try:
            # Look for operator select or input
            if operador:
                op_select = page.query_selector(
                    "select[id*='operador' i], select[name*='operador' i], "
                    "select[id*='empresa' i], select[name*='empresa' i]"
                )
                if op_select:
                    op_select.select_option(label=operador)
                    logger.info("Selected operator: %s", operador)
                else:
                    op_input = page.query_selector(
                        "input[id*='operador' i], input[name*='operador' i], "
                        "input[placeholder*='operador' i]"
                    )
                    if op_input:
                        op_input.fill(operador)
                        logger.info("Filled operator input: %s", operador)

            # Look for estrato select or input
            if estrato:
                str_select = page.query_selector(
                    "select[id*='estrato' i], select[name*='estrato' i], "
                    "select[id*='nivel' i], select[name*='nivel' i]"
                )
                if str_select:
                    str_select.select_option(label=estrato)
                    logger.info("Selected estrato: %s", estrato)
                else:
                    str_input = page.query_selector(
                        "input[id*='estrato' i], input[name*='estrato' i]"
                    )
                    if str_input:
                        str_input.fill(estrato)
                        logger.info("Filled estrato input: %s", estrato)

            # Submit if filters were filled
            if operador or estrato:
                submit_btn = page.query_selector(
                    "button[type='submit'], input[type='submit'], "
                    "button[id*='consultar' i], button[id*='buscar' i], "
                    "button[id*='filtrar' i]"
                )
                if submit_btn:
                    submit_btn.click()
                    page.wait_for_load_state("networkidle", timeout=30000)
                    page.wait_for_timeout(2000)

        except Exception as e:
            logger.warning("Filter interaction failed (non-fatal): %s", e)

    def _parse_result(
        self, page, ciudad: str, operador: str, estrato: str
    ) -> SuiTarifasResult:
        """Parse tariff data from the SUI page."""
        tarifas: list[SuiTarifa] = []

        # Try table-based extraction first
        tarifas = self._extract_from_tables(page, operador, estrato)

        # Fall back to body text extraction
        if not tarifas:
            tarifas = self._extract_from_body(page, operador, estrato)

        return SuiTarifasResult(
            queried_at=datetime.now(),
            ciudad=ciudad,
            operador=operador,
            estrato=estrato,
            total=len(tarifas),
            tarifas=tarifas,
        )

    def _extract_from_tables(self, page, operador: str, estrato: str) -> list[SuiTarifa]:
        """Extract tariff rows from HTML tables."""
        tarifas: list[SuiTarifa] = []

        try:
            tables = page.query_selector_all("table")
            if not tables:
                return tarifas

            for table in tables:
                rows = table.query_selector_all("tr")
                if len(rows) < 2:
                    continue

                # Try to detect header row
                headers: list[str] = []
                header_row = rows[0]
                header_cells = header_row.query_selector_all("th, td")
                for cell in header_cells:
                    headers.append(cell.inner_text().strip().lower())

                if not headers:
                    continue

                # Map column names to SuiTarifa fields
                col_map = _map_columns(headers)

                for row in rows[1:]:
                    cells = row.query_selector_all("td")
                    if not cells:
                        continue

                    vals = [c.inner_text().strip() for c in cells]
                    if not any(vals):
                        continue

                    def gv(key: str) -> str:
                        idx = col_map.get(key, -1)
                        return vals[idx] if 0 <= idx < len(vals) else ""

                    tarifa = SuiTarifa(
                        operador=gv("operador") or operador,
                        estrato=gv("estrato") or estrato,
                        periodo=gv("periodo"),
                        valor_kwh=gv("valor_kwh"),
                        componente_generacion=gv("componente_generacion"),
                        componente_transmision=gv("componente_transmision"),
                        componente_distribucion=gv("componente_distribucion"),
                        componente_comercializacion=gv("componente_comercializacion"),
                        componente_perdidas=gv("componente_perdidas"),
                        componente_restricciones=gv("componente_restricciones"),
                    )
                    tarifas.append(tarifa)

        except Exception as e:
            logger.warning("Table extraction failed: %s", e)

        return tarifas

    def _extract_from_body(self, page, operador: str, estrato: str) -> list[SuiTarifa]:
        """Extract tariff data from body text as fallback."""
        tarifas: list[SuiTarifa] = []

        try:
            body_text = page.inner_text("body")
            lines = [ln.strip() for ln in body_text.split("\n") if ln.strip()]

            current: dict[str, str] = {}
            for line in lines:
                lower = line.lower()

                if any(kw in lower for kw in ["kwh", "$/kwh", "valor"]) and not current.get(
                    "valor_kwh"
                ):
                    parts = line.split(":")
                    if len(parts) > 1:
                        current["valor_kwh"] = parts[-1].strip()

                if "generaci" in lower:
                    parts = line.split(":")
                    if len(parts) > 1:
                        current["componente_generacion"] = parts[-1].strip()

                if "transmisi" in lower:
                    parts = line.split(":")
                    if len(parts) > 1:
                        current["componente_transmision"] = parts[-1].strip()

                if "distribuci" in lower:
                    parts = line.split(":")
                    if len(parts) > 1:
                        current["componente_distribucion"] = parts[-1].strip()

                if "comercializaci" in lower:
                    parts = line.split(":")
                    if len(parts) > 1:
                        current["componente_comercializacion"] = parts[-1].strip()

                if "p\u00e9rdida" in lower or "perdida" in lower:
                    parts = line.split(":")
                    if len(parts) > 1:
                        current["componente_perdidas"] = parts[-1].strip()

                if "restricci" in lower:
                    parts = line.split(":")
                    if len(parts) > 1:
                        current["componente_restricciones"] = parts[-1].strip()

            if current:
                tarifas.append(
                    SuiTarifa(
                        operador=operador,
                        estrato=estrato,
                        **{k: v for k, v in current.items() if k in SuiTarifa.model_fields},
                    )
                )

        except Exception as e:
            logger.warning("Body text extraction failed: %s", e)

        return tarifas


def _map_columns(headers: list[str]) -> dict[str, int]:
    """Map column header strings to SuiTarifa field names."""
    mapping: dict[str, int] = {}
    for i, h in enumerate(headers):
        if any(kw in h for kw in ["operador", "empresa", "prestador"]):
            mapping["operador"] = i
        elif any(kw in h for kw in ["estrato", "nivel"]):
            mapping["estrato"] = i
        elif any(kw in h for kw in ["periodo", "mes", "fecha"]):
            mapping["periodo"] = i
        elif any(kw in h for kw in ["cu total", "valor kwh", "tarifa total", "$/kwh"]):
            mapping["valor_kwh"] = i
        elif any(kw in h for kw in ["generaci"]):
            mapping["componente_generacion"] = i
        elif any(kw in h for kw in ["transmisi"]):
            mapping["componente_transmision"] = i
        elif any(kw in h for kw in ["distribuci"]):
            mapping["componente_distribucion"] = i
        elif any(kw in h for kw in ["comercializaci"]):
            mapping["componente_comercializacion"] = i
        elif any(kw in h for kw in ["p\u00e9rdida", "perdida"]):
            mapping["componente_perdidas"] = i
        elif any(kw in h for kw in ["restricci"]):
            mapping["componente_restricciones"] = i
    return mapping
