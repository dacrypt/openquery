"""Pico y Placa source — Colombian driving restrictions.

Pure logic source (no scraping). Determines whether a vehicle plate
is restricted from driving on a given date/time in Colombian cities.

Supported cities: Bogotá, Medellín, Cali.
"""

from __future__ import annotations

import logging
from datetime import date

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.pico_y_placa import PicoYPlacaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)

# Colombian public holidays for 2026 (fixed + variable/transferred)
HOLIDAYS_2026 = {
    date(2026, 1, 1),    # Año Nuevo
    date(2026, 1, 12),   # Día de los Reyes Magos (transferred)
    date(2026, 3, 23),   # San José (transferred)
    date(2026, 3, 29),   # Domingo de Ramos
    date(2026, 4, 2),    # Jueves Santo
    date(2026, 4, 3),    # Viernes Santo
    date(2026, 5, 1),    # Día del Trabajo
    date(2026, 5, 18),   # Ascensión del Señor (transferred)
    date(2026, 6, 8),    # Corpus Christi (transferred)
    date(2026, 6, 15),   # Sagrado Corazón (transferred)
    date(2026, 6, 29),   # San Pedro y San Pablo (transferred)
    date(2026, 7, 20),   # Día de la Independencia
    date(2026, 8, 7),    # Batalla de Boyacá
    date(2026, 8, 17),   # Asunción de la Virgen (transferred)
    date(2026, 10, 12),  # Día de la Raza (transferred)
    date(2026, 11, 2),   # Todos los Santos (transferred)
    date(2026, 11, 16),  # Independencia de Cartagena (transferred)
    date(2026, 12, 8),   # Inmaculada Concepción
    date(2026, 12, 25),  # Navidad
}

# Medellín restrictions (first semester 2026)
MEDELLIN_RESTRICTIONS: dict[int, list[int]] = {
    0: [1, 7],  # Monday
    1: [0, 3],  # Tuesday
    2: [4, 6],  # Wednesday
    3: [5, 9],  # Thursday
    4: [2, 8],  # Friday
}

# Cali restrictions (first semester 2026)
CALI_RESTRICTIONS: dict[int, list[int]] = {
    0: [1, 2],  # Monday
    1: [3, 4],  # Tuesday
    2: [5, 6],  # Wednesday
    3: [7, 8],  # Thursday
    4: [9, 0],  # Friday
}


