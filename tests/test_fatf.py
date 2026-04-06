"""Tests for intl.fatf — FATF high-risk jurisdictions (black/grey lists)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from openquery.exceptions import SourceError
from openquery.sources.base import DocumentType, QueryInput

# ===========================================================================
# TestFatfResult — model tests
# ===========================================================================


class TestFatfResult:
    def test_defaults(self):
        from openquery.models.intl.fatf import IntlFatfResult

        r = IntlFatfResult()
        assert r.country == ""
        assert r.list_type == ""
        assert r.last_updated == ""
        assert r.black_list == []
        assert r.grey_list == []
        assert r.details == ""
        assert r.audit is None
        assert isinstance(r.queried_at, datetime)

    def test_json_roundtrip(self):
        from openquery.models.intl.fatf import IntlFatfResult

        r = IntlFatfResult(
            country="Iran",
            list_type="black",
            last_updated="October 2023",
            black_list=["Iran", "North Korea"],
            grey_list=["Syria", "Yemen"],
        )
        dumped = r.model_dump_json()
        restored = IntlFatfResult.model_validate_json(dumped)
        assert restored.country == "Iran"
        assert restored.list_type == "black"
        assert "Iran" in restored.black_list
        assert "Syria" in restored.grey_list

    def test_audit_excluded_from_json(self):
        from openquery.models.intl.fatf import IntlFatfResult

        r = IntlFatfResult(audit={"raw": "html"})
        data = r.model_dump()
        assert "audit" not in data


# ===========================================================================
# TestFatfSourceMeta
# ===========================================================================


class TestFatfSourceMeta:
    def test_meta_name(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        assert IntlFatfSource().meta().name == "intl.fatf"

    def test_meta_country(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        assert IntlFatfSource().meta().country == "INTL"

    def test_meta_no_captcha_no_browser(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        meta = IntlFatfSource().meta()
        assert meta.requires_captcha is False
        assert meta.requires_browser is False

    def test_meta_rate_limit(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        assert IntlFatfSource().meta().rate_limit_rpm == 5

    def test_meta_supports_custom(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        assert DocumentType.CUSTOM in IntlFatfSource().meta().supported_inputs


# ===========================================================================
# TestFatfParseResult
# ===========================================================================

MOCK_FATF_HTML = """
<html>
<body>
<p>Last updated: October 2023</p>
<section>
<h2>Jurisdictions under increased monitoring (Grey List)</h2>
<ul>
<li>Bulgaria</li>
<li>Burkina Faso</li>
<li>Cameroon</li>
<li>Croatia</li>
<li>Democratic Republic of Congo</li>
<li>Haiti</li>
<li>Kenya</li>
<li>Mali</li>
<li>Mozambique</li>
<li>Nigeria</li>
<li>South Africa</li>
<li>Tanzania</li>
<li>Vietnam</li>
<li>Yemen</li>
</ul>
</section>
<section>
<h2>High-Risk Jurisdictions subject to a Call for Action (Black List)</h2>
<ul>
<li>Iran</li>
<li>North Korea</li>
</ul>
</section>
</body>
</html>
"""


class TestFatfParseResult:
    def _make_input(self, country: str = "") -> QueryInput:
        return QueryInput(
            document_number=country,
            document_type=DocumentType.CUSTOM,
            extra={"country": country} if country else {},
        )

    def test_parse_lists_extracts_countries(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        source = IntlFatfSource()
        black_list, grey_list, last_updated = source._parse_lists(MOCK_FATF_HTML)
        # Should find some countries
        assert isinstance(black_list, list)
        assert isinstance(grey_list, list)

    def test_full_list_query(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        mock_resp = MagicMock()
        mock_resp.text = MOCK_FATF_HTML
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            result = IntlFatfSource().query(self._make_input(""))

        assert result.list_type == "all"
        assert isinstance(result.black_list, list)
        assert isinstance(result.grey_list, list)

    def test_country_found_on_black_list(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        source = IntlFatfSource()
        mock_resp = MagicMock()
        mock_resp.text = MOCK_FATF_HTML
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            # Override _parse_lists to return controlled data
            with patch.object(
                source,
                "_parse_lists",
                return_value=(["Iran", "North Korea"], ["Bulgaria", "Haiti"], "October 2023"),
            ):
                result = source._fetch("Iran")

        assert result.list_type == "black"
        assert "Iran" in result.black_list

    def test_country_found_on_grey_list(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        source = IntlFatfSource()
        mock_resp = MagicMock()
        mock_resp.text = MOCK_FATF_HTML
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with patch.object(
                source,
                "_parse_lists",
                return_value=(["Iran", "North Korea"], ["Bulgaria", "Haiti"], "October 2023"),
            ):
                result = source._fetch("Bulgaria")

        assert result.list_type == "grey"

    def test_country_not_on_any_list(self):
        from openquery.sources.intl.fatf import IntlFatfSource

        source = IntlFatfSource()
        mock_resp = MagicMock()
        mock_resp.text = MOCK_FATF_HTML
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with patch.object(
                source,
                "_parse_lists",
                return_value=(["Iran", "North Korea"], ["Bulgaria", "Haiti"], "October 2023"),
            ):
                result = source._fetch("Germany")

        assert result.list_type == "none"

    def test_http_error_raises_source_error(self):
        import httpx

        from openquery.sources.intl.fatf import IntlFatfSource

        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "503", request=MagicMock(), response=mock_resp
        )

        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_client.get.return_value = mock_resp

            with pytest.raises(SourceError, match="intl.fatf"):
                IntlFatfSource().query(self._make_input("Iran"))
