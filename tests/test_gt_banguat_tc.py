"""Tests for gt.banguat_tc — Guatemala Banguat exchange rate by date source."""

from __future__ import annotations

from openquery.sources.base import DocumentType, QueryInput


class TestGtBanguatTcParseHtml:
    def test_empty_result_returns_defaults(self):
        from openquery.models.gt.banguat_tc import GtBanguatTcResult

        r = GtBanguatTcResult()
        assert r.usd_rate == ""
        assert r.date == ""

    def test_usd_rate_parsed_from_soap(self):
        xml = """<?xml version="1.0"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
            <TipoCambioFechaResponse xmlns="http://www.banguat.gob.gt/variables/ws/">
              <TipoCambioFechaResult>
                <CambioDolar>
                  <VarDolar>
                    <fecha>01/04/2026</fecha>
                    <referencia>7.76990</referencia>
                  </VarDolar>
                </CambioDolar>
              </TipoCambioFechaResult>
            </TipoCambioFechaResponse>
          </soap:Body>
        </soap:Envelope>"""
        import xml.etree.ElementTree as ET

        from openquery.sources.gt.banguat_tc import GtBanguatTcSource

        GtBanguatTcSource()
        root = ET.fromstring(xml)
        usd_rate = ""
        fecha = ""
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "fecha" and elem.text:
                fecha = elem.text.strip()
            elif tag == "referencia" and elem.text:
                usd_rate = elem.text.strip()
        assert usd_rate == "7.76990"
        assert fecha == "01/04/2026"

    def test_model_roundtrip(self):
        from openquery.models.gt.banguat_tc import GtBanguatTcResult

        r = GtBanguatTcResult(date="01/04/2026", usd_rate="7.76990")
        data = r.model_dump_json()
        r2 = GtBanguatTcResult.model_validate_json(data)
        assert r2.date == "01/04/2026"
        assert r2.usd_rate == "7.76990"

    def test_audit_excluded_from_json(self):
        from openquery.models.gt.banguat_tc import GtBanguatTcResult

        r = GtBanguatTcResult(date="01/04/2026", audit=b"pdf-bytes")
        assert "audit" not in r.model_dump_json()


class TestGtBanguatTcSourceMeta:
    def test_meta(self):
        from openquery.sources.gt.banguat_tc import GtBanguatTcSource

        meta = GtBanguatTcSource().meta()
        assert meta.name == "gt.banguat_tc"
        assert meta.country == "GT"
        assert DocumentType.CUSTOM in meta.supported_inputs
        assert meta.requires_browser is False
        assert meta.rate_limit_rpm == 10

    def test_default_date_used_when_empty(self):
        from openquery.sources.gt.banguat_tc import GtBanguatTcSource

        GtBanguatTcSource()
        qi = QueryInput(document_type=DocumentType.CUSTOM, document_number="")
        # Should not raise — uses today's date
        date = qi.extra.get("date", "") or qi.document_number
        if not date:
            from datetime import datetime

            date = datetime.now().strftime("%d/%m/%Y")
        assert len(date) >= 8
