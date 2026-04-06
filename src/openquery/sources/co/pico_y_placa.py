"""Pico y Placa source — Colombian driving restrictions.

Pure logic source (no scraping). Determines whether a vehicle plate
is restricted from driving on a given date/time in Colombian cities.

Features:
- Dynamic Colombian public holiday calculation (any year, Ley 51 de 1983)
- Data-driven city configuration (easy to add new cities)
- Supports 13+ Colombian cities
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from openquery.exceptions import SourceError
from openquery.models.co.pico_y_placa import PicoYPlacaResult
from openquery.sources import register
from openquery.sources.base import BaseSource, DocumentType, QueryInput, SourceMeta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dynamic Colombian Public Holidays (Ley 51 de 1983)
# ---------------------------------------------------------------------------


def _easter_date(year: int) -> date:
    """Compute Easter Sunday for a given year using the Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _next_monday(d: date) -> date:
    """If d is not Monday, move to the next Monday (Ley 51 de 1983 emiliani)."""
    weekday = d.weekday()
    if weekday == 0:
        return d
    return d + timedelta(days=(7 - weekday))


def colombian_holidays(year: int) -> set[date]:
    """Calculate all Colombian public holidays for a given year.

    Based on Ley 51 de 1983 (Ley Emiliani):
    - Fixed holidays that always fall on their date
    - Transferable holidays moved to the following Monday
    - Easter-relative holidays
    """
    easter = _easter_date(year)

    # Fixed holidays (always on their date)
    fixed = [
        date(year, 1, 1),  # Año Nuevo
        date(year, 5, 1),  # Día del Trabajo
        date(year, 7, 20),  # Grito de Independencia
        date(year, 8, 7),  # Batalla de Boyacá
        date(year, 12, 8),  # Inmaculada Concepción
        date(year, 12, 25),  # Navidad
    ]

    # Transferable to next Monday (Ley Emiliani)
    transferred = [
        _next_monday(date(year, 1, 6)),  # Reyes Magos
        _next_monday(date(year, 3, 19)),  # San José
        _next_monday(date(year, 6, 29)),  # San Pedro y San Pablo
        _next_monday(date(year, 8, 15)),  # Asunción de la Virgen
        _next_monday(date(year, 10, 12)),  # Día de la Raza
        _next_monday(date(year, 11, 1)),  # Todos los Santos
        _next_monday(date(year, 11, 11)),  # Independencia de Cartagena
    ]

    # Easter-relative holidays
    easter_relative = [
        easter - timedelta(days=3),  # Jueves Santo
        easter - timedelta(days=2),  # Viernes Santo
        _next_monday(easter + timedelta(days=39)),  # Ascensión del Señor (transferred)
        _next_monday(easter + timedelta(days=60)),  # Corpus Christi (transferred)
        _next_monday(easter + timedelta(days=68)),  # Sagrado Corazón (transferred)
    ]

    return set(fixed + transferred + easter_relative)


# ---------------------------------------------------------------------------
# City Configurations — Data-driven pico y placa rules
# ---------------------------------------------------------------------------

# Type of restriction
EVEN_ODD = "par_impar"  # Even/odd calendar day (like Bogotá)
WEEKDAY_BASED = "dia_semana"  # By day of week (like Medellín, Cali)
NO_RESTRICTION = "sin_restriccion"

CityConfig = dict[str, Any]

