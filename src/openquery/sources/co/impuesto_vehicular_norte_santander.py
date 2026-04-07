"""Norte de Santander vehicle tax source."""

from __future__ import annotations

from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://vehiculos.nortedesantander.gov.co/"
SOURCE_NAME = "co.impuesto_vehicular_norte_santander"


@register
class ImpuestoVehicularNorteSantanderSource(ImpuestoVehicularBaseSource):
    """Query Norte de Santander vehicle tax portal."""

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Norte de Santander"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Norte de Santander",
            description="Vehicle tax debt query for Norte de Santander department",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )
