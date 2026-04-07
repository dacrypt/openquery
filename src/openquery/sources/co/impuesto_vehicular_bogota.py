"""Bogotá vehicle tax source — SHD Consulta Pagos."""

from __future__ import annotations

from openquery.sources import register
from openquery.sources.base import DocumentType, SourceMeta
from openquery.sources.co._impuesto_vehicular_base import ImpuestoVehicularBaseSource

SOURCE_URL = "https://oficinavirtual.shd.gov.co/ConsultaPagos/ConsultaPagos.html"
SOURCE_NAME = "co.impuesto_vehicular_bogota"


@register
class ImpuestoVehicularBogotaSource(ImpuestoVehicularBaseSource):
    """Query Bogotá vehicle tax (SHD — Secretaría de Hacienda Distrital)."""

    _source_name = SOURCE_NAME
    _source_url = SOURCE_URL
    _departamento = "Bogotá D.C."
    _needs_documento = False

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name=SOURCE_NAME,
            display_name="Impuesto Vehicular — Bogotá (SHD)",
            description="Vehicle tax debt query for Bogotá D.C. via Secretaría de Hacienda Distrital",  # noqa: E501
            country="CO",
            url=SOURCE_URL,
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=True,
            rate_limit_rpm=5,
        )
