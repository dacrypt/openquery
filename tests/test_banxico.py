"""Unit tests for mx.banxico — Banco de México economic indicators source."""

from __future__ import annotations

from openquery.models.mx.banxico import BanxicoDataPoint, BanxicoResult
from openquery.sources.mx.banxico import BanxicoSource


class TestBanxicoResult:
    """Test BanxicoResult model."""

    def test_default_values(self):
        data = BanxicoResult()
        assert data.series_id == ""
        assert data.series_name == ""
        assert data.data_points == []
        assert data.details == {}
        assert data.audit is None

    def test_round_trip_json(self):
        data = BanxicoResult(
            series_id="SF43718",
            series_name="Tipo de cambio USD/MXN",
            data_points=[BanxicoDataPoint(date="2024-01-02", value="17.1234")],
            details={"idSerie": "SF43718"},
        )
        json_str = data.model_dump_json()
        restored = BanxicoResult.model_validate_json(json_str)
        assert restored.series_id == "SF43718"
        assert restored.series_name == "Tipo de cambio USD/MXN"
        assert len(restored.data_points) == 1
        assert restored.data_points[0].date == "2024-01-02"
        assert restored.data_points[0].value == "17.1234"

    def test_audit_excluded_from_json(self):
        data = BanxicoResult(series_id="SF43718", audit={"evidence": "pdf"})
        json_str = data.model_dump_json()
        assert "audit" not in json_str
        assert data.audit == {"evidence": "pdf"}


class TestBanxicoDataPoint:
    """Test BanxicoDataPoint model."""

    def test_default_values(self):
        dp = BanxicoDataPoint()
        assert dp.date == ""
        assert dp.value == ""

    def test_with_values(self):
        dp = BanxicoDataPoint(date="2024-03-01", value="16.9532")
        assert dp.date == "2024-03-01"
        assert dp.value == "16.9532"


class TestBanxicoSourceMeta:
    """Test BanxicoSource metadata."""

    def test_meta_name(self):
        source = BanxicoSource()
        assert source.meta().name == "mx.banxico"

    def test_meta_country(self):
        source = BanxicoSource()
        assert source.meta().country == "MX"

    def test_meta_rate_limit(self):
        source = BanxicoSource()
        assert source.meta().rate_limit_rpm == 20

    def test_meta_requires_browser(self):
        source = BanxicoSource()
        assert source.meta().requires_browser is False

    def test_meta_requires_captcha(self):
        source = BanxicoSource()
        assert source.meta().requires_captcha is False

    def test_default_timeout(self):
        source = BanxicoSource()
        assert source._timeout == 30.0


class TestParseResponse:
    """Test _parse_response parsing logic."""

    def test_parse_valid_response(self):
        source = BanxicoSource()
        data = {
            "bmx": {
                "series": [
                    {
                        "idSerie": "SF43718",
                        "titulo": "Tipo de cambio USD/MXN",
                        "datos": [
                            {"fecha": "02/01/2024", "dato": "17.1234"},
                            {"fecha": "03/01/2024", "dato": "17.2000"},
                        ],
                    }
                ]
            }
        }
        result = source._parse_response("SF43718", data)
        assert result.series_id == "SF43718"
        assert result.series_name == "Tipo de cambio USD/MXN"
        assert len(result.data_points) == 2
        assert result.data_points[0].date == "02/01/2024"
        assert result.data_points[0].value == "17.1234"

    def test_parse_empty_response(self):
        source = BanxicoSource()
        result = source._parse_response("SF99999", {"bmx": {"series": []}})
        assert result.series_id == "SF99999"
        assert result.data_points == []

    def test_parse_missing_bmx_key(self):
        source = BanxicoSource()
        result = source._parse_response("SF43718", {})
        assert result.series_id == "SF43718"
        assert result.data_points == []
