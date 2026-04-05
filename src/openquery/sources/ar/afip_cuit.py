"""AFIP CUIT source — Argentine federal taxpayer registry.

Queries AFIP's public padron for taxpayer registration details by CUIT.

Flow:
1. Navigate to AFIP constancia page
2. Enter CUIT number
3. Submit and parse taxpayer details
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.afip_cuit import AfipCuitResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# Navigate directly to the iframe URL (the parent page wraps this in an iframe)
AFIP_URL = "https://seti.afip.gob.ar/padron-puc-constancia-internet/jsp/Constancia.jsp"

MAX_RETRIES = 3


def _build_captcha_chain():
    """Build a captcha solver chain for AFIP's 6-char alphanumeric image captcha.

    Primary: PaddleOCR PP-OCRv5 (~100% accuracy, ~130ms).
    Fallback chain: VotingSolver(EasyOCR+Tesseract) -> HuggingFace -> LLM -> 2Captcha.
    Degrades gracefully based on what's installed.
    """
    import os

    from openquery.core.captcha import ChainedSolver, OCRSolver

    solvers = []

    # PaddleOCR (best accuracy ~100%, needs paddleocr+paddlepaddle installed)
    try:
        from openquery.core.captcha import PaddleOCRSolver

        solvers.append(PaddleOCRSolver(max_chars=6))
    except Exception:
        pass

    # Voting (EasyOCR + Tesseract, ~90% combined)
    try:
        from openquery.core.captcha import EasyOCRSolver, VotingSolver

        solvers.append(VotingSolver([EasyOCRSolver(max_chars=6), OCRSolver(max_chars=6)]))
    except Exception:
        solvers.append(OCRSolver(max_chars=6))

    if not solvers:
        solvers.append(OCRSolver(max_chars=6))

    # LLM vision solver (Claude/GPT-4o, needs API key)
    try:
        from openquery.core.captcha import LLMCaptchaSolver

        if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            solvers.append(LLMCaptchaSolver(max_chars=6))
    except Exception:
        pass

    # HuggingFace OCR (optional, needs HF_TOKEN)
    if os.environ.get("HF_TOKEN"):
        try:
            from openquery.core.captcha import HuggingFaceOCRSolver

            solvers.append(HuggingFaceOCRSolver(max_chars=6))
        except Exception:
            pass

    return ChainedSolver(solvers) if len(solvers) > 1 else solvers[0]


@register
class AfipCuitSource(BaseSource):
    """Query Argentine AFIP taxpayer registry by CUIT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.afip_cuit",
            display_name="AFIP — Constancia de CUIT",
            description="Argentine federal taxpayer registry: business name, activities, and tax regime",
            country="AR",
            url=AFIP_URL,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=True,  # Custom text CAPTCHA (not reCAPTCHA)
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        cuit = input.extra.get("cuit", "") or input.document_number
        if not cuit:
            raise SourceError("ar.afip_cuit", "CUIT is required (pass via extra.cuit)")
        return self._query_with_retries(cuit, audit=input.audit)

    def _query_with_retries(self, cuit: str, audit: bool = False) -> AfipCuitResult:
        """Execute query with captcha retry logic."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        solver = _build_captcha_chain()
        last_error: Exception | None = None
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("ar.afip_cuit", "cuit", cuit)

        with browser.page(AFIP_URL, wait_until="networkidle") as page:
            if collector:
                collector.attach(page)

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    return self._do_query(page, cuit, solver, collector)
                except SourceError as e:
                    last_error = e
                    err_msg = str(e).lower()
                    if "captcha" in err_msg or "validacion" in err_msg:
                        logger.warning(
                            "Attempt %d/%d: captcha failed, retrying: %s",
                            attempt, MAX_RETRIES, e,
                        )
                        # Reload for fresh captcha
                        page.goto(AFIP_URL, wait_until="networkidle")
                        continue
                    raise

        raise last_error  # type: ignore[misc]

    def _do_query(
        self, page, cuit: str, solver, collector,
    ) -> AfipCuitResult:
        """Single query attempt against AFIP."""
        try:
            page.wait_for_timeout(2000)

            # Fill CUIT — exact ID from site: #cuit
            cuit_input = page.query_selector('#cuit, input[name="cuit"]')
            if not cuit_input:
                raise SourceError("ar.afip_cuit", "Could not find CUIT input field")
            cuit_input.fill(cuit.replace("-", ""))
            logger.info("Filled CUIT: %s", cuit)

            # Solve CAPTCHA — image with distorted text (6 alphanumeric chars)
            captcha_img = page.query_selector(
                '#imgCaptcha, img[alt*="distorsionadas"], img.ag-captcha-img'
            )
            if captcha_img:
                captcha_bytes = captcha_img.screenshot()
                if captcha_bytes:
                    captcha_text = solver.solve(
                        captcha_bytes, length="6", charset="alphanumeric",
                    )
                    token_input = page.query_selector(
                        '#token, input[name="token"]'
                    )
                    if token_input:
                        token_input.fill(captcha_text)
                        logger.info("Solved CAPTCHA: %s", captcha_text)

            if collector:
                collector.screenshot(page, "form_filled")

            # Submit — exact selector from site: button.ag-btn-primary
            submit = page.query_selector(
                'button.ag-btn-primary, '
                'button[type="submit"], input[type="submit"]'
            )
            if submit:
                submit.click()
            else:
                cuit_input.press("Enter")

            page.wait_for_timeout(3000)
            page.wait_for_selector("body", timeout=15000)

            if collector:
                collector.screenshot(page, "result")

            # Check for captcha error on result page
            body_text = page.inner_text("body")
            if "captcha" in body_text.lower() and (
                "incorrecto" in body_text.lower()
                or "inválido" in body_text.lower()
                or "invalido" in body_text.lower()
            ):
                raise SourceError("ar.afip_cuit", "CAPTCHA validation failed")

            result = self._parse_result(page, cuit)

            if collector:
                result.audit = collector.generate_pdf(
                    page, result.model_dump_json(),
                )

            return result

        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ar.afip_cuit", f"Query failed: {e}") from e

    def _parse_result(self, page, cuit: str) -> AfipCuitResult:
        from datetime import datetime

        body_text = page.inner_text("body")

        result = AfipCuitResult(queried_at=datetime.now(), cuit=cuit)

        # Parse fields
        field_patterns = [
            (r"(?:raz[oó]n\s*social|apellido\s*y\s*nombre|denominaci[oó]n)[:\s]+([^\n]+)", "razon_social"),
            (r"(?:tipo\s*(?:de\s*)?persona)[:\s]+([^\n]+)", "tipo_persona"),
            (r"(?:estado)[:\s]+([^\n]+)", "estado"),
            (r"(?:domicilio\s*fiscal)[:\s]+([^\n]+)", "domicilio_fiscal"),
            (r"(?:r[eé]gimen\s*(?:impositivo)?)[:\s]+([^\n]+)", "regimen_impositivo"),
            (r"(?:fecha\s*(?:de\s*)?contrato\s*social)[:\s]+([^\n]+)", "fecha_contrato_social"),
        ]

        for pattern, field in field_patterns:
            m = re.search(pattern, body_text, re.IGNORECASE)
            if m:
                setattr(result, field, m.group(1).strip())

        # Parse actividades
        actividades = re.findall(
            r"(?:actividad|actividades)[:\s]+([^\n]+)", body_text, re.IGNORECASE,
        )
        if actividades:
            result.actividades = [a.strip() for a in actividades]

        # Try table-based parsing
        rows = page.query_selector_all("table tr, .constancia tr")
        for row in rows:
            cells = row.query_selector_all("td, th")
            if len(cells) >= 2:
                label = (cells[0].inner_text() or "").strip().lower()
                value = (cells[1].inner_text() or "").strip()
                if "razon social" in label or "denominacion" in label:
                    result.razon_social = result.razon_social or value
                elif "estado" in label and not result.estado:
                    result.estado = value
                elif "domicilio" in label and not result.domicilio_fiscal:
                    result.domicilio_fiscal = value

        return result
