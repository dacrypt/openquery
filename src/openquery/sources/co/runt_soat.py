"""RUNT SOAT source — Colombian mandatory vehicle insurance status.

Queries RUNT for SOAT (Seguro Obligatorio de Accidentes de Transito)
status by vehicle plate number.

Flow:
1. Launch headless browser -> navigate to RUNT page (acquires WAF cookies)
2. Generate captcha via browser-context fetch
3. Solve captcha with OCR
4. POST query via browser-context fetch
5. Parse SOAT data from response

Source: https://ciudadano.runt.gov.co/
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import CaptchaError, SourceError
from openquery.models.co.runt_soat import RuntSoatResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RUNT_PAGE = "https://portalpublico.runt.gov.co/#/consulta-vehiculo/consulta/consulta-ciudadana"
BASE_URL = "https://runtproapi.runt.gov.co/CYRConsultaVehiculoMS"
CAPTCHA_URL = f"{BASE_URL}/captcha/libre-captcha/generar"
AUTH_URL = f"{BASE_URL}/auth"

MAX_RETRIES = 3


def _build_captcha_chain():
    """Build a captcha solver chain based on available backends.

    Primary: PaddleOCR PP-OCRv5 (~100% accuracy, ~130ms).
    Fallback chain: VotingSolver(EasyOCR+Tesseract) -> HuggingFace -> 2Captcha.
    Degrades gracefully based on what's installed.
    """
    import os

    from openquery.core.captcha import ChainedSolver, OCRSolver

    solvers = []

    # PaddleOCR (best accuracy ~100%, needs paddleocr+paddlepaddle installed)
    try:
        from openquery.core.captcha import PaddleOCRSolver

        solvers.append(PaddleOCRSolver(max_chars=5))
    except Exception:
        pass

    # Voting (EasyOCR + Tesseract, ~90% combined)
    try:
        from openquery.core.captcha import EasyOCRSolver, VotingSolver

        solvers.append(VotingSolver([EasyOCRSolver(max_chars=5), OCRSolver(max_chars=5)]))
    except Exception:
        # Tesseract alone as minimum fallback
        solvers.append(OCRSolver(max_chars=5))

    if not solvers:
        solvers.append(OCRSolver(max_chars=5))

    # HuggingFace OCR (optional, needs HF_TOKEN)
    if os.environ.get("HF_TOKEN"):
        try:
            from openquery.core.captcha import HuggingFaceOCRSolver

            solvers.append(HuggingFaceOCRSolver(max_chars=5))
        except Exception:
            pass

    # 2Captcha (paid, last resort)
    two_captcha_key = os.environ.get("TWO_CAPTCHA_API_KEY", "")
    if two_captcha_key:
        from openquery.core.captcha import TwoCaptchaSolver

        solvers.append(TwoCaptchaSolver(api_key=two_captcha_key))

    return ChainedSolver(solvers) if len(solvers) > 1 else solvers[0]


@register
class RuntSoatSource(BaseSource):
    """Query Colombian SOAT status from RUNT."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.runt_soat",
            display_name="RUNT \u2014 Estado del SOAT",
            description="Colombian mandatory vehicle insurance (SOAT) status from RUNT",
            country="CO",
            url=RUNT_PAGE,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query SOAT status by plate number."""
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "co.runt_soat",
                f"Unsupported input type: {input.document_type}. Use plate.",
            )
        return self._query_with_retries(input.document_number, audit=input.audit)

    def _query_with_retries(self, placa: str, audit: bool = False) -> RuntSoatResult:
        """Execute query with captcha retry logic."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        solver = _build_captcha_chain()
        last_error: Exception | None = None
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.runt_soat", "placa", placa)

        with browser.page(RUNT_PAGE, wait_until="networkidle") as page:
            if collector:
                collector.attach(page)

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    logger.info(
                        "RUNT SOAT attempt %d/%d for placa=%s",
                        attempt, MAX_RETRIES, placa,
                    )

                    # Step 1: Generate captcha
                    captcha_id, image_bytes = self._generate_captcha(page)

                    # Step 2: Solve captcha
                    captcha_text = solver.solve(image_bytes)
                    logger.info("Captcha solved: %s", captcha_text)

                    if collector:
                        collector.screenshot(page, f"captcha_attempt_{attempt}")

                    # Step 3: Execute query
                    data = self._execute_query(page, placa, captcha_text, captcha_id)

                    # Step 4: Parse SOAT data from response
                    result = self._parse_response(data, placa)

                    if collector:
                        collector.screenshot(page, "result")
                        result_json = result.model_dump_json()
                        result.audit = collector.generate_pdf(page, result_json)

                    return result

                except (SourceError, CaptchaError) as e:
                    last_error = e
                    logger.warning("Attempt %d failed: %s", attempt, e)
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "Attempt %d failed unexpectedly: %s", attempt, e, exc_info=True,
                    )

        raise SourceError(
            "co.runt_soat",
            f"All {MAX_RETRIES} attempts failed. Last error: {last_error}",
        )

    def _generate_captcha(self, page) -> tuple[str, bytes]:
        """Generate a captcha via browser-context fetch."""
        result = page.evaluate(f"""async () => {{
            const r = await fetch('{CAPTCHA_URL}');
            const data = await r.json();
            return {{
                id: data.id || data.idLibreCaptcha || '',
                imagen: data.imagen || data.image || data.captcha || '',
                error: data.error || false,
            }};
        }}""")

        captcha_id = result.get("id", "")
        if not captcha_id:
            raise SourceError("co.runt_soat", f"No captcha ID in response: {result}")

        image_data = result.get("imagen", "")
        if not image_data:
            raise SourceError("co.runt_soat", "No captcha image in response")

        # Decode base64 image
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            raise SourceError("co.runt_soat", f"Cannot decode captcha image: {e}") from e

        if len(image_bytes) < 100:
            raise SourceError(
                "co.runt_soat", f"Captcha image too small ({len(image_bytes)} bytes)",
            )

        return captcha_id, image_bytes

    def _execute_query(
        self, page, placa: str, captcha_text: str, captcha_id: str,
    ) -> dict:
        """POST auth query to RUNT API via browser fetch."""
        body = {
            "procedencia": "NACIONAL",
            "tipoConsulta": "1",
            "placa": placa,
            "tipoDocumento": None,
            "documento": None,
            "vin": None,
            "soat": None,
            "aseguradora": "",
            "rtm": None,
            "reCaptcha": None,
            "captcha": captcha_text,
            "valueCaptchaEncripted": "",
            "idLibreCaptcha": captcha_id,
            "verBannerSoat": True,
            "configuracion": {
                "tiempoInactividad": "900",
                "tiempoCuentaRegresiva": "10",
            },
        }

        body_json = json.dumps(body)

        result = page.evaluate(f"""async () => {{
            const r = await fetch('{AUTH_URL}', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: {json.dumps(body_json)},
            }});
            const text = await r.text();
            return {{ status: r.status, body: text }};
        }}""")

        status = result.get("status", 0)
        body_text = result.get("body", "")

        if status in (401, 403):
            raise CaptchaError("co.runt_soat", f"Captcha verification failed ({status})")

        if status != 200:
            raise SourceError(
                "co.runt_soat", f"RUNT API returned {status}: {body_text[:200]}",
            )

        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as e:
            raise SourceError("co.runt_soat", f"Invalid JSON response: {e}") from e

        if isinstance(data, dict):
            error_msg = data.get("mensaje", data.get("message", ""))
            if error_msg and "captcha" in error_msg.lower():
                raise CaptchaError("co.runt_soat", f"Captcha error: {error_msg}")
            if data.get("error") is True:
                desc = data.get(
                    "descripcionRespuesta", data.get("mensaje", "Unknown error"),
                )
                if "no corresponden" in desc.lower() or "no se encontr" in desc.lower():
                    logger.info("RUNT SOAT returned no matching data: %s", desc)
                else:
                    raise SourceError("co.runt_soat", f"RUNT error: {desc}")

        return data

    def _parse_response(self, data: dict, placa: str) -> RuntSoatResult:
        """Parse RUNT API response extracting SOAT-specific fields."""
        vehicle = data
        if "infoVehiculo" in data:
            vehicle = data["infoVehiculo"] or {}
        elif "vehiculo" in data:
            vehicle = data["vehiculo"] or {}

        def g(keys: list[str], default: str = "") -> str:
            for k in keys:
                val = vehicle.get(k)
                if val is not None:
                    return str(val).strip()
            return default

        soat_vigente = g(["soatVigente", "vigenciaSoat"]).upper() in (
            "SI", "S\u00cd", "YES", "TRUE", "1",
        )
        aseguradora = g(["aseguradora", "soatAseguradora", "nombreAseguradora"])
        numero_poliza = g(["polizaSoat", "numPolizaSoat", "poliza"])
        fecha_inicio = g(["fechaInicioSoat", "soatFechaInicio"])
        fecha_vencimiento = g([
            "fechaVencimientoSoat", "soatFechaVencimiento", "vencimientoSoat",
        ])
        estado = "Vigente" if soat_vigente else "Vencido"
        clase_vehiculo = g(["clase", "claseVehiculo"])

        mensaje = f"SOAT {placa}: {estado}"
        if aseguradora:
            mensaje += f" ({aseguradora})"

        return RuntSoatResult(
            queried_at=datetime.now(),
            placa=placa,
            tiene_soat=soat_vigente,
            aseguradora=aseguradora,
            numero_poliza=numero_poliza,
            fecha_inicio=fecha_inicio,
            fecha_vencimiento=fecha_vencimiento,
            estado=estado,
            clase_vehiculo=clase_vehiculo,
            mensaje=mensaje,
        )
