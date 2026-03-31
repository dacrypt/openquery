"""Fasecolda source — Colombian vehicle reference prices.

Queries the Fasecolda Guía de Valores hidden REST API to fetch
vehicle reference prices by brand and model year.

Flow:
1. Open Fasecolda web page in browser
2. Intercept bearer token from API calls
3. Cascade through API endpoints: categoria → estado → modelo → marca → referencia → detalles
4. Return matching vehicle values

API base: https://guiadevalores.fasecolda.com/apifasecolda/api/
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.fasecolda import FasecoldaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

FASECOLDA_PAGE = "https://guiadevalores.fasecolda.com/ConsultaExplorador/"
API_BASE = "https://guiadevalores.fasecolda.com/apifasecolda/api"

# Default category ID for automobiles
DEFAULT_CATEGORY_ID = 1
# Default state: usado (used)
DEFAULT_STATE_ID = 2


@register
class FasecoldaSource(BaseSource):
    """Query Fasecolda vehicle reference prices."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.fasecolda",
            display_name="Fasecolda — Guía de Valores de Vehículos",
            description="Colombian vehicle reference prices from Fasecolda",
            country="CO",
            url=FASECOLDA_PAGE,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query Fasecolda by brand and model year.

        Expects:
            input.extra["marca"]  — brand name (e.g., "TESLA", "CHEVROLET")
            input.extra["modelo"] — model year (e.g., 2026)
        """
        if input.document_type != DocumentType.CUSTOM:
            raise SourceError(
                "co.fasecolda",
                f"Only CUSTOM queries supported, got: {input.document_type}",
            )

        marca = input.extra.get("marca", "").upper().strip()
        modelo = input.extra.get("modelo")
        if not marca:
            raise SourceError("co.fasecolda", "extra['marca'] is required")

        return self._query(marca, modelo, audit=input.audit)

    def _query(
        self, marca: str, modelo: int | None = None, audit: bool = False,
    ) -> FasecoldaResult:
        """Navigate to Fasecolda, intercept bearer token, and query API."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.fasecolda", "marca", marca)

        captured_token: dict[str, str] = {}

        with browser.page(FASECOLDA_PAGE, wait_until="networkidle") as page:
            try:
                if collector:
                    collector.attach(page)

                # Intercept bearer token from API requests
                def _handle_request(request):
                    auth = request.headers.get("authorization", "")
                    if auth.lower().startswith("bearer ") and not captured_token:
                        captured_token["token"] = auth
                        logger.info("Captured bearer token from request")

                page.on("request", _handle_request)

                # Wait for page to load and trigger API calls
                page.wait_for_timeout(5000)

                if not captured_token:
                    # Try clicking elements to trigger API calls
                    try:
                        page.click("select, .dropdown, button", timeout=3000)
                        page.wait_for_timeout(3000)
                    except Exception:
                        pass

                if not captured_token:
                    raise SourceError(
                        "co.fasecolda",
                        "Could not capture bearer token from Fasecolda. "
                        "The site may require manual login or have changed its auth flow. "
                        f"Try manually at: {FASECOLDA_PAGE}",
                    )

                token = captured_token["token"]

                # Cascade through API to find the brand and references
                results = self._cascade_api(page, token, marca, modelo)

                if collector:
                    collector.screenshot(page, "result")

                result = self._build_result(marca, modelo, results)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.fasecolda", f"Query failed: {e}") from e

    def _cascade_api(
        self, page, token: str, marca: str, modelo: int | None,
    ) -> list[dict]:
        """Cascade through Fasecolda API endpoints to find vehicle data."""
        cat_id = DEFAULT_CATEGORY_ID
        state_id = DEFAULT_STATE_ID

        # Step 1: Get available model years
        models_data = self._api_fetch(
            page, token,
            f"{API_BASE}/modelo/getmodelo/{cat_id}/{state_id}",
        )

        # Find matching model year
        model_id = None
        if modelo and isinstance(models_data, list):
            for m in models_data:
                year = m.get("modelo") or m.get("id") or m.get("value")
                if str(year) == str(modelo):
                    model_id = m.get("id") or m.get("modelo") or year
                    break

        if model_id is None and modelo:
            # Try using the year directly as model_id
            model_id = modelo

        if model_id is None:
            raise SourceError(
                "co.fasecolda",
                f"Model year {modelo} not found in Fasecolda",
            )

        # Step 2: Get brands for this category/state/year
        brands_data = self._api_fetch(
            page, token,
            f"{API_BASE}/marca/getmarca/{cat_id}/{state_id}/{model_id}",
        )

        # Find matching brand
        brand_id = None
        if isinstance(brands_data, list):
            for b in brands_data:
                brand_name = (
                    b.get("marca") or b.get("nombre") or b.get("name") or ""
                ).upper()
                if marca in brand_name or brand_name in marca:
                    brand_id = b.get("id") or b.get("idMarca")
                    break

        if brand_id is None:
            raise SourceError(
                "co.fasecolda",
                f"Brand '{marca}' not found in Fasecolda for year {modelo}",
            )

        # Step 3: Get references for this brand
        refs_data = self._api_fetch(
            page, token,
            f"{API_BASE}/referenciauno/getgeferenciauno/{cat_id}/{state_id}/{model_id}/{brand_id}",
        )

        if not isinstance(refs_data, list) or not refs_data:
            return []

        # Step 4: Get full details for each reference
        results = []
        for ref in refs_data[:20]:  # Limit to first 20 references
            ref_id = ref.get("id") or ref.get("idReferencia")
            if ref_id is None:
                continue
            try:
                detail = self._api_fetch(
                    page, token,
                    f"{API_BASE}/listacodigos/getbuscabasica/"
                    f"{cat_id}/{state_id}/{model_id}/{brand_id}/{ref_id}/1",
                )
                if isinstance(detail, list):
                    results.extend(detail)
                elif isinstance(detail, dict):
                    results.append(detail)
            except Exception as e:
                logger.warning("Failed to fetch detail for ref %s: %s", ref_id, e)

        return results

    def _api_fetch(self, page, token: str, url: str) -> list | dict:
        """Fetch from Fasecolda API using browser context."""
        result = page.evaluate(f"""async () => {{
            const r = await fetch('{url}', {{
                headers: {{ 'Authorization': '{token}' }},
            }});
            if (!r.ok) return {{ __error: true, status: r.status, text: await r.text() }};
            return await r.json();
        }}""")

        if isinstance(result, dict) and result.get("__error"):
            status = result.get("status", 0)
            text = result.get("text", "")[:200]
            raise SourceError(
                "co.fasecolda", f"API returned {status}: {text}",
            )

        return result

    def _build_result(
        self, marca: str, modelo: int | None, results: list[dict],
    ) -> FasecoldaResult:
        """Build FasecoldaResult from API data."""
        first = results[0] if results else {}

        return FasecoldaResult(
            marca=marca,
            linea=str(first.get("referencia") or first.get("linea") or ""),
            modelo=modelo or 0,
            valor=int(first.get("valor") or first.get("precio") or 0),
            cilindraje=int(first.get("cilindraje") or 0),
            combustible=str(first.get("combustible") or first.get("tipoCombustible") or ""),
            transmision=str(first.get("transmision") or ""),
            puertas=int(first.get("puertas") or 0),
            pasajeros=int(first.get("pasajeros") or first.get("capacidadPasajeros") or 0),
            codigo_fasecolda=str(first.get("codigoFasecolda") or first.get("codigo") or ""),
            resultados=results,
        )
