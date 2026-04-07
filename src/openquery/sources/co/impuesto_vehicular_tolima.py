"""Tolima vehicle tax source — SIVER."""

from __future__ import annotations

from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://aplicativosenlinea.net/sivervtolima/redirect/"
SOURCE_NAME = "co.impuesto_vehicular_tolima"


@register
class ImpuestoVehicularTolimaSource(ImpuestoVehicularBaseSource):
    """Query Tolima vehicle tax portal (SIVER)."""

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Tolima"
    _needs_documento = True

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Tolima (SIVER)",
            description="Vehicle tax debt query for Tolima department via SIVER system",
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )
