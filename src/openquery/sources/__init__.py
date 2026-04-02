"""Source registry — discover and retrieve data sources."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openquery.sources.base import BaseSource

_REGISTRY: dict[str, type[BaseSource]] = {}


def register(source_cls: type[BaseSource]) -> type[BaseSource]:
    """Decorator to register a source class."""
    from openquery.sources.base import BaseSource

    if not issubclass(source_cls, BaseSource):
        raise TypeError(f"{source_cls} must be a subclass of BaseSource")
    instance = source_cls()
    _REGISTRY[instance.meta().name] = source_cls
    return source_cls


def get_source(name: str, **kwargs) -> BaseSource:
    """Get a source instance by name (e.g., 'co.simit')."""
    _ensure_loaded()
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown source '{name}'. Available: {available}")
    return _REGISTRY[name](**kwargs)


def list_sources() -> list[BaseSource]:
    """List all registered source instances."""
    _ensure_loaded()
    return [cls() for cls in _REGISTRY.values()]


def _ensure_loaded() -> None:
    """Import source modules to trigger registration."""
    if _REGISTRY:
        return
    # Import all source modules to trigger @register decorators
    try:
        import openquery.sources.co.simit  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.runt  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.procuraduria  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.policia  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.adres  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.peajes  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.combustible  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.estaciones_ev  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.siniestralidad  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.fasecolda  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.pico_y_placa  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.recalls  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.vehiculos  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.contraloria  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.us.ofac  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.intl.onu  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.us.nhtsa_vin  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.us.nhtsa_recalls  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.us.nhtsa_complaints  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.us.epa_fuel_economy  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.intl.ship_tracking  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.pep  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.proveedores_ficticios  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.dian_rut  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.estado_cedula  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.sisben  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.rues  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.colpensiones  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.libreta_militar  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.rnmc  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.defuncion  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.inpec  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.secop  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.rethus  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.ruaf  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.fopep  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.snr  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.garantias_mobiliarias  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.copnia  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.runt_conductor  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.puesto_votacion  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.consejos_profesionales  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.migracion_ppt  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.soi  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.cambio_estrato  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.rnt_turismo  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.retencion_vehiculos  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.cufe_dian  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.nombre_completo  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.afiliados_compensado  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.mi_casa_ya  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.einforma  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.consulta_procesos  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.certificado_tradicion  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.runt_soat  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.runt_rtm  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.jep  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.tarifas_energia  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.estado_tramite_cedula  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.seguridad_social  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.registro_civil  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.tutelas  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.comparendos_transito  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.licencias_salud  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.estado_cedula_extranjeria  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.validar_policia  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.rne  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.camara_comercio_medellin  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.directorio_empresas  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.empresas_google  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.supersociedades  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.multas_bogota  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.multas_medellin  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.multas_itagui  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.multas_suiteneptuno  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.co.multas_quipux  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.ec.sri_ruc  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.ec.ant_citaciones  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.ec.cne_padron  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.ec.funcion_judicial  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.ec.supercias  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.ec.senescyt  # noqa: F401
    except ImportError:
        pass
    # Peru
    try:
        import openquery.sources.pe.sunat_ruc  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.pe.poder_judicial  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.pe.osce_sancionados  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.pe.sunarp_vehicular  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.pe.servir_sanciones  # noqa: F401
    except ImportError:
        pass
    # Chile
    try:
        import openquery.sources.cl.sii_rut  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.cl.pjud  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.cl.fiscalizacion  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.cl.superir  # noqa: F401
    except ImportError:
        pass
    # Mexico
    try:
        import openquery.sources.mx.curp  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.mx.sat_efos  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.mx.siem  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.mx.repuve  # noqa: F401
    except ImportError:
        pass
    # Argentina
    try:
        import openquery.sources.ar.afip_cuit  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.ar.pjn  # noqa: F401
    except ImportError:
        pass
    try:
        import openquery.sources.ar.dnrpa  # noqa: F401
    except ImportError:
        pass
    # Brazil
    try:
        import openquery.sources.br.cnpj  # noqa: F401
    except ImportError:
        pass
    # Costa Rica
    try:
        import openquery.sources.cr.cedula  # noqa: F401
    except ImportError:
        pass
    # Dominican Republic
    try:
        import openquery.sources.do.rnc  # noqa: F401
    except ImportError:
        pass
    # Paraguay
    try:
        import openquery.sources.py.ruc  # noqa: F401
    except ImportError:
        pass
    # Guatemala
    try:
        import openquery.sources.gt.nit  # noqa: F401
    except ImportError:
        pass
    # Honduras
    try:
        import openquery.sources.hn.rtn  # noqa: F401
    except ImportError:
        pass
    # El Salvador
    try:
        import openquery.sources.sv.nit  # noqa: F401
    except ImportError:
        pass
    # Uruguay
    try:
        import openquery.sources.uy.sucive  # noqa: F401
    except ImportError:
        pass
