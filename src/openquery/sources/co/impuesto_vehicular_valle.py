"""Valle del Cauca vehicle tax source."""

from __future__ import annotations

from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://www.vehiculosvalle.com.co/"
SOURCE_NAME = "co.impuesto_vehicular_valle"


@register
class ImpuestoVehicularValleSource(ImpuestoVehicularBaseSource):
    """Query Valle del Cauca vehicle tax portal."""

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Valle del Cauca"
    _needs_documento = True

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Valle del Cauca",
            description="Vehicle tax debt query for Valle del Cauca department",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )
