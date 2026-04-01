"""RNE source — Registro Nacional de Números Excluidos (Do Not Call).

Queries the CRC (Comisión de Regulación de Comunicaciones) API to check
if a phone number or email is registered in the Do Not Call list.

Flow:
1. Authenticate with CRC using user credentials to obtain JWT token
2. POST query with phone number or email to the validation endpoint
3. Parse JSON response

Source: https://tramitescrcom.gov.co/tramites/publico/rne/loginRNE.xhtml
API: https://tramitescrcom.gov.co/excluidosback/consultaMasiva/validarExcluidos
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.rne import RneResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

LOGIN_URL = "https://tramitescrcom.gov.co/excluidosback/auth/login"
VALIDATE_URL = "https://tramitescrcom.gov.co/excluidosback/consultaMasiva/validarExcluidos"


@register
class RneSource(BaseSource):
    """Query Colombian Do Not Call registry (RNE / CRC)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.rne",
            display_name="RNE — Registro Números Excluidos",
            description="Colombian Do Not Call registry (Ley 2300/2023) — check if a phone/email is excluded",
            country="CO",
            url="https://tramitescrcom.gov.co/tramites/publico/rne/loginRNE.xhtml",
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=10,
        )

    def query(self, input: QueryInput) -> BaseModel:
        telefono = input.extra.get("telefono", "").strip()
        email = input.extra.get("email", "").strip()
        usuario = input.extra.get("usuario", "").strip()
        password = input.extra.get("password", "").strip()

        if not telefono and not email:
            raise SourceError("co.rne", "Must provide extra['telefono'] or extra['email']")
        if not usuario or not password:
            raise SourceError("co.rne", "Must provide extra['usuario'] and extra['password'] (CRC credentials)")

        consulta = telefono or email
        tipo = "TEL" if telefono else "COR"
        return self._query(consulta, tipo, usuario, password)

    def _query(self, consulta: str, tipo: str, usuario: str, password: str) -> RneResult:
        from datetime import datetime

        try:
            with httpx.Client(timeout=self._timeout) as client:
                # Step 1: Authenticate to get JWT
                login_resp = client.post(LOGIN_URL, json={
                    "usuario": usuario,
                    "contrasena": password,
                })
                login_resp.raise_for_status()
                login_data = login_resp.json()

                token = login_data.get("token", "")
                if not token:
                    raise SourceError("co.rne", "Authentication failed — no token received")

                # Step 2: Query the RNE
                headers = {"Authorization": f"Bearer {token}"}
                validate_resp = client.post(
                    VALIDATE_URL,
                    json={"datos": [{"tipo": tipo, "valor": consulta}]},
                    headers=headers,
                )
                validate_resp.raise_for_status()
                data = validate_resp.json()

            # Parse response
            resultados = data if isinstance(data, list) else data.get("resultados", [data])
            esta_excluido = False
            fecha_registro = ""

            for item in resultados:
                if isinstance(item, dict):
                    excluido = item.get("excluido", item.get("esta_excluido", False))
                    if excluido in (True, "SI", "S", "true", "1"):
                        esta_excluido = True
                    fecha_registro = str(item.get("fechaRegistro", item.get("fecha_registro", "")))

            tipo_label = "telefono" if tipo == "TEL" else "email"
            if esta_excluido:
                mensaje = f"El {tipo_label} {consulta} está registrado en la lista de excluidos"
            else:
                mensaje = f"El {tipo_label} {consulta} no está en la lista de excluidos"

            return RneResult(
                queried_at=datetime.now(),
                consulta=consulta,
                tipo_consulta=tipo_label,
                esta_excluido=esta_excluido,
                fecha_registro=fecha_registro,
                mensaje=mensaje,
            )

        except SourceError:
            raise
        except httpx.HTTPStatusError as e:
            msg = f"API returned HTTP {e.response.status_code}"
            raise SourceError("co.rne", msg) from e
        except httpx.RequestError as e:
            raise SourceError("co.rne", f"Request failed: {e}") from e
        except Exception as e:
            raise SourceError("co.rne", f"Query failed: {e}") from e
