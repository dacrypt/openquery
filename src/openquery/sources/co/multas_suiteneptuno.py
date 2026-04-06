"""Multas SuiteNeptuno source — Traffic fines via SIOTWEB/SuiteNeptuno portals.

Generic source for Colombian transit offices using the SuiteNeptuno/SIOTWEB
platform (ASP.NET + DevExpress). Multiple cities use the same platform with
different base URLs.

Cities:
- Floridablanca: tramitesdttf.siotweb.suiteneptuno.com
- Barrancabermeja: tramitesittb.siotweb.com
- Apartadó: apartado.portal-siotweb.suiteneptuno.com
- Los Patios: patios.siotportal.suiteneptuno.com

All share the same reCAPTCHA v2 sitekey and API pattern.
Requires OPENQUERY_CAPSOLVER_API_KEY (or another reCAPTCHA provider) to solve.

Flow:
1. Navigate to /Comparendos/Consultas
2. Fill DevExpress form (tipo búsqueda, tipo documento, identificación)
3. Solve reCAPTCHA v2 via external provider
4. Call ConsultarFotoMultas() which POSTs to ?handler=ListaComparendosPreliquidados
5. Parse comparendos from JSON response
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.multas_transito import (
    ComparendoLocal,
    MultasTransitoLocalResult,
)
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# All SuiteNeptuno portals share this sitekey
RECAPTCHA_SITEKEY = "6Lfp_psUAAAAAEx9iHdk2XtNvmRL3qpHrNiV2Fhc"

# City configurations: (name, display, base_url)
SUITENEPTUNO_CITIES = {
    "floridablanca": (
        "Floridablanca",
        "Tránsito Floridablanca — Multas y Comparendos",
        "https://tramitesdttf.siotweb.suiteneptuno.com",
    ),
    "barrancabermeja": (
        "Barrancabermeja",
        "Tránsito Barrancabermeja — Multas y Comparendos",
        "https://tramitesittb.siotweb.com",
    ),
    "apartado": (
        "Apartadó",
        "Tránsito Apartadó — Multas y Comparendos",
        "https://apartado.portal-siotweb.suiteneptuno.com",
    ),
    "los_patios": (
        "Los Patios",
        "Tránsito Los Patios — Multas y Comparendos",
        "https://patios.siotportal.suiteneptuno.com",
    ),
}


class MultasSuiteNeptunoSource(BaseSource):
    """Query traffic fines from a SuiteNeptuno/SIOTWEB transit portal."""

    def __init__(
        self,
        city_key: str,
        timeout: float = 45.0,
        headless: bool = True,
    ) -> None:
        self._city_key = city_key
        city_name, display_name, base_url = SUITENEPTUNO_CITIES[city_key]
        self._city_name = city_name
        self._display_name = display_name
        self._base_url = base_url
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=f"co.multas_{self._city_key}",
            display_name=self._display_name,
            description=f"{self._city_name} traffic fines via SuiteNeptuno/SIOTWEB portal",
            country="CO",
            url=f"{self._base_url}/Comparendos/Consultas",
            supported_inputs=[DocumentType.CEDULA],
            requires_captcha=True,  # reCAPTCHA v2
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.CEDULA:
            raise SourceError(
                f"co.multas_{self._city_key}",
                f"Unsupported input type: {input.document_type}. Use CEDULA.",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, doc_number: str, audit: bool = False) -> MultasTransitoLocalResult:
        from openquery.core.browser import BrowserManager
        from openquery.core.captcha import (
            build_recaptcha_solver,
            inject_recaptcha_token,
        )

        source_name = f"co.multas_{self._city_key}"
        solver = build_recaptcha_solver()
        if not solver:
            raise SourceError(
                source_name,
                "reCAPTCHA v2 solver required. Set OPENQUERY_CAPSOLVER_API_KEY "
                "or another provider API key.",
            )

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector

            collector = AuditCollector(source_name, "cedula", doc_number)

        page_url = f"{self._base_url}/Comparendos/Consultas"

        with browser.page(page_url, wait_until="domcontentloaded") as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_timeout(5000)

                # Intercept the consulta API response
                api_data: list[dict] = []

                def handle_response(response):
                    if "ListaComparendosPreliquidados" in response.url:
                        try:
                            body = response.text()
                            parsed = json.loads(body)
                            if isinstance(parsed, list):
                                api_data.extend(parsed)
                        except Exception:
                            pass

                page.on("response", handle_response)

                # Fill form via DevExtreme API
                page.evaluate(
                    """(docNumber) => {
                    var sbs = document.querySelectorAll('.dx-selectbox');

                    // Tipo búsqueda = Identificación
                    DevExpress.ui.dxSelectBox.getInstance(sbs[0])
                        .option('value', 'Identificación');
                }""",
                    doc_number,
                )
                page.wait_for_timeout(1000)

                # Open tipo doc to trigger lazy load, then select CC
                page.evaluate("""() => {
                    var sbs = document.querySelectorAll('.dx-selectbox');
                    DevExpress.ui.dxSelectBox.getInstance(sbs[1]).open();
                }""")
                page.wait_for_timeout(2000)

                page.evaluate("""() => {
                    var sbs = document.querySelectorAll('.dx-selectbox');
                    var sb2 = DevExpress.ui.dxSelectBox.getInstance(sbs[1]);
                    var items = sb2.option('items') || [];
                    for (var i = 0; i < items.length; i++) {
                        if (items[i].Valor1 &&
                            items[i].Valor1.indexOf('Ciudadan') >= 0) {
                            sb2.option('value', items[i]);
                            break;
                        }
                    }
                    sb2.close();
                }""")
                page.wait_for_timeout(500)

                # Fill correo and identificación
                page.evaluate(
                    """(docNumber) => {
                    var correo = document.querySelector('input[name="Correo"]');
                    if (correo) {
                        var inst = DevExpress.ui.dxTextBox.getInstance(
                            correo.closest('.dx-textbox')
                        );
                        if (inst) inst.option('value', 'consulta@openquery.co');
                    }

                    var id = document.querySelector('input[name="Identificacion"]');
                    if (id) {
                        var inst2 = DevExpress.ui.dxTextBox.getInstance(
                            id.closest('.dx-textbox')
                        );
                        if (inst2) inst2.option('value', docNumber);
                    }
                }""",
                    doc_number,
                )

                logger.info("Filled form for %s: %s", self._city_name, doc_number)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Solve reCAPTCHA v2
                logger.info("Solving reCAPTCHA v2 for %s...", self._city_name)
                token = solver.solve_recaptcha_v2(RECAPTCHA_SITEKEY, page_url)
                inject_recaptcha_token(page, token)
                logger.info("reCAPTCHA solved and injected")

                # Call ConsultarFotoMultas()
                page.evaluate("ConsultarFotoMultas()")
                logger.info("Called ConsultarFotoMultas()")
                page.wait_for_timeout(10000)

                if collector:
                    collector.screenshot(page, "result")

                return self._parse_results(page, doc_number, api_data, collector)

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(source_name, f"Query failed: {e}") from e

    def _parse_results(
        self,
        page,
        doc_number: str,
        api_data: list[dict],
        collector,
    ) -> MultasTransitoLocalResult:
        """Parse comparendos from intercepted API response or grid."""
        comparendos: list[ComparendoLocal] = []
        total_deuda = 0.0

        for item in api_data:
            comp_data = item.get("Comparendo", item)
            comp = ComparendoLocal(
                numero=str(comp_data.get("NumeroComparendo", comp_data.get("Comparendo", ""))),
                tipo="Comparendo",
                fecha=str(comp_data.get("FechaComparendo", "")),
                estado=str(comp_data.get("Estado", "")),
                placa=str(comp_data.get("Placa", "")),
                saldo=float(comp_data.get("ValorComparendo", 0) or 0),
                total=float(comp_data.get("ValorComparendo", 0) or 0),
            )
            comparendos.append(comp)
            total_deuda += comp.total

        # Fallback: try parsing from the DevExpress grid if no API data
        if not comparendos:
            grid_data = page.evaluate("""() => {
                try {
                    var grid = $("#gridComparendosPortal").dxDataGrid("instance");
                    var rows = grid.getVisibleRows();
                    return rows.map(r => r.data);
                } catch(e) { return []; }
            }""")
            for row in grid_data or []:
                comp = ComparendoLocal(
                    numero=str(row.get("Comparendo", row.get("NumeroComparendo", ""))),
                    tipo="Comparendo",
                    fecha=str(row.get("FechaComparendo", "")),
                    estado=str(row.get("Estado", "")),
                    placa=str(row.get("Placa", "")),
                    saldo=float(row.get("ValorComparendo", 0) or 0),
                    total=float(row.get("ValorComparendo", 0) or 0),
                )
                comparendos.append(comp)
                total_deuda += comp.total

        result = MultasTransitoLocalResult(
            queried_at=datetime.now(),
            documento=doc_number,
            ciudad=self._city_name,
            total_comparendos=len(comparendos),
            total_deuda=total_deuda,
            comparendos=comparendos,
            mensaje=(
                f"Se encontraron {len(comparendos)} comparendo(s) en {self._city_name}"
                if comparendos
                else f"No registra comparendos en {self._city_name}"
            ),
        )

        if collector:
            result_json = result.model_dump_json()
            result.audit = collector.generate_pdf(page, result_json)

        logger.info(
            "%s results — %d comparendos, total=$%.0f",
            self._city_name,
            result.total_comparendos,
            result.total_deuda,
        )
        return result


# Register one source per city
@register
class MultasFloridablancaSource(MultasSuiteNeptunoSource):
    def __init__(self, **kw):
        super().__init__("floridablanca", **kw)


@register
class MultasBarrancabermejaSource(MultasSuiteNeptunoSource):
    def __init__(self, **kw):
        super().__init__("barrancabermeja", **kw)


@register
class MultasApartadoSource(MultasSuiteNeptunoSource):
    def __init__(self, **kw):
        super().__init__("apartado", **kw)


@register
class MultasLosPatiospSource(MultasSuiteNeptunoSource):
    def __init__(self, **kw):
        super().__init__("los_patios", **kw)