@register
class PicoYPlacaSource(BaseSource):
    """Determine Pico y Placa driving restrictions for Colombian cities."""

    def __init__(self) -> None:
        pass

    def meta(self) -> SourceMeta:
        return SourceMeta(
            name="co.pico_y_placa",
            display_name="Pico y Placa — Restricción Vehicular",
            description="Driving restrictions by plate number in Bogotá, Medellín, and Cali",
            country="CO",
            url="https://www.movilidadbogota.gov.co/web/pico-y-placa",
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=1000,
        )

    def query(self, input: QueryInput) -> BaseModel:
        """Check driving restriction for a plate.

        Expects:
            input.document_number — plate (e.g., "ABC123")
            input.extra["ciudad"]  — city (default "bogota")
            input.extra["fecha"]   — ISO date (default today)
        """
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "co.pico_y_placa",
                f"Only PLATE queries supported, got: {input.document_type}",
            )

        placa = input.document_number.upper().strip()
        if not placa:
            raise SourceError("co.pico_y_placa", "Plate number is required")

        ciudad = input.extra.get("ciudad", "bogota").lower().strip()
        fecha_str = input.extra.get("fecha")

        if fecha_str:
            try:
                fecha = date.fromisoformat(fecha_str)
            except ValueError:
                raise SourceError(
                    "co.pico_y_placa",
                    f"Invalid date format: {fecha_str}. Use ISO format (YYYY-MM-DD)",
                )
        else:
            fecha = date.today()

        # Extract last digit from plate
        ultimo_digito = ""
        for ch in reversed(placa):
            if ch.isdigit():
                ultimo_digito = ch
                break

        if not ultimo_digito:
            raise SourceError(
                "co.pico_y_placa",
                f"Could not extract digit from plate: {placa}",
            )

        digito = int(ultimo_digito)

        if ciudad == "bogota":
            result = self._check_bogota(placa, digito, fecha)
        elif ciudad in ("medellin", "medellín"):
            result = self._check_medellin(placa, digito, fecha)
        elif ciudad == "cali":
            result = self._check_cali(placa, digito, fecha)
        else:
            raise SourceError(
                "co.pico_y_placa",
                f"Unsupported city: {ciudad}. Supported: bogota, medellin, cali",
            )

        result.placa = placa
        result.ultimo_digito = ultimo_digito
        result.ciudad = ciudad
        result.fecha = fecha.isoformat()
        return result

    def _is_holiday(self, fecha: date) -> bool:
        """Check if a date is a Colombian public holiday."""
        return fecha in HOLIDAYS_2026

    def _is_weekend(self, fecha: date) -> bool:
        """Check if a date is a weekend (Saturday=5, Sunday=6)."""
        return fecha.weekday() >= 5

    def _check_bogota(self, placa: str, digito: int, fecha: date) -> PicoYPlacaResult:
        """Bogotá 2024-2026 pico y placa: par/impar by calendar day.

        Even calendar day → plates ending 1,2,3,4,5 restricted
        Odd calendar day  → plates ending 6,7,8,9,0 restricted
        """
        result = PicoYPlacaResult(tipo_vehiculo="particular")

        if self._is_weekend(fecha) or self._is_holiday(fecha):
            reason = "Fin de semana" if self._is_weekend(fecha) else "Día festivo"
            result.restringido = False
            result.motivo = f"{reason} — no aplica pico y placa"
            result.horario = ""
            return result

        day_of_month = fecha.day
        is_even_day = day_of_month % 2 == 0

        if is_even_day:
            restricted_digits = {1, 2, 3, 4, 5}
        else:
            restricted_digits = {6, 7, 8, 9, 0}

        restringido = digito in restricted_digits

        result.restringido = restringido
        result.horario = "6:00 AM - 9:00 PM" if restringido else ""

        if restringido:
            parity = "par" if is_even_day else "impar"
            result.motivo = (
                f"Día {day_of_month} ({parity}): placas terminadas en "
                f"{','.join(str(d) for d in sorted(restricted_digits))} restringidas"
            )
        else:
            result.motivo = (
                f"Día {day_of_month}: placa terminada en {digito} puede circular"
            )

        return result

    def _check_medellin(self, placa: str, digito: int, fecha: date) -> PicoYPlacaResult:
        """Medellín first semester 2026 pico y placa."""
        result = PicoYPlacaResult(tipo_vehiculo="particular")

        if self._is_weekend(fecha) or self._is_holiday(fecha):
            reason = "Fin de semana" if self._is_weekend(fecha) else "Día festivo"
            result.restringido = False
            result.motivo = f"{reason} — no aplica pico y placa"
            result.horario = ""
            return result

        weekday = fecha.weekday()
        restricted = MEDELLIN_RESTRICTIONS.get(weekday, [])
        restringido = digito in restricted

        result.restringido = restringido
        result.horario = "5:00 AM - 8:00 PM" if restringido else ""

        day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        day_name = day_names[weekday] if weekday < 5 else ""

        if restringido:
            result.motivo = (
                f"{day_name}: placas terminadas en "
                f"{','.join(str(d) for d in restricted)} restringidas"
            )
        else:
            result.motivo = (
                f"{day_name}: placa terminada en {digito} puede circular"
            )

        return result

    def _check_cali(self, placa: str, digito: int, fecha: date) -> PicoYPlacaResult:
        """Cali first semester 2026 pico y placa."""
        result = PicoYPlacaResult(tipo_vehiculo="particular")

        if self._is_weekend(fecha) or self._is_holiday(fecha):
            reason = "Fin de semana" if self._is_weekend(fecha) else "Día festivo"
            result.restringido = False
            result.motivo = f"{reason} — no aplica pico y placa"
            result.horario = ""
            return result

        weekday = fecha.weekday()
        restricted = CALI_RESTRICTIONS.get(weekday, [])
        restringido = digito in restricted

        result.restringido = restringido
        result.horario = "6:00 AM - 7:00 PM" if restringido else ""

        day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        day_name = day_names[weekday] if weekday < 5 else ""

        if restringido:
            result.motivo = (
                f"{day_name}: placas terminadas en "
                f"{','.join(str(d) for d in restricted)} restringidas"
            )
        else:
            result.motivo = (
                f"{day_name}: placa terminada en {digito} puede circular"
            )

        return result
