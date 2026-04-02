"""Multas Quipux source — Traffic fines via Servicios Digitales (Quipux) portals.

Generic source for Colombian transit offices using the Quipux "Servicios Digitales"
platform (AngularJS SPA + /backavit/ backend). Multiple cities use the same platform.

Cities:
- Envigado: movilidad.envigado.gov.co
- Bello: serviciosdigitales.movilidadavanzadabello.com.co
- Sabaneta: transitosabaneta.utsetsa.com
- Rionegro: movilidad.rionegro.gov.co
- Popayán: www.transitopopayan.com.co
- Manizales: www.movilidadmanizales.com.co
- Cali: movilidadcali.com.co

All use reCAPTCHA v2 (explicit) on the search form.
Requires OPENQUERY_CAPSOLVER_API_KEY (or another reCAPTCHA provider) to solve.

Flow:
1. Navigate to /portal-servicios/
2. Close popup modals
3. Fill search input with cédula/placa
4. Solve reCAPTCHA v2
5. Trigger AngularJS search via Enter key
6. Intercept /backavit/avit/home/findInfoHomePublic API response
7. Parse comparendos from JSON
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

# City configurations: (display_city, display_name, base_url, back_path)
QUIPUX_CITIES = {
    "envigado": (
        "Envigado",
        "Tránsito Envigado — Multas y Comparendos",
        "https://movilidad.envigado.gov.co",
        "/backavit/avit",
    ),
    "bello": (
        "Bello",
        "Tránsito Bello — Multas y Comparendos",
        "https://serviciosdigitales.movilidadavanzadabello.com.co",
        "/backavit/avit",
    ),
    "rionegro": (
        "Rionegro",
        "Tránsito Rionegro — Multas y Comparendos",
        "https://movilidad.rionegro.gov.co",
        "/back-ssdd/avit",
    ),
    "popayan": (
        "Popayán",
        "Tránsito Popayán — Multas y Comparendos",
        "https://www.transitopopayan.com.co",
        "/backavit/avit",
    ),
    "manizales": (
        "Manizales",
        "Tránsito Manizales — Multas y Comparendos",
        "https://www.movilidadmanizales.com.co",
        "/backavit/avit",
    ),
    "cali": (
        "Cali",
        "Tránsito Cali — Multas y Comparendos",
        "https://movilidadcali.com.co",
        "/backavit/avit",
    ),
}


class MultasQuipuxSource(BaseSource):
    """Query traffic fines from a Quipux Servicios Digitales transit portal."""

    def __init__(
        self,
        city_key: str,
        timeout: float = 45.0,
        headless: bool = True,
    ) -> None:
        self._city_key = city_key
        city_name, display_name, base_url, back_path = QUIPUX_CITIES[city_key]
        self._city_name = city_name
        self._display_name = display_name
        self._base_url = base_url
        self._back_path = back_path
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=f"co.multas_{self._city_key}",
            display_name=self._display_name,
            description=f"{self._city_name} traffic fines via Quipux Servicios Digitales",
            country="CO",
            url=f"{self._base_url}/portal-servicios/",
            supported_inputs=[DocumentType.CEDULA, DocumentType.PLATE],
            requires_captcha=True,  # reCAPTCHA v2
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in (DocumentType.CEDULA, DocumentType.PLATE):
            raise SourceError(
                f"co.multas_{self._city_key}",
                f"Unsupported input type: {input.document_type}",
            )
        return self._query(input.document_number, audit=input.audit)

    def _query(self, search_term: str, audit: bool = False) -> MultasTransitoLocalResult:
        from openquery.core.browser import BrowserManager
        from openquery.core.captcha import (
            build_recaptcha_solver,
            extract_recaptcha_sitekey,
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

            collector = AuditCollector(source_name, "cedula/placa", search_term)

        page_url = f"{self._base_url}/portal-servicios/"

        with browser.page(page_url, wait_until="domcontentloaded") as page:
            try:
                if collector:
                    collector.attach(page)

                page.wait_for_timeout(8000)

                # Close popup modals
                page.evaluate("""() => {
                    document.querySelectorAll('.modal.show, .modal.fade.show')
                        .forEach(m => { m.style.display='none'; m.classList.remove('show'); });
                    document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                    document.body.classList.remove('modal-open');
                    document.body.style.overflow = 'auto';
                }""")
                page.wait_for_timeout(500)

                # Intercept API responses
                api_result = {}

                def handle_response(response):
                    url = response.url
                    if "findInfoHomePublic" in url and response.status == 200:
                        try:
                            body = response.text()
                            api_result.update(json.loads(body))
                        except Exception:
                            pass
                    elif "findUsuarios" in url and response.status == 200:
                        try:
                            body = response.text()
                            parsed = json.loads(body)
                            if isinstance(parsed, list) and parsed:
                                api_result["_user"] = parsed[0]
                        except Exception:
                            pass

                page.on("response", handle_response)

                # Solve reCAPTCHA v2
                sitekey = extract_recaptcha_sitekey(page)
                if not sitekey:
                    raise SourceError(source_name, "Could not extract reCAPTCHA sitekey")

                logger.info("Solving reCAPTCHA v2 for %s...", self._city_name)
                token = solver.solve_recaptcha_v2(sitekey, page_url)
                inject_recaptcha_token(page, token)
                logger.info("reCAPTCHA solved and injected")

                # Fill search input and submit
                search_input = page.locator('[ng-model="ctrl.input"]')
                search_input.fill(search_term)
                search_input.press("Enter")
                logger.info("Submitted search for %s: %s", self._city_name, search_term)

                page.wait_for_timeout(10000)

                if collector:
                    collector.screenshot(page, "result")

                return self._parse_response(
                    page, search_term, api_result, collector
                )

            except SourceError:
                raise
            except Exception as e:
                raise SourceError(source_name, f"Query failed: {e}") from e

    def _parse_response(
        self,
        page,
        search_term: str,
        api_result: dict,
        collector,
    ) -> MultasTransitoLocalResult:
        """Parse API response (same structure as Medellín's Quipux backend)."""
        nombre = ""
        user_info = api_result.get("_user", {})
        if user_info:
            parts = [user_info.get("nombre", ""), user_info.get("apellido1", "")]
            nombre = " ".join(p for p in parts if p).strip()

        body_text = page.inner_text("body")
        no_multas = any(
            phrase in body_text.lower()
            for phrase in ["no presenta ninguna multa", "no registra", "no tiene"]
        )

        consulta = api_result.get("consultaMultaOComparendoOutDTO", {})
        if not consulta and no_multas:
            return MultasTransitoLocalResult(
                queried_at=datetime.now(),
                documento=search_term,
                nombre=nombre,
                ciudad=self._city_name,
                mensaje=f"No registra multas ni comparendos en {self._city_name}",
            )

        comparendos: list[ComparendoLocal] = []
        total_deuda = 0.0

        for item in consulta.get("informacionComparendo", []):
            comp = ComparendoLocal(
                numero=str(item.get("numeroComparendo", "")),
                tipo="Comparendo",
                fecha=str(item.get("fechaComparendo", "")),
                estado=str(item.get("estado", "")),
                placa=str(item.get("placa", "")),
                saldo=float(item.get("valorComparendo", 0) or 0),
                total=float(item.get("valorTotal", item.get("valorComparendo", 0)) or 0),
            )
            comparendos.append(comp)
            total_deuda += comp.total

        for item in consulta.get("informacionMulta", []):
            comp = ComparendoLocal(
                numero=str(item.get("numeroResolucion", "")),
                tipo="Multa",
                fecha=str(item.get("fechaResolucion", "")),
                estado=str(item.get("estado", "")),
                placa=str(item.get("placa", "")),
                saldo=float(item.get("valorMulta", 0) or 0),
                total=float(item.get("valorTotal", item.get("valorMulta", 0)) or 0),
            )
            comparendos.append(comp)
            total_deuda += comp.total

        for item in consulta.get("informacionMoroso", []):
            comp = ComparendoLocal(
                numero=str(item.get("numeroResolucion", "")),
                tipo="Moroso",
                fecha=str(item.get("fechaResolucion", "")),
                estado="Moroso",
                placa=str(item.get("placa", "")),
                saldo=float(item.get("valorMoroso", 0) or 0),
                total=float(item.get("valorTotal", item.get("valorMoroso", 0)) or 0),
            )
            comparendos.append(comp)
            total_deuda += comp.total

        result = MultasTransitoLocalResult(
            queried_at=datetime.now(),
            documento=search_term,
            nombre=nombre,
            ciudad=self._city_name,
            total_comparendos=len(comparendos),
            total_deuda=total_deuda,
            comparendos=comparendos,
            mensaje=(
                f"Se encontraron {len(comparendos)} registro(s) en {self._city_name}"
                if comparendos
                else f"No registra multas ni comparendos en {self._city_name}"
            ),
        )

        if collector:
            result_json = result.model_dump_json()
            result.audit = collector.generate_pdf(page, result_json)

        return result


# Register one source per city
@register
class MultasEnvigadoSource(MultasQuipuxSource):
    def __init__(self, **kw):
        super().__init__("envigado", **kw)


@register
class MultasBelloSource(MultasQuipuxSource):
    def __init__(self, **kw):
        super().__init__("bello", **kw)


@register
class MultasRionegropSource(MultasQuipuxSource):
    def __init__(self, **kw):
        super().__init__("rionegro", **kw)


@register
class MultasPopayanSource(MultasQuipuxSource):
    def __init__(self, **kw):
        super().__init__("popayan", **kw)


@register
class MultasManizalesSource(MultasQuipuxSource):
    def __init__(self, **kw):
        super().__init__("manizales", **kw)


@register
class MultasCaliSource(MultasQuipuxSource):
    def __init__(self, **kw):
        super().__init__("cali", **kw)
