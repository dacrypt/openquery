"""RUNT data model — Colombian vehicle registry."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RuntResult(BaseModel):
    """Data from Colombia's RUNT (Registro Único Nacional de Tránsito).

    All fields from the RUNT API response (infoVehiculo).
    Source: https://runtproapi.runt.gov.co/CYRConsultaVehiculoMS/auth
    """

    queried_at: datetime = Field(default_factory=datetime.now)

    # Vehicle identification
    estado: str = ""
    placa: str = ""
    licencia_transito: str = ""
    id_automotor: int = 0
    tarjeta_registro: str = ""

    # Classification
    clase_vehiculo: str = ""
    id_clase_vehiculo: int = 0
    clasificacion: str = ""
    tipo_servicio: str = ""
    id_tipo_servicio: int | None = None

    # Manufacturer
    marca: str = ""
    linea: str = ""
    modelo_ano: str = ""
    color: str = ""

    # Identifiers
    numero_serie: str = ""
    numero_motor: str = ""
    numero_chasis: str = ""
    numero_vin: str = ""

    # Specs
    tipo_combustible: str = ""
    tipo_carroceria: str = ""
    cilindraje: str = ""
    puertas: int = 0
    peso_bruto_kg: int = 0
    capacidad_carga: str = ""
    capacidad_pasajeros: int = 0
    pasajeros_total: int | None = None
    numero_ejes: int = 0

    # Legal status
    gravamenes: bool = False
    prendas: bool = False
    repotenciado: bool = False
    blindaje: bool = False
    antiguo_clasico: bool = False
    vehiculo_ensenanza: bool = False
    seguridad_estado: bool = False

    # VIN re-stamps
    regrabacion_motor: bool = False
    num_regrabacion_motor: str = ""
    regrabacion_chasis: bool = False
    num_regrabacion_chasis: str = ""
    regrabacion_serie: bool = False
    num_regrabacion_serie: str = ""
    regrabacion_vin: bool = False
    num_regrabacion_vin: str = ""

    # SOAT (mandatory insurance)
    soat_vigente: bool = False
    soat_aseguradora: str = ""
    soat_vencimiento: str = ""

    # RTM (mechanical inspection)
    tecnomecanica_vigente: bool = False
    tecnomecanica_vencimiento: str = ""

    # Registration
    fecha_matricula: str = ""
    fecha_registro: str = ""
    autoridad_transito: str = ""
    dias_matriculado: int | None = None

    # Import
    importacion: int = 0
    fecha_expedicion_lt_importacion: str = ""
    fecha_vencimiento_lt_importacion: str = ""
    nombre_pais: str = ""

    # DIAN (tax authority)
    ver_valida_dian: bool = False
    validacion_dian: str = ""

    # Customs
    subpartida: str = ""
    tipo_maquinaria: str = ""

    # Owner
    no_identificacion: str = ""

    # Control flags
    mostrar_solicitudes: bool = True
