"""Boyacá vehicle tax source — SIVER."""

from __future__ import annotations

from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://vehiculos.boyaca.gov.co/siver-v-boyaca/redirect/"
SOURCE_NAME = "co.impuesto_vehicular_boyaca"


@register
class ImpuestoVehicularBoyacaSource(ImpuestoVehicularBaseSource):
    """Query Boyacá vehicle tax portal (SIVER)."""

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Boyacá"
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Boyacá (SIVER)",
            description="Vehicle tax debt query for Boyacá department via SIVER system",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )
