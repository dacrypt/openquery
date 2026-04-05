"""OSCE Sancionados source — Peruvian sanctioned government suppliers.

Queries OSCE for suppliers sanctioned/disqualified from government contracting.

Flow:
1. Navigate to OSCE inhabilitados page
2. Enter RUC or supplier name
3. Submit search
4. Parse result table rows
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.pe.osce_sancionados import OsceSancionadosResult, ProveedorSancionado
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

OSCE_URL = "https://www.rnp.gob.pe/consultasenlinea/inhabilitados/busqueda.asp"


@register
class OsceSancionadosSource(BaseSource):
    """Query Peruvian sanctioned supplier registry (OSCE)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="pe.osce_sancionados",
            display_name="OSCE — Proveedores Sancionados",
            description="Peruvian sanctioned government suppliers: disqualifications and sanctions",
            country="PE",
            url=OSCE_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        ruc = input.extra.get("ruc", "")
        name = input.extra.get("name", "")
        if not ruc and not name:
            raise SourceError(
                "pe.osce_sancionados",
                "Must provide extra.ruc or extra.name",
            )
        return self._query(ruc=ruc, name=name, audit=input.audit)

    def _query(
        self,
        ruc: str = "",
        name: str = "",
        audit: bool = False,
    ) -> OsceSancionadosResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector(
                "pe.osce_sancionados", "custom", ruc or name
            )

        with browser.page(OSCE_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_load_state("networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # The page has two separate search sections, each with a plain textbox
                # and its own "Buscar" button (no id/name attrs on the inputs):
                #   Section 1: Buscar por Nombre/Razón o Denominación Social
                #   Section 2: Buscar por RUC/Código de Proveedor Extranjero
                # Below both sections is the image CAPTCHA with a separate code input.
                all_inputs = page.query_selector_all('input[type="text"], input:not([type])')
                # Expected layout: [name_input, ruc_input, captcha_input]

                search_btn = None
                filled_input = None

                if ruc and len(all_inputs) >= 2:
                    # RUC input is the second textbox
                    all_inputs[1].fill(ruc)
                    filled_input = all_inputs[1]
                    logger.info("Filled RUC: %s", ruc)
                    # Find the second "Buscar" button (next to RUC field)
                    buscar_buttons = page.query_selector_all('button:has-text("Buscar")')
                    if len(buscar_buttons) >= 2:
                        search_btn = buscar_buttons[1]
                    elif buscar_buttons:
                        search_btn = buscar_buttons[0]
                elif name and len(all_inputs) >= 1:
                    # Name input is the first textbox
                    all_inputs[0].fill(name)
                    filled_input = all_inputs[0]
                    logger.info("Filled name: %s", name)
                    # Find the first "Buscar" button (next to name field)
                    buscar_buttons = page.query_selector_all('button:has-text("Buscar")')
                    if buscar_buttons:
                        search_btn = buscar_buttons[0]

                # Solve image CAPTCHA — the CAPTCHA image is not marked with captcha
                # attributes; identify it as the img above "Ingrese el Código de la imagen"
                captcha_input = all_inputs[2] if len(all_inputs) >= 3 else None
                captcha_img = page.query_selector('img[src*="captcha" i], img + a + * img, table img')
                # Fallback: any img that precedes a "Ingrese" label
                if not captcha_img:
                    captcha_img = page.query_selector('img')

                if captcha_img and captcha_input:
                    from openquery.core.captcha import ChainedSolver, LLMCaptchaSolver, OCRSolver
                    solvers = []
                    try:
                        solvers.append(LLMCaptchaSolver())
                    except Exception:
                        pass
                    solvers.append(OCRSolver(max_chars=6))
                    chain = ChainedSolver(solvers)
                    for attempt in range(1, 4):
                        try:
                            image_bytes = captcha_img.screenshot()
                            if image_bytes and len(image_bytes) >= 100:
                                text = chain.solve(image_bytes)
                                if text:
                                    captcha_input.fill(text)
                                    logger.info("CAPTCHA solved (attempt %d): %s", attempt, text)
                                    break
                        except Exception as e:
                            logger.warning("CAPTCHA attempt %d failed: %s", attempt, e)
                        # Refresh CAPTCHA via the "Refrescar código" link
                        refresh = page.query_selector('a:has-text("Refrescar"), a[href*="refrescar" i]')
                        if refresh:
                            refresh.click()
                            page.wait_for_timeout(1000)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit via the appropriate Buscar button
                if search_btn:
                    search_btn.click()
                elif filled_input:
                    filled_input.press("Enter")
                else:
                    page.keyboard.press("Enter")

                page.wait_for_timeout(3000)
                page.wait_for_selector(
                    "table, .resultado, #divResultado, .list-group",
                    timeout=15000,
                )

                if collector:
                    collector.screenshot(page, "result")

                result = self._parse_result(page)

                if collector:
                    result.audit = collector.generate_pdf(
                        page, result.model_dump_json()
                    )

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(
                    "pe.osce_sancionados", f"Query failed: {e}"
                ) from e

    def _parse_result(self, page) -> OsceSancionadosResult:
        """Parse the OSCE result page."""
        from datetime import datetime

        body_text = page.inner_text("body")
        result = OsceSancionadosResult(queried_at=datetime.now())

        rows = page.query_selector_all("table tbody tr, table tr")
        sancionados: list[ProveedorSancionado] = []

        for row in rows:
            cells = row.query_selector_all("td")
            if not cells or len(cells) < 3:
                continue
            values = [(c.inner_text() or "").strip() for c in cells]
            sancionado = ProveedorSancionado(
                nombre=values[0] if len(values) > 0 else "",
                ruc=values[1] if len(values) > 1 else "",
                sancion=values[2] if len(values) > 2 else "",
                fecha_inicio=values[3] if len(values) > 3 else "",
                fecha_fin=values[4] if len(values) > 4 else "",
                motivo=values[5] if len(values) > 5 else "",
                estado=values[6] if len(values) > 6 else "",
            )
            sancionados.append(sancionado)

        result.sancionados = sancionados
        result.total_sancionados = len(sancionados)

        # Fallback: extract count from text
        if not sancionados:
            m = re.search(
                r"(\d+)\s*(?:resultado|registro|sancion)", body_text, re.IGNORECASE
            )
            if m:
                result.total_sancionados = int(m.group(1))

        return result
