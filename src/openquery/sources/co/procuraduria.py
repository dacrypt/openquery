"""Procuraduria source — Colombian disciplinary records.

Queries the Procuraduria General de la Nacion for disciplinary, criminal,
contractual, and fiscal background records.

The site uses a trivial math captcha (e.g., "¿Cuanto es 3 X 3?") that can
be solved by parsing the arithmetic expression.

Flow:
1. Navigate to https://apps.procuraduria.gov.co/webcert/inicio.aspx?tpo=2
2. Select document type
3. Enter document number
4. Solve math captcha
5. Click "Generar"
6. Parse result (PDF certificate or "no records" message)
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.procuraduria import ProcuraduriaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

PROCURADURIA_URL = "https://apps.procuraduria.gov.co/webcert/inicio.aspx?tpo=2"

# Map our DocumentType to Procuraduria's dropdown values
DOC_TYPE_MAP = {
    DocumentType.CEDULA: "1",      # Cedula de Ciudadania
    DocumentType.NIT: "4",         # NIT
    DocumentType.PASSPORT: "6",    # Pasaporte
}


def _solve_with_qa_chain(question: str) -> str:
    """Use the QA solver chain to answer a knowledge-based captcha question.

    Tries backends in order: Ollama (free/local) → HuggingFace (free/cloud)
    → Anthropic (paid) → OpenAI (paid).
    """
    from openquery.core.llm import QAError, build_qa_chain

    try:
        chain = build_qa_chain()
        return chain.answer(question)
    except QAError as e:
        raise SourceError(
            "co.procuraduria",
            f"Cannot solve captcha: '{question}'. {e.detail}",
        ) from e


@register
class ProcuraduriaSource(BaseSource):
    """Query Colombian disciplinary records (Procuraduria)."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.procuraduria",
            display_name="Procuraduria — Antecedentes Disciplinarios",
            description="Colombian disciplinary, criminal, contractual and fiscal records",
            country="CO",
            url=PROCURADURIA_URL,
            supported_inputs=[DocumentType.CEDULA, DocumentType.NIT, DocumentType.PASSPORT],
            requires_captcha=True,  # Math captcha (trivial)
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type not in DOC_TYPE_MAP:
            raise SourceError(
                "co.procuraduria",
                f"Unsupported document type: {input.document_type}",
            )
        nombre = input.extra.get("nombre", "")
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                return self._query(
                    input.document_type, input.document_number,
                    nombre=nombre, audit=input.audit,
                )
            except SourceError as e:
                last_error = e
                logger.warning("Attempt %d failed: %s", attempt + 1, e)
        raise last_error  # type: ignore[misc]

    def _query(
        self, doc_type: DocumentType, doc_number: str, nombre: str = "",
        audit: bool = False,
    ) -> ProcuraduriaResult:
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.procuraduria", str(doc_type), doc_number)

        with browser.page(PROCURADURIA_URL) as page:
            try:
                if collector:
                    collector.attach(page)

                # Wait for form to load
                page.wait_for_selector("#ddlTipoID", timeout=15000)

                # Select document type
                procuraduria_type = DOC_TYPE_MAP[doc_type]
                page.select_option("#ddlTipoID", procuraduria_type)
                logger.info("Selected document type: %s", procuraduria_type)

                # Fill document number
                page.fill("#txtNumID", doc_number)
                logger.info("Filled document number")

                # Solve captcha (math or name-based)
                captcha_text = page.inner_text("#lblPregunta")
                answer = self._solve_captcha(captcha_text, nombre)
                page.fill("#txtRespuestaPregunta", str(answer))
                logger.info("Captcha: '%s' -> '%s'", captcha_text, answer)

                if collector:
                    collector.screenshot(page, "form_filled")

                # Click "Generar"
                page.click("#btnExportar")
                page.wait_for_timeout(3000)

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
            except Exception as e:
                raise SourceError("co.procuraduria", f"Query failed: {e}") from e

    @staticmethod
    def _solve_captcha(text: str, nombre: str = "") -> str:
        """Solve Procuraduria captcha using pattern matching or LLM fallback.

        Types seen:
        - Math: "¿ Cuanto es 3 X 3 ?"
        - Geography: "¿ Cual es la Capital de Antioquia (sin tilde)?"
        - Name: "¿Escriba las dos primeras letras del primer nombre...?"
        - Other knowledge questions
        """
        # Try math captcha first (cheapest, no LLM needed)
        match = re.search(r"(\d+)\s*[xX*×]\s*(\d+)", text)
        if match:
            return str(int(match.group(1)) * int(match.group(2)))

        match = re.search(r"(\d+)\s*[+]\s*(\d+)", text)
        if match:
            return str(int(match.group(1)) + int(match.group(2)))

        match = re.search(r"(\d+)\s*[-]\s*(\d+)", text)
        if match:
            return str(int(match.group(1)) - int(match.group(2)))

        # Name-based captcha
        if "primeras letras" in text.lower() and nombre:
            first_name = nombre.strip().split()[0] if nombre.strip() else ""
            if len(first_name) >= 2:
                return first_name[:2].upper()

        # Fallback: use QA chain to answer knowledge questions
        return _solve_with_qa_chain(text)

    def _parse_result(
        self, page, doc_type: DocumentType, doc_number: str,
    ) -> ProcuraduriaResult:
        """Parse the result page after submitting the form."""
        from datetime import datetime

        body_text = page.inner_text("body")

        # Check for error messages (captcha wrong, etc.)
        is_error = any(phrase in body_text.lower() for phrase in [
            "no corresponde con lo que espera",
            "datos incorrectos",
            "intente nuevamente",
        ])
        if is_error:
            raise SourceError("co.procuraduria", "Captcha or form validation failed")

        # Check for "no tiene antecedentes" message
        no_records = any(phrase in body_text.lower() for phrase in [
            "no tiene antecedentes",
            "no registra antecedentes",
            "no aparece registrado",
            "no se encontraron registros",
        ])

        # Check for actual records found — be specific to avoid false positives
        # from the page's static text about what antecedentes are
        has_records = any(phrase in body_text.lower() for phrase in [
            "registra sanciones",
            "registra inhabilidades",
            "se encontraron los siguientes",
            "presenta anotaciones",
        ]) and not no_records

        # Try to get the certificate PDF URL
        cert_url = ""
        pdf_link = page.query_selector('a[href*=".pdf"], a[href*="Certificado"]')
        if pdf_link:
            cert_url = pdf_link.get_attribute("href") or ""

        # Extract message
        mensaje = ""
        msg_el = page.query_selector("#lblResultado, #divResultado, .resultado")
        if msg_el:
            mensaje = msg_el.inner_text().strip()
        elif no_records:
            mensaje = "No registra antecedentes vigentes"
        elif has_records:
            mensaje = "Registra antecedentes disciplinarios"

        return ProcuraduriaResult(
            queried_at=datetime.now(),
            cedula=doc_number,
            tipo_documento=str(doc_type),
            tiene_antecedentes=has_records,
            mensaje=mensaje,
            certificado_url=cert_url,
        )
