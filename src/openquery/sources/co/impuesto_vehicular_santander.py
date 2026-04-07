"""Santander vehicle tax source — IUVA SyC."""

from __future__ import annotations

from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://iuva.syc.com.co/santander"
SOURCE_NAME = "co.impuesto_vehicular_santander"


@register
class ImpuestoVehicularSantanderSource(ImpuestoVehicularBaseSource):
    """Query Santander vehicle tax portal (IUVA)."""

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Santander"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Santander (IUVA)",
            description="Vehicle tax debt query for Santander department via IUVA system",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )
