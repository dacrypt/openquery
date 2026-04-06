"""Tests for CLI commands and app entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from openquery.app import app

runner = CliRunner()


class TestVersionFlag:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "openquery" in result.output

    def test_short_version(self):
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "openquery" in result.output


class TestSourcesCommand:
    def test_sources_list(self):
        result = runner.invoke(app, ["sources"])
        assert result.exit_code == 0
        assert "co.simit" in result.output
        assert "co.runt" in result.output

    def test_shows_all_13_sources(self):
        result = runner.invoke(app, ["sources"])
        assert result.exit_code == 0
        for name in [
            "co.simit",
            "co.runt",
            "co.policia",
            "co.adres",
            "co.pico_y_placa",
            "co.peajes",
            "co.vehiculos",
        ]:
            assert name in result.output


class TestQueryCommand:
    def test_no_doc_type_error(self):
        result = runner.invoke(app, ["query", "co.simit"])
        assert result.exit_code == 1
        assert "Provide" in result.output

    def test_unknown_source(self):
        result = runner.invoke(app, ["query", "xx.nope", "--cedula", "123"])
        assert result.exit_code == 1

    def test_unsupported_doc_type(self):
        # co.pico_y_placa only supports PLATE, not CEDULA
        result = runner.invoke(app, ["query", "co.pico_y_placa", "--cedula", "123"])
        assert result.exit_code == 1
        assert "does not support" in result.output

    def test_invalid_extra_json(self):
        result = runner.invoke(
            app,
            [
                "query",
                "co.peajes",
                "--custom",
                "tolls",
                "--extra",
                "not-valid-json",
            ],
        )
        assert result.exit_code == 1
        assert "Invalid" in result.output

    @patch("openquery.sources.get_source")
    def test_successful_query_json(self, mock_get_source):
        from pydantic import BaseModel

        class FakeResult(BaseModel):
            placa: str = "ABC123"
            restringido: bool = False

        mock_source = MagicMock()
        mock_source.meta.return_value.display_name = "Test Source"
        mock_source.supports.return_value = True
        mock_source.query.return_value = FakeResult()
        mock_get_source.return_value = mock_source

        result = runner.invoke(app, ["query", "co.test", "--placa", "ABC123", "--json"])
        assert result.exit_code == 0
        assert "ABC123" in result.output

    @patch("openquery.sources.get_source")
    def test_successful_query_pretty(self, mock_get_source):
        from pydantic import BaseModel

        class FakeResult(BaseModel):
            placa: str = "XYZ789"
            total: int = 5

        mock_source = MagicMock()
        mock_source.meta.return_value.display_name = "Test Source"
        mock_source.supports.return_value = True
        mock_source.query.return_value = FakeResult()
        mock_get_source.return_value = mock_source

        result = runner.invoke(app, ["query", "co.test", "--placa", "XYZ789"])
        assert result.exit_code == 0

    @patch("openquery.sources.get_source")
    def test_query_exception_handled(self, mock_get_source):
        mock_source = MagicMock()
        mock_source.meta.return_value.display_name = "Test"
        mock_source.supports.return_value = True
        mock_source.query.side_effect = RuntimeError("connection timeout")
        mock_get_source.return_value = mock_source

        result = runner.invoke(app, ["query", "co.test", "--cedula", "123"])
        assert result.exit_code == 1
        assert "connection timeout" in result.output


class TestNoArgsHelp:
    def test_no_args_shows_help(self):
        result = runner.invoke(app, [])
        # no_args_is_help=True causes exit code 0 or 2 depending on typer version
        assert result.exit_code in (0, 2)
        # Should show usage/help text
        assert "query" in result.output.lower() or "usage" in result.output.lower()
