"""Meta vehicle tax source."""

from __future__ import annotations

from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://impuestovehicular.meta.gov.co/"
SOURCE_NAME = "co.impuesto_vehicular_meta"


@register
class ImpuestoVehicularMetaSource(ImpuestoVehicularBaseSource):
    """Query Meta vehicle tax portal."""

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Meta"
    _needs_documento = True

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Meta",
            description="Vehicle tax debt query for Meta department",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )
