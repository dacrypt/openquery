"""RUNT source — Colombian vehicle registry.

Queries Colombia's RUNT API using Playwright to bypass Imperva WAF.

Flow:
1. Launch headless browser -> navigate to RUNT page (acquires WAF cookies)
2. Generate captcha via browser-context fetch
3. Solve captcha with OCR (or paid service)
4. POST auth query via browser-context fetch
5. Parse response into RuntResult model
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import CaptchaError, SourceError
from openquery.models.co.runt import RuntResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

RUNT_PAGE = "https://www.runt.gov.co/consultaCiudadana/#/consultaVehiculo"
BASE_URL = "https://runtproapi.runt.gov.co/CYRConsultaVehiculoMS"
CAPTCHA_URL = f"{BASE_URL}/captcha/libre-captcha/generar"
AUTH_URL = f"{BASE_URL}/auth"

MAX_RETRIES = 3


def _build_captcha_chain():
    """Build a captcha solver chain based on available backends.

    Primary: PaddleOCR PP-OCRv5 (~100% accuracy, ~130ms).
    Fallback chain: VotingSolver(EasyOCR+Tesseract) → HuggingFace → 2Captcha.
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

    # LLM visual fallback (uses ANTHROPIC_API_KEY or OPENAI_API_KEY)
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        try:
            from openquery.core.captcha import LLMCaptchaSolver

            solvers.append(LLMCaptchaSolver(max_chars=5))
        except Exception:
            pass

    # 2Captcha (paid, last resort)
    two_captcha_key = os.environ.get("TWO_CAPTCHA_API_KEY", "")
    if two_captcha_key:
        from openquery.core.captcha import TwoCaptchaSolver

        solvers.append(TwoCaptchaSolver(api_key=two_captcha_key))

    return ChainedSolver(solvers) if len(solvers) > 1 else solvers[0]


