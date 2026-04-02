"""Consejos Profesionales sources — Colombian professional council registries.

Each professional council has a similar consultation pattern:
1. Navigate to the council's verification page
2. Enter document number
3. Submit and parse registration/license status

This module registers 10 professional council sources using a factory pattern.
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.consejo_profesional import ConsejoProfesionalResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)


# --- Configuration for each professional council ---

CONSEJOS = [
    {
        "name": "co.conaltel",
        "display_name": "CONALTEL — Tecnólogos en Electricidad",
        "description": "Consejo Profesional Nacional de Tecnólogos en Electricidad, Electromecánica, Electrónica y afines",
        "url": "https://www.conaltel.gov.co/",
        "consejo_label": "CONALTEL",
        "inputs": [DocumentType.CEDULA],
    },
    {
        "name": "co.consejo_mecanica",
        "display_name": "CPIEM — Ing. Mecánica y Electrónica",
        "description": "Consejo Profesional de Ingeniería Mecánica, Electrónica y profesiones afines",
        "url": "https://www.consejoprofesional.org.co/",
        "consejo_label": "Consejo Prof. Ing. Mecánica",
        "inputs": [DocumentType.CEDULA],
    },
    {
        "name": "co.cpae",
        "display_name": "CPAE — Administradores de Empresas",
        "description": "Consejo Profesional de Administración de Empresas (CPAE)",
        "url": "https://www.cpae.gov.co/",
        "consejo_label": "CPAE",
        "inputs": [DocumentType.CEDULA],
    },
    {
        "name": "co.cpip",
        "display_name": "CPIP — Ing. de Petróleos",
        "description": "Consejo Profesional de Ingeniería de Petróleos (CPIP)",
        "url": "https://www.cpip.gov.co/",
        "consejo_label": "CPIP",
        "inputs": [DocumentType.CEDULA],
    },
    {
        "name": "co.cpiq",
        "display_name": "CPIQ — Ing. Química",
        "description": "Consejo Profesional de Ingeniería Química de Colombia (CPIQ)",
        "url": "https://www.cpiq.gov.co/",
        "consejo_label": "CPIQ",
        "inputs": [DocumentType.CEDULA],
    },
    {
        "name": "co.cpnaa",
        "display_name": "CPNAA — Arquitectura",
        "description": "Consejo Profesional Nacional de Arquitectura y sus Profesiones Auxiliares (CPNAA)",
        "url": "https://www.cpnaa.gov.co/",
        "consejo_label": "CPNAA",
        "inputs": [DocumentType.CEDULA, DocumentType.PASSPORT],
    },
    {
        "name": "co.cpnt",
        "display_name": "CPNT — Topografía",
        "description": "Consejo Profesional Nacional de Topografía (CPNT)",
        "url": "https://www.cpnt.gov.co/",
        "consejo_label": "CPNT",
        "inputs": [DocumentType.CEDULA],
    },
    {
        "name": "co.cpbiol",
        "display_name": "CPBiol — Biología",
        "description": "Consejo Profesional de Biología (CPBiol)",
        "url": "https://www.cpbiol.gov.co/",
        "consejo_label": "CPBiol",
        "inputs": [DocumentType.CEDULA],
    },
    {
        "name": "co.veterinario",
        "display_name": "COMVEZCOL — Medicina Veterinaria",
        "description": "Consejo Profesional de Medicina Veterinaria y Zootecnia de Colombia (COMVEZCOL)",
        "url": "https://www.comvezcol.org/",
        "consejo_label": "COMVEZCOL",
        "inputs": [DocumentType.CEDULA],
    },
    {
        "name": "co.urna",
        "display_name": "CSJ — Profesionales del Derecho",
        "description": "Consulta de Profesionales del Derecho y Jueces de Paz",
        "url": "https://www.ramajudicial.gov.co/",
        "consejo_label": "Rama Judicial",
        "inputs": [DocumentType.CEDULA, DocumentType.NIT],
    },
]


def _make_consejo_source(config: dict) -> type[BaseSource]:
    """Factory to create a professional council source class."""

    source_name = config["name"]
    display = config["display_name"]
    desc = config["description"]
    url = config["url"]
    consejo_label = config["consejo_label"]
    inputs = config["inputs"]

    class ConsejoSource(BaseSource):
        __doc__ = f"Query {consejo_label} professional registry."

        def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
            self._timeout = timeout
            self._headless = headless

        def meta(self) -> SourceMeta:
            return SourceMeta(
                name=source_name,
                display_name=display,
                description=desc,
                country="CO",
                url=url,
                supported_inputs=inputs,
                requires_captcha=False,
                requires_browser=True,
                rate_limit_rpm=10,
            )

        def query(self, input: QueryInput) -> BaseModel:
            if input.document_type not in inputs:
                raise SourceError(source_name, f"Unsupported document type: {input.document_type}")
            return self._query(input.document_number, input.document_type, audit=input.audit)

        def _query(self, documento: str, doc_type: DocumentType, audit: bool = False) -> ConsejoProfesionalResult:
            from openquery.core.browser import BrowserManager

            browser = BrowserManager(headless=self._headless, timeout=self._timeout)
            collector = None

            if audit:
                from openquery.core.audit import AuditCollector
                collector = AuditCollector(source_name, doc_type.value, documento)

            with browser.page(url) as page:
                try:
                    if collector:
                        collector.attach(page)

                    page.wait_for_load_state("networkidle", timeout=30000)
                    page.wait_for_timeout(2000)

                    # Fill document number
                    doc_input = page.query_selector(
                        'input[type="text"][id*="documento"], '
                        'input[type="text"][id*="cedula"], '
                        'input[type="text"][id*="numero"], '
                        'input[type="text"][id*="matricula"], '
                        'input[type="text"][name*="documento"], '
                        'input[type="text"][name*="cedula"], '
                        'input[type="text"]'
                    )
                    if not doc_input:
                        raise SourceError(source_name, "Could not find document input field")

                    doc_input.fill(documento)

                    if collector:
                        collector.screenshot(page, "form_filled")

                    # Submit
                    submit_btn = page.query_selector(
                        'button[type="submit"], input[type="submit"], '
                        'button[id*="consultar"], button[id*="buscar"], '
                        'input[id*="consultar"], input[id*="buscar"], '
                        'a[id*="consultar"]'
                    )
                    if submit_btn:
                        submit_btn.click()
                    else:
                        doc_input.press("Enter")

                    page.wait_for_timeout(5000)

                    if collector:
                        collector.screenshot(page, "result")

                    result = self._parse_result(page, documento, doc_type)

                    if collector:
                        result_json = result.model_dump_json()
                        result.audit = collector.generate_pdf(page, result_json)

                    return result

                except SourceError:
                    raise
                except Exception as e:
                    raise SourceError(source_name, f"Query failed: {e}") from e

        def _parse_result(self, page, documento: str, doc_type: DocumentType) -> ConsejoProfesionalResult:
            body_text = page.inner_text("body")
            body_lower = body_text.lower()

            esta_registrado = any(phrase in body_lower for phrase in [
                "vigente", "activ", "registrad", "matrícula",
            ]) and not any(phrase in body_lower for phrase in [
                "no se encontr", "no registra", "no tiene",
            ])

            no_registrado = any(phrase in body_lower for phrase in [
                "no se encontr", "no registra", "no tiene", "sin resultado",
            ])

            result = ConsejoProfesionalResult(
                queried_at=datetime.now(),
                documento=documento,
                tipo_documento=doc_type.value,
                consejo=consejo_label,
                esta_registrado=esta_registrado and not no_registrado,
            )

            # Extract fields
            field_map = {
                "nombre": "nombre",
                "matrícula": "matricula",
                "matricula": "matricula",
                "estado": "estado_matricula",
                "profesión": "profesion",
                "profesion": "profesion",
                "especialidad": "especialidad",
                "universidad": "universidad",
                "fecha": "fecha_registro",
            }

            for line in body_text.split("\n"):
                stripped = line.strip()
                lower = stripped.lower()
                for label, field in field_map.items():
                    if label in lower and ":" in stripped:
                        value = stripped.split(":", 1)[1].strip()
                        if not getattr(result, field):
                            setattr(result, field, value)
                        break

            if no_registrado:
                result.mensaje = f"No registra matrícula en {consejo_label}"
            elif esta_registrado:
                result.mensaje = f"Matrícula {result.estado_matricula or 'registrada'} en {consejo_label}"

            return result

    # Give each class a unique name for registry
    ConsejoSource.__name__ = f"Consejo_{source_name.replace('.', '_')}Source"
    ConsejoSource.__qualname__ = ConsejoSource.__name__
    return ConsejoSource


# Register all professional councils
for _config in CONSEJOS:
    register(_make_consejo_source(_config))
