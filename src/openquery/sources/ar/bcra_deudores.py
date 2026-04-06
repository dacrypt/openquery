"""BCRA Central de Deudores source — Argentine credit report.

Queries BCRA's public REST API for credit/debt information by CUIT/CUIL.
Free API, no authentication, no CAPTCHA.

API: https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas/{identificacion}
"""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.ar.bcra_deudores import BcraDebt, BcraDeudoresResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

API_BASE = "https://api.bcra.gob.ar/centraldedeudores/v1.0"


@register
class BcraDeudoresSource(BaseSource):
    """Query Argentine BCRA Central de Deudores by CUIT/CUIL."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="ar.bcra_deudores",
            display_name="BCRA — Central de Deudores",
            description=(
                "Argentine credit report: debt situations, financing amounts, and 24-month history"
                " (BCRA public API)"
            ),
            country="AR",
            url=API_BASE,
            supported_inputs=[DocumentType.CUSTOM],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=20,
        )

    def query(self, input: QueryInput) -> BaseModel:
        identificacion = input.extra.get("cuit", "") or input.document_number
        if not identificacion:
            raise SourceError(
                "ar.bcra_deudores", "CUIT/CUIL is required (pass via extra.cuit or document_number)"
            )
        identificacion = identificacion.replace("-", "").replace(".", "")
        return self._query(identificacion)

    def _query(self, identificacion: str) -> BcraDeudoresResult:
        import httpx

        try:
            url = f"{API_BASE}/Deudas/{identificacion}"
            logger.info("Querying BCRA Central de Deudores: %s", identificacion)

            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url)
                if resp.status_code == 404:
                    # No debts found — return empty result
                    return BcraDeudoresResult(
                        queried_at=datetime.now(),
                        identificacion=identificacion,
                    )
                resp.raise_for_status()
                data = resp.json()

            return self._parse_response(identificacion, data)

        except httpx.HTTPStatusError as e:
            raise SourceError(
                "ar.bcra_deudores", f"API returned HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise SourceError("ar.bcra_deudores", f"Request failed: {e}") from e
        except SourceError:
            raise
        except Exception as e:
            raise SourceError("ar.bcra_deudores", f"Query failed: {e}") from e

    def _parse_response(self, identificacion: str, data: dict) -> BcraDeudoresResult:
        """Parse the BCRA API response into BcraDeudoresResult."""
        results_data = data.get("results", data)

        denominacion = results_data.get("denominacion", "")
        periodos = results_data.get("periodos", [])

        debts: list[BcraDebt] = []
        worst_situation = 0

        for periodo in periodos:
            period_str = str(periodo.get("periodo", ""))
            entidades = periodo.get("entidades", [])
            for entidad in entidades:
                situation = int(entidad.get("situacion", 0))
                debt = BcraDebt(
                    entity=str(entidad.get("entidad", "")),
                    situation=situation,
                    amount=float(entidad.get("monto", 0) or 0),
                    period=period_str,
                )
                debts.append(debt)
                if situation > worst_situation:
                    worst_situation = situation

        return BcraDeudoresResult(
            queried_at=datetime.now(),
            identificacion=identificacion,
            denominacion=denominacion,
            total_debts=len(debts),
            debts=debts,
            periods_checked=len(periodos),
            worst_situation=worst_situation,
            details=results_data if isinstance(results_data, dict) else {},
        )