@register
class RuntSource(BaseSource):
    """Query Colombia's RUNT vehicle registry."""

    def __init__(self, timeout: float = 30.0, headless: bool = True) -> None:
        self._timeout = timeout
        self._headless = headless

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.runt",
            display_name="RUNT — Registro Único Nacional de Tránsito",
            description="Colombian vehicle registry with real-time SOAT, RTM, and ownership data",
            country="CO",
            url=RUNT_PAGE,
            supported_inputs=[DocumentType.VIN, DocumentType.PLATE, DocumentType.CEDULA],
            requires_captcha=True,
            requires_browser=True,
            rate_limit_rpm=5,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Query RUNT by VIN, plate, or owner cedula."""
        if input.document_type == DocumentType.VIN:
            return self._query_with_retries(
                tipo_consulta="2", campo="vin", valor=input.document_number,
                audit=input.audit,
            )
        elif input.document_type == DocumentType.PLATE:
            return self._query_with_retries(
                tipo_consulta="1", campo="placa", valor=input.document_number,
                audit=input.audit,
            )
        elif input.document_type == DocumentType.CEDULA:
            return self._query_with_retries(
                tipo_consulta="1", campo="documento", valor=input.document_number,
                tipo_documento=input.extra.get("tipo_documento", "C"),
                audit=input.audit,
            )
        else:
            raise SourceError("co.runt", f"Unsupported input type: {input.document_type}")

    def _query_with_retries(
        self, tipo_consulta: str, campo: str, valor: str, tipo_documento: str = "C",
        audit: bool = False,
    ) -> RuntResult:
        """Execute query with captcha retry logic."""
        from openquery.core.browser import BrowserManager

        browser = BrowserManager(headless=self._headless, timeout=self._timeout)
        solver = _build_captcha_chain()
        last_error: Exception | None = None
        collector = None

        if audit:
            from openquery.core.audit import AuditCollector
            collector = AuditCollector("co.runt", campo, valor)

        with browser.page(RUNT_PAGE, wait_until="networkidle") as page:
            if collector:
                collector.attach(page)

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    logger.info(
                        "RUNT attempt %d/%d for %s=%s", attempt, MAX_RETRIES, campo, valor,
                    )

                    # Step 1: Generate captcha
                    captcha_id, image_bytes = self._generate_captcha(page)

                    # Step 2: Solve captcha
                    captcha_text = solver.solve(image_bytes)
                    logger.info("Captcha solved: %s", captcha_text)

                    if collector:
                        collector.screenshot(page, f"captcha_attempt_{attempt}")

                    # Step 3: Execute query
                    data = self._execute_query(
                        page, tipo_consulta, campo, valor, captcha_text, captcha_id,
                        tipo_documento=tipo_documento,
                    )

                    # Step 4: Parse response
                    vin = valor if campo == "vin" else ""
                    result = self._parse_response(data, vin)

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
                    logger.warning("Attempt %d failed unexpectedly: %s", attempt, e, exc_info=True)

        raise SourceError("co.runt", f"All {MAX_RETRIES} attempts failed. Last error: {last_error}")

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
            raise SourceError("co.runt", f"No captcha ID in response: {result}")

        image_data = result.get("imagen", "")
        if not image_data:
            raise SourceError("co.runt", "No captcha image in response")

        # Decode base64 image
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(image_data)
        except Exception as e:
            raise SourceError("co.runt", f"Cannot decode captcha image: {e}") from e

        if len(image_bytes) < 100:
            raise SourceError("co.runt", f"Captcha image too small ({len(image_bytes)} bytes)")

        return captcha_id, image_bytes

    def _execute_query(
        self,
        page,
        tipo_consulta: str,
        campo: str,
        valor: str,
        captcha_text: str,
        captcha_id: str,
        tipo_documento: str = "C",
    ) -> dict:
        """POST auth query to RUNT API via browser fetch."""
        body = {
            "procedencia": "NACIONAL",
            "tipoConsulta": tipo_consulta,
            "placa": valor if campo == "placa" else None,
            "tipoDocumento": tipo_documento,
            "documento": valor if campo == "documento" else None,
            "vin": valor if campo == "vin" else None,
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
            raise CaptchaError("co.runt", f"Captcha verification failed ({status})")

        if status != 200:
            raise SourceError("co.runt", f"RUNT API returned {status}: {body_text[:200]}")

        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as e:
            raise SourceError("co.runt", f"Invalid JSON response: {e}") from e

        if isinstance(data, dict):
            error_msg = data.get("mensaje", data.get("message", ""))
            if error_msg and "captcha" in error_msg.lower():
                raise CaptchaError("co.runt", f"Captcha error: {error_msg}")
            if data.get("error") is True:
                desc = data.get("descripcionRespuesta", data.get("mensaje", "Unknown error"))
                raise SourceError("co.runt", f"RUNT error: {desc}")

        return data

    def _parse_response(self, data: dict, vin: str) -> RuntResult:
        """Parse RUNT API response into RuntResult model."""
        vehicle = data
        if "infoVehiculo" in data:
            vehicle = data["infoVehiculo"]
        elif "vehiculo" in data:
            vehicle = data["vehiculo"]

        def g(keys: list[str], default: str = "") -> str:
            for k in keys:
                val = vehicle.get(k)
                if val is not None:
                    return str(val).strip()
            return default

        def gi(keys: list[str], default: int = 0) -> int:
            val = g(keys, str(default))
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        def gb(keys: list[str], default: bool = False) -> bool:
            val = g(keys, "")
            if val.upper() in ("SI", "SÍ", "YES", "TRUE", "1"):
                return True
            if val.upper() in ("NO", "FALSE", "0"):
                return False
            return default

        return RuntResult(
            queried_at=datetime.now(),
            estado=g(["estadoAutomotor", "estado"]),
            placa=g(["placa", "placaActual"]),
            licencia_transito=g(["numLicencia", "licenciaTransito"]),
            id_automotor=gi(["idAutomotor"]),
            tarjeta_registro=g(["tarjetaRegistro"]),
            clase_vehiculo=g(["clase", "claseVehiculo"]),
            id_clase_vehiculo=gi(["idClaseVehiculo"]),
            clasificacion=g(["clasificacion"]),
            tipo_servicio=g(["tipoServicio"]),
            marca=g(["marca"]),
            linea=g(["linea"]),
            modelo_ano=g(["modelo"]),
            color=g(["color"]),
            numero_serie=g(["numSerie"]),
            numero_motor=g(["numMotor"]),
            numero_chasis=g(["numChasis"]),
            numero_vin=g(["vin"], vin),
            tipo_combustible=g(["tipoCombustible"]),
            tipo_carroceria=g(["tipoCarroceria"]),
            cilindraje=g(["cilindraje"], "0"),
            puertas=gi(["puertas"]),
            peso_bruto_kg=gi(["pesoBruto"]),
            capacidad_carga=g(["capacidadCarga"]),
            capacidad_pasajeros=gi(["pasajerosSentados"]),
            numero_ejes=gi(["numeroEjes"]),
            gravamenes=gb(["gravamenes"]),
            prendas=gb(["prendas"]),
            repotenciado=gb(["repotenciado"]),
            antiguo_clasico=gb(["antiguoClasico"]),
            vehiculo_ensenanza=gb(["vehiculoEnsenanza"]),
            seguridad_estado=gb(["seguridadEstado"]),
            regrabacion_motor=gb(["esRegrabadoMotor"]),
            num_regrabacion_motor=g(["numRegraMotor"]),
            regrabacion_chasis=gb(["esRegrabadoChasis"]),
            num_regrabacion_chasis=g(["numRegraChasis"]),
            regrabacion_serie=gb(["esRegrabadoSerie"]),
            num_regrabacion_serie=g(["numRegraSerie"]),
            regrabacion_vin=gb(["esRegrabadoVin"]),
            num_regrabacion_vin=g(["numRegraVin"]),
            # SOAT
            soat_vigente=gb(["soatVigente", "vigenciaSoat"]),
            soat_aseguradora=g(["aseguradora", "soatAseguradora", "nombreAseguradora"]),
            soat_vencimiento=g([
                "fechaVencimientoSoat", "soatFechaVencimiento", "vencimientoSoat",
            ]),
            # RTM (tecnicomecanica)
            tecnomecanica_vigente=gb(["rtmVigente", "vigenciaRTM", "tecnomecanicaVigente"]),
            tecnomecanica_vencimiento=g([
                "fechaVencimientoRTM", "rtmFechaVencimiento", "vencimientoRTM",
                "tecnomecanicaVencimiento",
            ]),
            # Registration
            fecha_matricula=g(["fechaMatricula"]),
            fecha_registro=g(["fechaRegistro"]),
            autoridad_transito=g(["organismoTransito"]),
            dias_matriculado=gi(["diasMatriculado"]) or None,
            importacion=gi(["importacion"]),
            fecha_expedicion_lt_importacion=g(["fechaExpedLTImportacion"]),
            fecha_vencimiento_lt_importacion=g(["fechaVenciLTImportacion"]),
            nombre_pais=g(["nombrePais"]),
            ver_valida_dian=gb(["verValidaDIAN"]),
            validacion_dian=g(["validacionDIAN"]),
            subpartida=g(["subpartida"]),
            no_identificacion=g(["noIdentificacion"]),
            mostrar_solicitudes=gb(["mostrarSolicitudes"]),
        )
