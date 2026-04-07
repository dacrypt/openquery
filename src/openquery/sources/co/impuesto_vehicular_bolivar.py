"""Bolívar vehicle tax source."""

from __future__ import annotations

from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://impuestos.bolivar.gov.co/"
SOURCE_NAME = "co.impuesto_vehicular_bolivar"


@register
class ImpuestoVehicularBolivarSource(ImpuestoVehicularBaseSource):
    """Query Bolívar vehicle tax portal."""

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Bolívar"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Bolívar",
            description="Vehicle tax debt query for Bolívar department",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )
