"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def runt_api_response() -> dict:
    """Sample RUNT API response with infoVehiculo wrapper."""
    return {
        "infoVehiculo": {
            "estadoAutomotor": "REGISTRADO",
            "marca": "TESLA",
            "linea": "MODELO Y",
            "modelo": "2026",
            "color": "GRIS GRAFITO",
            "vin": "5YJ3E1EA1PF000001",
            "numChasis": "5YJ3E1EA1PF000001",
            "tipoCombustible": "ELECTRICO",
            "tipoCarroceria": "SUV",
            "clase": "CAMIONETA",
            "puertas": "4",
            "pesoBruto": "1992",
            "pasajerosSentados": "5",
            "numeroEjes": "2",
            "gravamenes": "NO",
        }
    }