CITIES: dict[str, CityConfig] = {
    "bogota": {
        "nombre": "Bogotá D.C.",
        "tipo": EVEN_ODD,
        "horario": "6:00 AM - 9:00 PM",
        "regla": {
            # Even day → plates 6,7,8,9,0 restricted; Odd day → plates 1,2,3,4,5 restricted
            # Verified: Infobae 2026-03-27, bogota.gov.co
            "par": [6, 7, 8, 9, 0],
            "impar": [1, 2, 3, 4, 5],
        },
        "fuente": "https://bogota.gov.co/mi-ciudad/movilidad/pico-y-placa-bogota-vehiculos-particulares-1-31-de-marzo-de-2026",
        "vigencia": "2024-2026",
    },
    "medellin": {
        "nombre": "Medellín",
        "tipo": WEEKDAY_BASED,
        "horario": "5:00 AM - 8:00 PM",
        "regla": {
            # Verified: medellin.gov.co, primer semestre 2026 (feb 2 - jul 31)
            0: [1, 7],  # Lunes
            1: [0, 3],  # Martes
            2: [4, 6],  # Miércoles
            3: [5, 9],  # Jueves
            4: [2, 8],  # Viernes
        },
        "fuente": "https://www.medellin.gov.co/es/secretaria-de-movilidad/pico-y-placa-medellin-2023-segundo-semestre/",
        "vigencia": "Feb 2 - Jul 31, 2026",
    },
    "cali": {
        "nombre": "Santiago de Cali",
        "tipo": WEEKDAY_BASED,
        "horario": "6:00 AM - 7:00 PM",
        "regla": {
            # Verified: cali.gov.co, primer semestre 2026 (ene 5 - jun 30)
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.cali.gov.co/boletines/publicaciones/190703/asi-sera-la-nueva-rotacion-del-pico-y-placa-en-cali-para-el-primer-semestre-de-2026/",
        "vigencia": "Ene 5 - Jun 30, 2026",
    },
    "barranquilla": {
        "nombre": "Barranquilla",
        "tipo": WEEKDAY_BASED,
        "horario": "7:00 AM - 8:00 PM",
        "regla": {
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.barranquilla.gov.co/transito",
        "vigencia": "2026",
    },
    "bucaramanga": {
        "nombre": "Bucaramanga",
        "tipo": WEEKDAY_BASED,
        "horario": "6:00 AM - 8:00 PM",
        "regla": {
            # Verified: americanmotos.com, desde ene 13 2026
            # Post-Semana Santa rotation (from Apr 6): 9,0 / 1,2 / 3,4 / 5,6 / 7,8
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.americanmotos.com/blogs/noticias/nuevo-pico-y-placa-bucaramanga-2026-todo-lo-que-debes-saber",
        "vigencia": "Ene 13 - Jun 30, 2026",
    },
    "cartagena": {
        "nombre": "Cartagena de Indias",
        "tipo": WEEKDAY_BASED,
        "horario": "7:00 - 9:00 AM, 6:00 - 8:00 PM",
        "regla": {
            # Verified: Infobae 2026-03-31, rotation Mar 30 - Jun 27
            0: [7, 8],  # Lunes
            1: [9, 0],  # Martes
            2: [1, 2],  # Miércoles
            3: [3, 4],  # Jueves
            4: [5, 6],  # Viernes
        },
        "fuente": "https://www.infobae.com/colombia/2026/03/31/pico-y-placa-en-cartagena-restricciones-vehiculares-para-evitar-multas-este-martes-31-de-marzo/",
        "vigencia": "Mar 30 - Jun 27, 2026",
    },
    "pereira": {
        "nombre": "Pereira",
        "tipo": WEEKDAY_BASED,
        "horario": "6:00 AM - 8:00 PM",
        "regla": {
            # Verified: eltiempo.com, Mar 31 2026 (Tue = 2,3)
            0: [0, 1],  # Lunes
            1: [2, 3],  # Martes
            2: [4, 5],  # Miércoles
            3: [6, 7],  # Jueves
            4: [8, 9],  # Viernes
        },
        "fuente": "https://www.pereira.gov.co/movilidad",
        "vigencia": "2026",
    },
    "manizales": {
        "nombre": "Manizales",
        "tipo": WEEKDAY_BASED,
        "horario": "6:30 AM - 7:30 PM",
        "regla": {
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.manizales.gov.co/",
        "vigencia": "2026",
    },
    "ibague": {
        "nombre": "Ibagué",
        "tipo": WEEKDAY_BASED,
        "horario": "6:30 AM - 7:30 PM",
        "regla": {
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.ibague.gov.co/",
        "vigencia": "2026",
    },
    "cucuta": {
        "nombre": "Cúcuta",
        "tipo": WEEKDAY_BASED,
        "horario": "6:00 AM - 8:00 PM",
        "regla": {
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.cucuta.gov.co/",
        "vigencia": "2026",
    },
    "villavicencio": {
        "nombre": "Villavicencio",
        "tipo": WEEKDAY_BASED,
        "horario": "6:00 AM - 8:00 PM",
        "regla": {
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.villavicencio.gov.co/",
        "vigencia": "2026",
    },
    "pasto": {
        "nombre": "San Juan de Pasto",
        "tipo": WEEKDAY_BASED,
        "horario": "6:00 AM - 8:00 PM",
        "regla": {
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.pasto.gov.co/",
        "vigencia": "2026",
    },
    "armenia": {
        "nombre": "Armenia",
        "tipo": WEEKDAY_BASED,
        "horario": "6:00 AM - 8:00 PM",
        "regla": {
            0: [1, 2],  # Lunes
            1: [3, 4],  # Martes
            2: [5, 6],  # Miércoles
            3: [7, 8],  # Jueves
            4: [9, 0],  # Viernes
        },
        "fuente": "https://www.armenia.gov.co/",
        "vigencia": "2026",
    },
}

# Aliases for accent-insensitive lookups
CITY_ALIASES: dict[str, str] = {
    "medellín": "medellin",
    "bogotá": "bogota",
    "ibagué": "ibague",
    "cúcuta": "cucuta",
    "san juan de pasto": "pasto",
    "santiago de cali": "cali",
    "cartagena de indias": "cartagena",
}

DAY_NAMES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


# ---------------------------------------------------------------------------
# Source Implementation
# ---------------------------------------------------------------------------


@register
class PicoYPlacaSource(BaseSource):
    """Determine Pico y Placa driving restrictions for Colombian cities.

    Supports 13 cities with data-driven configuration.
    Dynamic Colombian holiday calculation for any year.
    """

    def __init__(self) -> None:
        self._holiday_cache: dict[int, set[date]] = {}

    def meta(self) -> SourceMeta:
        city_list = ", ".join(sorted(CITIES.keys()))
        return SourceMeta(
            name="co.pico_y_placa",
            display_name="Pico y Placa — Restricción Vehicular",
            description=f"Driving restrictions by plate number in Colombian cities: {city_list}",
            country="CO",
            url="https://www.movilidadbogota.gov.co/web/pico-y-placa",
            supported_inputs=[DocumentType.PLATE],
            requires_captcha=False,
            requires_browser=False,
            rate_limit_rpm=1000,
        )

    def query(self, input: QueryInput) -> BaseModel:
        if input.document_type != DocumentType.PLATE:
            raise SourceError(
                "co.pico_y_placa", f"Only PLATE queries supported, got: {input.document_type}"
            )

        placa = input.document_number.upper().strip()
        if not placa:
            raise SourceError("co.pico_y_placa", "Plate number is required")

        ciudad_raw = input.extra.get("ciudad", "bogota").lower().strip()
        fecha_str = input.extra.get("fecha")

        if fecha_str:
            try:
                fecha = date.fromisoformat(fecha_str)
            except ValueError:
                raise SourceError(
                    "co.pico_y_placa", f"Invalid date format: {fecha_str}. Use YYYY-MM-DD"
                )
        else:
            fecha = date.today()

        # Resolve city alias
        ciudad = CITY_ALIASES.get(ciudad_raw, ciudad_raw)

        if ciudad not in CITIES:
            available = ", ".join(sorted(CITIES.keys()))
            raise SourceError(
                "co.pico_y_placa", f"Unsupported city: {ciudad_raw}. Available: {available}"
            )

        # Extract last digit
        ultimo_digito = ""
        for ch in reversed(placa):
            if ch.isdigit():
                ultimo_digito = ch
                break
        if not ultimo_digito:
            raise SourceError("co.pico_y_placa", f"Could not extract digit from plate: {placa}")

        digito = int(ultimo_digito)
        config = CITIES[ciudad]

        result = self._check_restriction(placa, digito, fecha, config)
        result.placa = placa
        result.ultimo_digito = ultimo_digito
        result.ciudad = ciudad
        result.ciudad_nombre = config["nombre"]
        result.fecha = fecha.isoformat()
        result.fuente_oficial = config["fuente"]
        result.vigencia = config["vigencia"]
        return result

    def _get_holidays(self, year: int) -> set[date]:
        if year not in self._holiday_cache:
            self._holiday_cache[year] = colombian_holidays(year)
        return self._holiday_cache[year]

    def _check_restriction(
        self, placa: str, digito: int, fecha: date, config: CityConfig
    ) -> PicoYPlacaResult:
        result = PicoYPlacaResult(tipo_vehiculo="particular")

        # Weekend check
        if fecha.weekday() >= 5:
            result.restringido = False
            result.motivo = "Fin de semana — no aplica pico y placa"
            return result

        # Holiday check (dynamic)
        holidays = self._get_holidays(fecha.year)
        if fecha in holidays:
            result.restringido = False
            result.motivo = "Día festivo — no aplica pico y placa"
            return result

        tipo = config["tipo"]

        if tipo == EVEN_ODD:
            return self._check_even_odd(digito, fecha, config, result)
        elif tipo == WEEKDAY_BASED:
            return self._check_weekday(digito, fecha, config, result)
        elif tipo == NO_RESTRICTION:
            result.restringido = False
            result.motivo = "Esta ciudad no tiene pico y placa vigente"
            return result
        else:
            raise SourceError("co.pico_y_placa", f"Unknown restriction type: {tipo}")

    def _check_even_odd(
        self, digito: int, fecha: date, config: CityConfig, result: PicoYPlacaResult
    ) -> PicoYPlacaResult:
        day_of_month = fecha.day
        is_even = day_of_month % 2 == 0

        restricted_digits = set(config["regla"]["par"] if is_even else config["regla"]["impar"])
        restringido = digito in restricted_digits

        result.restringido = restringido
        result.horario = config["horario"] if restringido else ""

        parity = "par" if is_even else "impar"
        if restringido:
            result.motivo = (
                f"Día {day_of_month} ({parity}): placas terminadas en "
                f"{','.join(str(d) for d in sorted(restricted_digits))} restringidas"
            )
        else:
            result.motivo = f"Día {day_of_month}: placa terminada en {digito} puede circular"

        return result

    def _check_weekday(
        self, digito: int, fecha: date, config: CityConfig, result: PicoYPlacaResult
    ) -> PicoYPlacaResult:
        weekday = fecha.weekday()
        restricted = config["regla"].get(weekday, [])
        restringido = digito in restricted

        result.restringido = restringido
        result.horario = config["horario"] if restringido else ""

        day_name = DAY_NAMES[weekday]
        if restringido:
            result.motivo = (
                f"{day_name}: placas terminadas en "
                f"{','.join(str(d) for d in restricted)} restringidas"
            )
        else:
            result.motivo = f"{day_name}: placa terminada en {digito} puede circular"

        return result
