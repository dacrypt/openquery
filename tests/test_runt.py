"""Unit tests for RUNT source."""

from __future__ import annotations

import io
import json as _json
from unittest.mock import MagicMock

import pytest

from openquery.exceptions import CaptchaError, SourceError
from openquery.models.co.runt import RuntResult
from openquery.sources.co.runt import RuntSource


class TestSolveCaptcha:
    """Test captcha solving."""

    def test_solve_returns_alphanumeric(self):
        from PIL import Image, ImageDraw, ImageFont

        # Create a large, clear image that OCR can read with any font
        img = Image.new("RGB", (400, 80), color="white")
        draw = ImageDraw.Draw(img)
        # Try system fonts across platforms, fall back to default at large size
        font = None
        for path in [
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Ubuntu
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # Fedora
        ]:
            try:
                font = ImageFont.truetype(path, 48)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default(size=48)
        draw.text((30, 10), "AB12C", fill="black", font=font)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        from openquery.core.captcha import OCRSolver

        solver = OCRSolver(max_chars=5)
        result = solver.solve(image_bytes)

        assert result.isalnum(), f"Expected alphanumeric, got: '{result}'"
        assert len(result) <= 5

    def test_solve_empty_image_raises(self):
        from PIL import Image

        img = Image.new("RGB", (50, 20), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        from openquery.core.captcha import OCRSolver

        solver = OCRSolver(max_chars=5)
        with pytest.raises(CaptchaError, match="too few characters"):
            solver.solve(buf.getvalue())


class TestExecuteQuery:
    """Test _execute_query with mocked Playwright page."""

    def test_query_success(self, runt_api_response):
        source = RuntSource()
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {
            "status": 200,
            "body": _json.dumps(runt_api_response),
        }

        result = source._execute_query(
            mock_page,
            "2",
            "vin",
            "5YJ3E1EA1PF000001",
            "abc12",
            "test-uuid",
        )
        assert result["infoVehiculo"]["marca"] == "TESLA"

    def test_query_captcha_fail_raises(self):
        source = RuntSource()
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {
            "status": 401,
            "body": "Unauthorized",
        }

        with pytest.raises(CaptchaError, match="Captcha verification failed"):
            source._execute_query(mock_page, "2", "vin", "VIN", "bad", "uuid")

    def test_query_server_error_raises(self):
        source = RuntSource()
        mock_page = MagicMock()
        mock_page.evaluate.return_value = {
            "status": 500,
            "body": "Internal Server Error",
        }

        with pytest.raises(SourceError, match="500"):
            source._execute_query(mock_page, "2", "vin", "VIN", "abc", "uuid")


class TestParseResponse:
    """Test response parsing into RuntResult."""

    def test_parse_with_info_vehiculo(self, runt_api_response):
        source = RuntSource()
        result = source._parse_response(runt_api_response, "5YJ3E1EA1PF000001")

        assert isinstance(result, RuntResult)
        assert result.estado == "REGISTRADO"
        assert result.marca == "TESLA"
        assert result.linea == "MODELO Y"
        assert result.modelo_ano == "2026"
        assert result.color == "GRIS GRAFITO"
        assert result.tipo_combustible == "ELECTRICO"
        assert result.tipo_carroceria == "SUV"
        assert result.clase_vehiculo == "CAMIONETA"
        assert result.puertas == 4
        assert result.peso_bruto_kg == 1992
        assert result.capacidad_pasajeros == 5
        assert result.numero_ejes == 2
        assert result.gravamenes is False

    def test_parse_flat_response(self):
        source = RuntSource()
        data = {
            "estadoAutomotor": "MATRICULADO",
            "marca": "CHEVROLET",
            "placa": "ABC123",
        }

        result = source._parse_response(data, "")
        assert result.estado == "MATRICULADO"
        assert result.marca == "CHEVROLET"
        assert result.placa == "ABC123"


class TestRuntSourceMeta:
    """Test source metadata."""

    def test_meta(self):
        source = RuntSource()
        meta = source.meta()
        assert meta.name == "co.runt"
        assert meta.country == "CO"
        assert meta.requires_captcha is True
