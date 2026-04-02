"""RUAF source — Colombian unified social security affiliates registry.

Queries RUAF/SISPRO for health, pension, and labor risk affiliations.

Flow:
1. Navigate to RUAF consultation page
2. Select document type and enter number
3. Solve CAPTCHA
4. Submit and parse affiliation records

Source: https://rufruf.minsalud.gov.co/RuafUI/Consultas
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from openquery.exceptions import CaptchaError, SourceError
from openquery.models.co.ruaf import RuafAfiliacion, RuafResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RUAF_URL = "https://ruaf.sispro.gov.co/AfiliadosRP.aspx"

DOC_TYPE_MAP = {
    DocumentType.CEDULA: "CC",
    DocumentType.PASSPORT: "PA",
}

MAX_RETRIES = 3


@register
class RuafSource(BaseSource):
    """Query Colombian unified affiliates registry (RUAF/SISPRO)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.ruaf",
            display_name="RUAF \u2014 Registro \u00danico de Afiliados",
            description="Colombian unified social security affiliates registry (SISPRO/RUAF)",
            country="CO",
            url=RUAF_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.PASSPORT],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in DOC_TYPE_MAP:
            raise SourceError(
                "co.ruaf",
                f"Unsupported document type: {input.document_type}. Use cedula or passport.",
            )

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                return self._query(
                    input.document_type, input.document_number, audit=input.audit,
                )
            except (SourceError, CaptchaError) as e:
                last_error = e
                logger.warning("Attempt %d failed: %s", attempt + 1, e)
        raise last_error  # type: ignore[misc]

    def _query(
        self, doc_type: DocumentType, doc_number: str, audit: bool = False,
    ) -> RuafResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.ruaf", doc_type.value, doc_number)

        with browser.page(RUAF_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for form to load
                page.wait_for_selector(
                    'select, input[type="text"]',
                    timeout=15000,
                )
                page.wait_for_timeout(2000)

                # Select document type
                doc_select = page.query_selector(
                    'select[id*="tipo"], select[name*="tipo"], select[id*="document"]'
                )
                if doc_select:
                    select_value = DOC_TYPE_MAP.get(doc_type, "CC")
                    page.select_option(
                        'select[id*="tipo"], select[name*="tipo"], select[id*="document"]',
                        value=select_value,
                        timeout=5000,
                    )
                    logger.info("Selected document type: %s", select_value)

                # Fill document number
                doc_input = page.query_selector(
                    'input[type="text"][id*="numero"], '
                    'input[type="text"][id*="documento"], '
                    'input[type="text"][name*="numero"], '
                    'input[type="text"]'
                )
                if not doc_input:
                    raise SourceError("co.ruaf", "Could not find document input field")

                doc_input.fill(doc_number)
                logger.info("Filled document: %s", doc_number)

                # Handle CAPTCHA — look for image captcha
                captcha_img = page.query_selector(
                    'img[id*="captcha"], img[src*="captcha"], img[alt*="captcha"]'
                )
                if captcha_img:
                    self._solve_captcha(page, captcha_img)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Submit
                submit_btn = page.query_selector(
                    'button[type="submit"], input[type="submit"], '
                    'button[id*="consultar"], button[id*="buscar"], '
                    'a[id*="consultar"], a[id*="buscar"]'
                )
                if submit_btn:
                    submit_btn.click()
                else:
                    doc_input.press("Enter")

                page.wait_for_timeout(5000)

                if collector:
                    collector.screenshot(page, "result")

                # Parse result
                result = self._parse_result(page, doc_type, doc_number)

                if collector:
                    result_json = result.model_dump_json()
                    result.audit = collector.generate_pdf(page, result_json)

                return result

            except SourceError:
                raise
            except CaptchaError:
                raise
            except Exception as e:
                raise SourceError("co.ruaf", f"Query failed: {e}") from e

    def _solve_captcha(self, page, captcha_img) -> None:
        """Solve image CAPTCHA using OCR chain."""
        import base64

        from openquery.core.captcha import ChainedSolver, OCRSolver

        # Get captcha image bytes
        src = captcha_img.get_attribute("src") or ""
        if src.startswith("data:"):
            # Base64-encoded image
            image_data = src.split(",", 1)[1] if "," in src else src
            image_bytes = base64.b64decode(image_data)
        else:
            # Fetch image via browser
            result = page.evaluate(f"""async () => {{
                const r = await fetch('{src}');
                const buf = await r.arrayBuffer();
                const bytes = new Uint8Array(buf);
                return btoa(String.fromCharCode(...bytes));
            }}""")
            image_bytes = base64.b64decode(result)

        # Solve with OCR
        solvers = [OCRSolver(max_chars=6)]
        try:
            from openquery.core.captcha import PaddleOCRSolver
            solvers.insert(0, PaddleOCRSolver(max_chars=6))
        except Exception:
            pass

        solver = ChainedSolver(solvers) if len(solvers) > 1 else solvers[0]
        captcha_text = solver.solve(image_bytes)
        logger.info("CAPTCHA solved: %s", captcha_text)

        # Fill captcha field
        captcha_input = page.query_selector(
            'input[id*="captcha"], input[name*="captcha"], '
            'input[id*="codigo"], input[name*="codigo"]'
        )
        if captcha_input:
            captcha_input.fill(captcha_text)
        else:
            raise CaptchaError("co.ruaf", "Could not find CAPTCHA input field")

    def _parse_result(
        self, page, doc_type: DocumentType, doc_number: str,
    ) -> RuafResult:
        """Parse the result page for affiliation records."""
        from datetime import datetime

        body_text = page.inner_text("body")
        body_lower = body_text.lower()

        # Check for errors
        is_error = any(phrase in body_lower for phrase in [
            "captcha incorrecto",
            "datos incorrectos",
            "intente nuevamente",
        ])
        if is_error:
            raise CaptchaError("co.ruaf", "CAPTCHA or form validation failed")

        # Check for no records
        no_records = any(phrase in body_lower for phrase in [
            "no se encontr",
            "sin registros",
            "no registra afiliaciones",
            "no aparece",
        ])

        # Try to extract name
        nombre = ""
        for line in body_text.split("\n"):
            line_stripped = line.strip()
            if any(label in line_stripped.lower() for label in ["nombre", "afiliado"]):
                parts = line_stripped.split(":")
                if len(parts) > 1:
                    nombre = parts[1].strip()
                    break

        # Parse affiliation rows from tables
        afiliaciones: list[RuafAfiliacion] = []
        rows = page.query_selector_all("table tr, .resultado tr, .afiliacion")
        for row in rows:
            cells = row.query_selector_all("td")
            text = row.inner_text().strip().lower()
            if len(cells) >= 3 and any(
                sub in text for sub in ["salud", "pensi", "riesgo", "caja"]
            ):
                cell_texts = [c.inner_text().strip() for c in cells]
                afiliaciones.append(RuafAfiliacion(
                    subsistema=cell_texts[0] if len(cell_texts) > 0 else "",
                    administradora=cell_texts[1] if len(cell_texts) > 1 else "",
                    estado=cell_texts[2] if len(cell_texts) > 2 else "",
                    regimen=cell_texts[3] if len(cell_texts) > 3 else "",
                    fecha_afiliacion=cell_texts[4] if len(cell_texts) > 4 else "",
                ))

        mensaje = ""
        if no_records:
            mensaje = "No registra afiliaciones en RUAF"
        elif afiliaciones:
            mensaje = f"Se encontraron {len(afiliaciones)} afiliaciones"

        return RuafResult(
            queried_at=datetime.now(),
            documento=doc_number,
            tipo_documento=doc_type.value,
            nombre=nombre,
            afiliaciones=afiliaciones,
            total_afiliaciones=len(afiliaciones),
            mensaje=mensaje,
        )
