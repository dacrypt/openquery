"""Empresas Google source — business search via Google Maps scraping.

Scrapes Google Maps search results for business information in Colombia.

Flow:
1. Navigate to Google Maps with search query
2. Wait for results to load
3. Parse business cards from the results panel

Source: https://www.google.com/maps
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.empresas_google import EmpresaGoogle, EmpresasGoogleResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

MAPS_URL = "https://www.google.com/maps"


@register
class EmpresasGoogleSource(BaseSource):
    """Search businesses on Google Maps (Colombia)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.empresas_google",
            display_name="Google Maps — Búsqueda Empresas",
            description="Business search via Google Maps scraping for Colombian businesses",
            country="CO",
            url=MAPS_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        query = input.extra.get("query", input.document_number).strip()
        ubicacion = input.extra.get("ubicacion", "Colombia").strip()

        if not query:
            raise SourceError("co.empresas_google", "Must provide extra['query'] or document_number")

        return self._query(query, ubicacion, audit=input.audit)

    def _query(self, query: str, ubicacion: str, audit: bool = False) -> EmpresasGoogleResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.empresas_google", "query", query)

        search_query = f"{query} {ubicacion}" if ubicacion else query
        search_url = f"{MAPS_URL}/search/{search_query}"

        with browser.page(search_url) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for results to load
                page.wait_for_timeout(5000)

                # Accept cookies/consent if prompted
                consent_btn = page.query_selector(
                    'button[aria-label*="Accept"], button[aria-label*="Aceptar"], '
                    'form[action*="consent"] button'
                )
                if consent_btn:
                    consent_btn.click()
                    page.wait_for_timeout(2000)

                if collector:
                    collector.screenshot(page, "search_results")

                result = self._parse_result(page, query, ubicacion)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except Exception as e:
                raise SourceError("co.empresas_google", f"Query failed: {e}") from e

    def _parse_result(self, page, query: str, ubicacion: str) -> EmpresasGoogleResult:
        from datetime import datetime

        empresas = []

        # Google Maps renders results as div cards with role="article" or specific classes
        result_items = page.query_selector_all(
            'div[role="article"], '
            'a[href*="/maps/place/"], '
            'div[class*="Nv2PK"]'
        )

        for item in result_items[:20]:  # Limit to first 20 results
            try:
                text = item.inner_text()
                lines = [l.strip() for l in text.split("\n") if l.strip()]

                if not lines:
                    continue

                nombre = lines[0] if lines else ""
                direccion = ""
                telefono = ""
                rating = ""
                total_resenas = ""
                categoria = ""
                horario = ""

                for line in lines[1:]:
                    # Rating pattern: "4.5(123)"
                    rating_match = re.search(r"(\d+[.,]\d+)\s*\((\d+)\)", line)
                    if rating_match:
                        rating = rating_match.group(1)
                        total_resenas = rating_match.group(2)
                        continue

                    # Phone pattern
                    phone_match = re.search(r"(\+?\d[\d\s\-]{7,})", line)
                    if phone_match and not telefono:
                        telefono = phone_match.group(1).strip()
                        continue

                    # Address-like lines (contain numbers and common words)
                    if any(kw in line.lower() for kw in ["calle", "carrera", "cra", "cl", "av", "#", "no."]):
                        if not direccion:
                            direccion = line
                            continue

                    # Category-like lines (short, no numbers)
                    if len(line) < 40 and not any(c.isdigit() for c in line) and not categoria:
                        categoria = line
                        continue

                    # Hours pattern
                    if any(kw in line.lower() for kw in ["abierto", "cerrado", "cierra", "abre", "horario"]):
                        horario = line

                if nombre and nombre != query:
                    empresas.append(EmpresaGoogle(
                        nombre=nombre,
                        direccion=direccion,
                        telefono=telefono,
                        rating=rating,
                        total_resenas=total_resenas,
                        categoria=categoria,
                        horario=horario,
                    ))
            except Exception:
                continue

        if not empresas:
            mensaje = "No se encontraron resultados en Google Maps"
        else:
            mensaje = f"Se encontraron {len(empresas)} negocio(s)"

        return EmpresasGoogleResult(
            queried_at=datetime.now(),
            query=query,
            ubicacion=ubicacion,
            empresas=empresas,
            total_empresas=len(empresas),
            mensaje=mensaje,
        )
