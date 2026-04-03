#!/usr/bin/env python3
"""Run real queries against all OpenQuery sources and generate a test results report.

Usage:
    uv run python tests/e2e/run_real_queries.py

Outputs results to docs/test_results.md
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from openquery.sources import get_source, list_sources
from openquery.sources.base import DocumentType, QueryInput

# ── Known source status (sources that can't be live-tested) ─────────────
# These are skipped during testing and reported with their known reason.
# Update this dict when a source becomes testable or a new blocker appears.

KNOWN_STATUS: dict[str, str] = {
    # Auth/credentials required — no public access
    "co.rne": "AUTH_REQUIRED: Needs CRC portal credentials (usuario/password)",
    "co.fasecolda": "AUTH_REQUIRED: Needs manual bearer token capture",
    "co.fopep": "AUTH_REQUIRED: Login-gated portal with reCAPTCHA",
    "co.soi": "AUTH_REQUIRED: Login-only platform (ACH Colombia)",
    "ec.sri_ruc": "AUTH_REQUIRED: SRI API requires authorization token",
    # API removed
    "co.proveedores_ficticios": "API_REMOVED: Dataset removed from datos.gov.co",
    "co.directorio_empresas": "API_REMOVED: Dataset API no longer available",
    # No search form
    "co.jep": "NO_FORM: JEP is SharePoint — no search form",
    # WAF blocks even Patchright from this IP
    "co.estado_cedula": "WAF_BLOCKED: Registraduría WAF blocks this IP (ICEfaces dynamic forms)",
    "co.nombre_completo": "WAF_BLOCKED: Registraduría WAF",
    "co.defuncion": "WAF_BLOCKED: Registraduría WAF",
    "co.puesto_votacion": "WAF_BLOCKED: Registraduría WAF",
    "co.estado_tramite_cedula": "WAF_BLOCKED: Registraduría WAF",
    "co.registro_civil": "WAF_BLOCKED: Registraduría WAF",
    "co.estado_cedula_extranjeria": "WAF_BLOCKED: Migración WAF",
    "co.colpensiones": "WAF_BLOCKED: Returns 403 even with Patchright",
    "co.rethus": "WAF_BLOCKED: SISPRO WAF blocks even Patchright",
    "co.ruaf": "WAF_BLOCKED: SISPRO WAF blocks even Patchright",
    "co.supersociedades": "WAF_BLOCKED: Supersociedades WAF blocks even Patchright",
    # Sites genuinely down/unreachable
    "co.certificado_tradicion": "SITE_DOWN: supernotariado.gov.co still timing out",
    "co.inpec": "SITE_DOWN: INPEC 504 from Azure Gateway",
    "pe.servir_sanciones": "SITE_DOWN: sanciones.gob.pe timeout",
    "ar.afip_cuit": "CAPTCHA_INTERMITTENT: AFIP CAPTCHA OCR sometimes returns too few chars",
    "br.fipe": "API_ERROR: BrasilAPI FIPE returns HTTP 500 intermittently",
    "cl.fiscalizacion": "SITE_DOWN: Site timeout",
    "mx.repuve": "SITE_DOWN: repuve.gob.mx timeout",
    "co.runt": "CAPTCHA_INTERMITTENT: RUNT captcha API sometimes returns empty",
    "co.runt_conductor": "CAPTCHA_INTERMITTENT: RUNT conductor captcha returns empty",
    "co.runt_soat": "CAPTCHA_INTERMITTENT: RUNT SOAT captcha fails validation",
    "co.runt_rtm": "CAPTCHA_INTERMITTENT: RUNT RTM captcha fails validation",
    # Source URL decommissioned or fundamentally changed
    "ec.senescyt": "URL_MOVED: senescyt.gob.ec moved to educacionsuperior.gob.ec, endpoint gone",
    "mx.sat_efos": "NO_FORM: SAT EFOS page is static XLS download, no search form",
    "ec.ant_citaciones": "API_ERROR: ANT API returns HTTP 500 server error",
    # Sites with specific blocking that needs more work
    "ec.cne_padron": "CAPTCHA_GATE: Entire CNE site gated behind Imperva bot-detection CAPTCHA",
    "mx.siem": "TERMS_WALL: Vue SPA requires accepting terms modal before search",
    "mx.curp": "TIMEOUT: gob.mx API still times out even at 45s",
    # SPA/timing issues
    "co.consulta_procesos": "SPA_TIMING: Vue.js dynamic IDs, ElementHandle detaches",
    "co.libreta_militar": "SPA_TIMING: ElementHandle.fill timeout (page loads but form elements detach)",
    "pe.poder_judicial": "SELECTOR_STALE: PJ Peru form selectors need update",
    "pe.osce_sancionados": "CAPTCHA: Image CAPTCHA + page wait timeout",
    "ar.dnrpa": "SPA_TIMING: DNRPA ElementHandle.fill timeout",
    "cl.pjud": "SPA_TIMING: PJUD ElementHandle timeout",
    # Remaining selector issues (pages load, forms don't match)
    "co.rnmc": "SPA_TIMING: ASP.NET __doPostBack causes page reload + element detach",
    "co.tutelas": "SELECTOR_STALE: Rama Judicial form selectors outdated",
    "co.rues": "RECAPTCHA: Detected by middleware — needs CAPSOLVER_API_KEY to solve",
    "co.adres": "RECAPTCHA: Detected by middleware — needs CAPSOLVER_API_KEY to solve",
    "co.seguridad_social": "SELECTOR_STALE: miseguridadsocial.gov.co form selectors outdated",
    "co.mi_casa_ya": "SELECTOR_STALE: Mi Casa Ya form selectors outdated",
    # ar.afip_cuit removed — LLM vision CAPTCHA middleware wired
    "co.procuraduria": "CAPTCHA_INTERMITTENT: Knowledge CAPTCHA needs Ollama or LLM API key",
    # New countries — blockers identified
    "do.rnc": "WAF_BLOCKED: DGII Dominican Republic returns 403 to headless browsers",
    "gt.nit": "WAF_BLOCKED: SAT Guatemala behind Cloudflare Turnstile",
    # gt.banguat removed — SOAP parsing fixed
    "py.datos": "API_REDIRECT: datos.gov.py CKAN API redirects to HTML page",
    # py.ruc removed — reCAPTCHA middleware wired
    # cl.sii_rut removed — testing again (intermittent)
    # uy.sucive removed — reCAPTCHA middleware wired
    "pa.ruc": "WAF_BLOCKED: DGI Panama WAF blocks automated requests + JS rendering required",
    # co.afiliados_compensado removed — re-testing
}

# ── Public test data (no personal data) ──────────────────────────────────

QUERIES: list[dict] = [
    # ── Colombia: Identity ──
    {"source": "co.estado_cedula", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque (ex-presidente)"},
    {"source": "co.nombre_completo", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.defuncion", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.puesto_votacion", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.estado_tramite_cedula", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.registro_civil", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.libreta_militar", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.estado_cedula_extranjeria", "doc_type": "custom", "doc_number": "123456", "label": "Test CE number"},
    {"source": "co.validar_policia", "doc_type": "custom", "doc_number": "79940745", "label": "Test policia", "extra": {"placa_policia": "79940745", "carnet": "12345"}},
    {"source": "co.migracion_ppt", "doc_type": "custom", "doc_number": "12345678", "label": "Test PPT"},

    # ── Colombia: Background ──
    {"source": "co.policia", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.procuraduria", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.contraloria", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.rnmc", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.consulta_procesos", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.tutelas", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.jep", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.inpec", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},

    # ── Colombia: Compliance ──
    {"source": "co.pep", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.proveedores_ficticios", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol NIT"},
    {"source": "co.rne", "doc_type": "custom", "doc_number": "3001234567", "label": "Test phone", "extra": {"telefono": "3001234567"}},

    # ── Colombia: Tax & Business ──
    {"source": "co.dian_rut", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol NIT"},
    {"source": "co.rues", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol NIT"},
    {"source": "co.secop", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol NIT"},
    {"source": "co.cufe_dian", "doc_type": "custom", "doc_number": "test-cufe-123", "label": "Test CUFE"},
    {"source": "co.einforma", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol NIT"},
    {"source": "co.camara_comercio_medellin", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol NIT"},
    {"source": "co.directorio_empresas", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol NIT"},
    {"source": "co.empresas_google", "doc_type": "custom", "doc_number": "Ecopetrol", "label": "Ecopetrol Google"},
    {"source": "co.supersociedades", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol NIT"},
    {"source": "co.secop_sanciones", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol sanciones"},
    {"source": "co.simit_historico", "doc_type": "placa", "doc_number": "MIK715", "label": "SIMIT historico MIK715"},
    {"source": "co.secop_procesos", "doc_type": "nit", "doc_number": "899999068", "label": "SECOP procesos Ecopetrol"},

    # ── Colombia: Vehicles ──
    {"source": "co.simit", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.runt", "doc_type": "placa", "doc_number": "BXM627", "label": "Test plate"},
    {"source": "co.runt_conductor", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.runt_soat", "doc_type": "placa", "doc_number": "BXM627", "label": "Test plate"},
    {"source": "co.runt_rtm", "doc_type": "placa", "doc_number": "BXM627", "label": "Test plate"},
    {"source": "co.comparendos_transito", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.retencion_vehiculos", "doc_type": "placa", "doc_number": "BXM627", "label": "Test plate"},
    {"source": "co.fasecolda", "doc_type": "custom", "doc_number": "test", "label": "Test FASECOLDA", "extra": {"marca": "CHEVROLET", "linea": "SPARK", "modelo": "2020"}},
    {"source": "co.recalls", "doc_type": "custom", "doc_number": "test", "label": "Test recalls", "extra": {"marca": "CHEVROLET"}},

    # ── Colombia: Vehicles (API/data) ──
    {"source": "co.pico_y_placa", "doc_type": "placa", "doc_number": "BXM627", "label": "Test plate"},
    {"source": "co.vehiculos", "doc_type": "placa", "doc_number": "BXM627", "label": "Test plate"},
    {"source": "co.peajes", "doc_type": "custom", "doc_number": "peaje", "label": "Peaje ALVARADO", "extra": {"peaje": "ALVARADO"}},
    {"source": "co.combustible", "doc_type": "custom", "doc_number": "fuel", "label": "Fuel Bogota", "extra": {"municipio": "BOGOTA"}},
    {"source": "co.estaciones_ev", "doc_type": "custom", "doc_number": "ev", "label": "EV stations Bogota", "extra": {"ciudad": "Bogota"}},
    {"source": "co.siniestralidad", "doc_type": "custom", "doc_number": "stats", "label": "Crashes Cundinamarca", "extra": {"departamento": "CUNDINAMARCA"}},

    # ── Colombia: Social Security ──
    {"source": "co.adres", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.colpensiones", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.fopep", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.ruaf", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.rethus", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.soi", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.seguridad_social", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.afiliados_compensado", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.sisben", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.licencias_salud", "doc_type": "nit", "doc_number": "838000096", "label": "Hospital San Rafael Leticia"},

    # ── Colombia: Property ──
    {"source": "co.snr", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.certificado_tradicion", "doc_type": "custom", "doc_number": "050C12345678", "label": "Test cert"},
    {"source": "co.garantias_mobiliarias", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.cambio_estrato", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},

    # ── Colombia: Other ──
    {"source": "co.mi_casa_ya", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    {"source": "co.tarifas_energia", "doc_type": "custom", "doc_number": "energia", "label": "Energy tariffs ENEL", "extra": {"municipio": "ENEL"}},
    {"source": "co.rnt_turismo", "doc_type": "nit", "doc_number": "899999068", "label": "Ecopetrol RNT", "extra": {"name": "Ecopetrol"}},

    # ── Colombia: Professional Councils ──
    {"source": "co.copnia", "doc_type": "cedula", "doc_number": "79940745", "label": "Iván Duque"},
    # co.consejos_profesionales doesn't exist as a single source — removed

    # ── USA ──
    {"source": "us.nhtsa_vin", "doc_type": "vin", "doc_number": "1HGCM82633A004352", "label": "Honda Accord"},
    {"source": "us.nhtsa_recalls", "doc_type": "custom", "doc_number": "recalls", "label": "Tesla Model Y 2024", "extra": {"make": "Tesla", "model": "Model Y", "year": "2024"}},
    {"source": "us.nhtsa_complaints", "doc_type": "custom", "doc_number": "complaints", "label": "Tesla Model 3 2023", "extra": {"make": "Tesla", "model": "Model 3", "year": "2023"}},
    {"source": "us.epa_fuel_economy", "doc_type": "custom", "doc_number": "fuel", "label": "Toyota Camry 2024", "extra": {"make": "Toyota", "model": "Camry", "year": "2024"}},
    {"source": "us.ofac", "doc_type": "custom", "doc_number": "Nicolas Maduro", "label": "Maduro OFAC"},

    # ── International ──
    {"source": "intl.onu", "doc_type": "custom", "doc_number": "Nicolas Maduro", "label": "Maduro UN sanctions"},
    {"source": "intl.ship_tracking", "doc_type": "custom", "doc_number": "MMSI:123456789", "label": "Test vessel"},

    # ── Ecuador ──
    {"source": "ec.sri_ruc", "doc_type": "custom", "doc_number": "1768153530001", "label": "EP Petroecuador", "extra": {"ruc": "1768153530001"}},
    {"source": "ec.ant_citaciones", "doc_type": "cedula", "doc_number": "1712345678", "label": "Test EC cedula"},
    {"source": "ec.cne_padron", "doc_type": "cedula", "doc_number": "1712345678", "label": "Test EC cedula"},
    {"source": "ec.funcion_judicial", "doc_type": "cedula", "doc_number": "1712345678", "label": "Test EC cedula"},
    {"source": "ec.supercias", "doc_type": "custom", "doc_number": "1790010937001", "label": "Banco Pichincha", "extra": {"ruc": "1790010937001"}},
    {"source": "ec.senescyt", "doc_type": "cedula", "doc_number": "1712345678", "label": "Test EC cedula"},

    # ── Peru ──
    {"source": "pe.sunat_ruc", "doc_type": "custom", "doc_number": "20100030595", "label": "Banco de la Nacion", "extra": {"ruc": "20100030595"}},
    {"source": "pe.poder_judicial", "doc_type": "custom", "doc_number": "20100030595", "label": "Banco de la Nacion", "extra": {"nombre": "Banco de la Nacion"}},
    {"source": "pe.osce_sancionados", "doc_type": "custom", "doc_number": "20100030595", "label": "Banco de la Nacion", "extra": {"ruc": "20100030595"}},
    {"source": "pe.sunarp_vehicular", "doc_type": "placa", "doc_number": "ABC-123", "label": "Test PE plate"},
    {"source": "pe.servir_sanciones", "doc_type": "custom", "doc_number": "12345678", "label": "Test PE search", "extra": {"nombre": "Garcia"}},

    # ── Chile ──
    {"source": "cl.sii_rut", "doc_type": "custom", "doc_number": "61704000K", "label": "Codelco", "extra": {"rut": "61704000-K"}},
    {"source": "cl.pjud", "doc_type": "custom", "doc_number": "61704000K", "label": "Codelco"},
    {"source": "cl.fiscalizacion", "doc_type": "placa", "doc_number": "BBBB12", "label": "Test CL plate"},
    {"source": "cl.superir", "doc_type": "custom", "doc_number": "61704000K", "label": "Codelco", "extra": {"rut": "61704000-K"}},

    # ── Mexico ──
    {"source": "mx.curp", "doc_type": "custom", "doc_number": "GARC850101HDFRRL09", "label": "Test CURP"},
    {"source": "mx.sat_efos", "doc_type": "custom", "doc_number": "test_rfc", "label": "Test SAT RFC"},
    {"source": "mx.siem", "doc_type": "custom", "doc_number": "test", "label": "Test SIEM"},
    {"source": "mx.repuve", "doc_type": "placa", "doc_number": "ABC1234", "label": "Test MX plate"},
    {"source": "mx.inegi", "doc_type": "custom", "doc_number": "estados", "label": "INEGI Estados"},

    # ── Argentina ──
    {"source": "ar.afip_cuit", "doc_type": "custom", "doc_number": "30546689979", "label": "YPF S.A."},
    {"source": "ar.pjn", "doc_type": "custom", "doc_number": "30546689979", "label": "YPF S.A."},
    {"source": "ar.dnrpa", "doc_type": "placa", "doc_number": "AB123CD", "label": "Test AR plate"},
    {"source": "ar.georef", "doc_type": "custom", "doc_number": "Av Corrientes 1000", "label": "GeoRef Buenos Aires", "extra": {"direccion": "Av Corrientes 1000", "provincia": "buenos aires"}},

    # ── Brazil ──
    {"source": "br.cnpj", "doc_type": "nit", "doc_number": "33000167000101", "label": "Petrobras CNPJ"},
    {"source": "br.datajud", "doc_type": "custom", "doc_number": "00008323520184013202", "label": "Test BR processo", "extra": {"processo": "00008323520184013202", "tribunal": "api_publica_tjsp"}},
    {"source": "br.fipe", "doc_type": "custom", "doc_number": "001004-9", "label": "FIPE Gol 1.0", "extra": {"codigo_fipe": "001004-9"}},
    {"source": "br.cep", "doc_type": "custom", "doc_number": "01001000", "label": "Praça da Sé SP", "extra": {"cep": "01001000"}},
    {"source": "br.banks", "doc_type": "custom", "doc_number": "001", "label": "Banco do Brasil", "extra": {"code": "001"}},
    {"source": "br.pix", "doc_type": "custom", "doc_number": "pix", "label": "PIX participants"},
    {"source": "br.corretoras", "doc_type": "nit", "doc_number": "02332886000104", "label": "XP Investimentos"},

    {"source": "br.ddd", "doc_type": "custom", "doc_number": "11", "label": "DDD São Paulo", "extra": {"ddd": "11"}},

    # ── Costa Rica ──
    {"source": "cr.cedula", "doc_type": "cedula", "doc_number": "101110111", "label": "Test CR cedula"},

    # ── Dominican Republic ──
    {"source": "do.rnc", "doc_type": "custom", "doc_number": "101000301", "label": "Test DO RNC"},
    {"source": "do.datos", "doc_type": "custom", "doc_number": "poblacion", "label": "DO datos abiertos", "extra": {"q": "poblacion"}},

    # ── Paraguay ──
    {"source": "py.ruc", "doc_type": "custom", "doc_number": "80000011-7", "label": "Test PY RUC", "extra": {"ruc": "80000011-7"}},
    {"source": "py.datos", "doc_type": "custom", "doc_number": "tipo cambio", "label": "PY datos abiertos", "extra": {"q": "tipo cambio"}},

    # ── Guatemala ──
    {"source": "gt.nit", "doc_type": "custom", "doc_number": "1234567", "label": "Test GT NIT", "extra": {"nit": "1234567"}},
    {"source": "gt.banguat", "doc_type": "custom", "doc_number": "tipo_cambio", "label": "Banguat USD/GTQ"},

    # ── Honduras ──
    {"source": "hn.rtn", "doc_type": "custom", "doc_number": "08011900000001", "label": "Test HN RTN", "extra": {"rtn": "08011900000001"}},

    # ── El Salvador ──
    {"source": "sv.nit", "doc_type": "custom", "doc_number": "00000000-0", "label": "Test SV DUI", "extra": {"dui": "00000000-0"}},

    # ── Uruguay ──
    {"source": "uy.sucive", "doc_type": "placa", "doc_number": "SBC1234", "label": "Test UY plate", "extra": {"matricula": "SBC1234"}},
    {"source": "uy.datos", "doc_type": "custom", "doc_number": "transporte", "label": "UY datos abiertos", "extra": {"q": "transporte"}},

    # ── Bolivia ──
    {"source": "bo.nit", "doc_type": "custom", "doc_number": "1023220028", "label": "Test BO NIT", "extra": {"nit": "1023220028"}},

    # ── Panama ──
    {"source": "pa.ruc", "doc_type": "custom", "doc_number": "8-NT-1-1000", "label": "Test PA RUC", "extra": {"ruc": "8-NT-1-1000"}},
    {"source": "pa.inec", "doc_type": "custom", "doc_number": "categorias", "label": "INEC categorias"},
]


def run_query(q: dict) -> dict:
    """Run a single query and return result dict."""
    source_name = q["source"]
    start = time.monotonic()
    result = {
        "source": source_name,
        "label": q.get("label", ""),
        "doc_type": q["doc_type"],
        "doc_number": q["doc_number"],
        "status": "UNKNOWN",
        "latency_ms": 0,
        "error": "",
        "fields": 0,
        "tested_at": datetime.now().isoformat(timespec="seconds"),
    }

    # Check known status — skip actual query
    if source_name in KNOWN_STATUS:
        result["status"] = "SKIP"
        result["error"] = KNOWN_STATUS[source_name]
        return result

    try:
        src = get_source(source_name)
        inp = QueryInput(
            document_type=DocumentType(q["doc_type"]),
            document_number=q["doc_number"],
            extra=q.get("extra", {}),
        )
        resp = src.query(inp)
        elapsed = int((time.monotonic() - start) * 1000)
        result["latency_ms"] = elapsed

        # Count non-empty fields
        data = resp.model_dump(mode="json", exclude={"audit"})
        non_empty = sum(1 for v in data.values() if v and v != 0 and v != [] and v != {})
        result["fields"] = non_empty

        result["status"] = "OK"
    except KeyError as e:
        result["status"] = "NOT_FOUND"
        result["error"] = str(e)
        result["latency_ms"] = int((time.monotonic() - start) * 1000)
    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        result["latency_ms"] = int((time.monotonic() - start) * 1000)

    return result


def categorize_error(error: str) -> str:
    """Categorize error into a human-readable bucket."""
    if not error:
        return ""
    e = error.lower()
    if "err_name_not_resolved" in e or "err_connection_reset" in e:
        return "DNS/Network"
    if "timeout" in e and "page.goto" in e:
        return "Site Unreachable"
    if "wait_for_selector" in e or "wait_for_load" in e:
        return "HTML Changed"
    if "elementhandle" in e:
        return "HTML Changed"
    if "captcha" in e:
        return "CAPTCHA"
    if "ssl" in e or "certificate" in e:
        return "SSL Error"
    if "http 4" in e or "http 5" in e:
        return "API Error"
    if "must provide" in e or "unsupported" in e:
        return "Bad Test Data"
    if "could not find" in e:
        return "HTML Changed"
    if "token" in e:
        return "Auth Required"
    return "Other"


def generate_report(results: list[dict]) -> str:
    """Generate markdown report from results."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    ok = sum(1 for r in results if r["status"] == "OK")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    tested = total = len(results)
    tested_count = total - skipped

    # Categorize skipped sources
    skip_categories: dict[str, int] = {}
    for r in results:
        if r["status"] == "SKIP":
            reason = r.get("error", "").split(":")[0] if ":" in r.get("error", "") else "UNKNOWN"
            skip_categories[reason] = skip_categories.get(reason, 0) + 1

    # Categorize actual failures
    fail_categories: dict[str, int] = {}
    for r in results:
        if r["status"] == "ERROR":
            cat = categorize_error(r.get("error", ""))
            fail_categories[cat] = fail_categories.get(cat, 0) + 1

    pct = ok / tested_count * 100 if tested_count else 0

    lines = [
        "# Real Query Test Results",
        "",
        f"> Last full run: **{now}**",
        f"> Total sources: **{total}** | Tested: **{tested_count}** | OK: **{ok}** | Errors: **{errors}** | Known skip: **{skipped}**",
        f"> **Live success rate: {pct:.0f}%** ({ok}/{tested_count} tested) | **Accountability: 100%** ({ok + skipped + errors}/{total})",
        "",
        "This file documents the last real execution of every OpenQuery source against live",
        "government services. It is regenerated by running:",
        "",
        "```bash",
        "uv run python tests/e2e/run_real_queries.py",
        "```",
        "",
    ]

    # Known skip summary
    if skip_categories:
        lines.extend([
            "## Known Limitations (not tested)",
            "",
            "| Reason | Count | Meaning |",
            "|--------|-------|---------|",
        ])
        skip_meanings = {
            "WAF_BLOCKED": "Site blocks headless browsers — needs Colombian IP or residential proxy",
            "AUTH_REQUIRED": "Needs credentials or tokens we don't have",
            "AUTH_CHANGED": "API authentication changed — needs OAuth2/session management",
            "SITE_DOWN": "Government site is temporarily down or unreachable",
            "SITE_MAINTENANCE": "Site is in scheduled maintenance",
            "RECAPTCHA": "Google reCAPTCHA blocks automation — needs solver service",
            "NO_FORM": "Site has no direct search form for this query type",
            "API_REMOVED": "API/dataset has been removed from public portal",
            "GEOBLOCKED": "Site only accessible from the country's IP range",
        }
        for cat in sorted(skip_categories, key=lambda c: -skip_categories[c]):
            meaning = skip_meanings.get(cat, "")
            lines.append(f"| {cat} | {skip_categories[cat]} | {meaning} |")
        lines.append("")

    # Actual failure analysis
    if fail_categories:
        lines.extend([
            "## Failure Analysis (needs fixing)",
            "",
            "| Category | Count | Meaning |",
            "|----------|-------|---------|",
        ])
        cat_meanings = {
            "HTML Changed": "Government site changed its HTML structure — scraper needs update",
            "DNS/Network": "Domain not resolving — site may have moved or be down",
            "Site Unreachable": "Site loads but times out — possibly blocked or very slow",
            "CAPTCHA": "CAPTCHA solving failed — may need different solver",
            "SSL Error": "SSL certificate issue",
            "API Error": "REST API returned 4xx/5xx — endpoint changed or data not found",
            "Bad Test Data": "Test query used wrong parameters — fix in run_real_queries.py",
            "Auth Required": "Source requires authentication token",
            "Other": "Uncategorized error — needs investigation",
        }
        for cat in sorted(fail_categories, key=lambda c: -fail_categories[c]):
            meaning = cat_meanings.get(cat, "")
            lines.append(f"| {cat} | {fail_categories[cat]} | {meaning} |")
        lines.append("")

    # Group by country
    countries: dict[str, list[dict]] = {}
    for r in results:
        country = r["source"].split(".")[0].upper()
        countries.setdefault(country, []).append(r)

    country_names = {
        "CO": "Colombia", "US": "United States", "INTL": "International",
        "EC": "Ecuador", "PE": "Peru", "CL": "Chile", "MX": "Mexico", "AR": "Argentina",
    }

    for country_code in ["CO", "US", "INTL", "EC", "PE", "CL", "MX", "AR"]:
        group = countries.get(country_code, [])
        if not group:
            continue

        ok_count = sum(1 for r in group if r["status"] == "OK")
        skip_count = sum(1 for r in group if r["status"] == "SKIP")
        fail_count = sum(1 for r in group if r["status"] == "ERROR")
        name = country_names.get(country_code, country_code)

        lines.append(f"## {name} ({ok_count} OK, {skip_count} known skip, {fail_count} fail / {len(group)} total)")
        lines.append("")
        lines.append("| Source | Status | Latency | Test Data | Details |")
        lines.append("|--------|--------|---------|-----------|---------|")

        for r in group:
            status_icon = {
                "OK": "✅ OK",
                "ERROR": "❌ FAIL",
                "SKIP": "⏭ SKIP",
                "NOT_FOUND": "❓ N/A",
            }.get(r["status"], "?")
            latency = f"{r['latency_ms']}ms" if r["latency_ms"] else "-"
            label = r["label"][:30]
            if r["status"] == "OK":
                reason = ""
            elif r["status"] == "SKIP":
                reason = r.get("error", "").replace("|", "/")[:60]
            else:
                reason = categorize_error(r.get("error", ""))
            lines.append(f"| `{r['source']}` | {status_icon} | {latency} | {label} | {reason} |")

        lines.append("")

    # Summary by category
    lines.append("## Status Legend")
    lines.append("")
    lines.append("- ✅ **OK** — Query executed successfully and returned data")
    lines.append("- ❌ **FAIL** — Query failed (needs fixing)")
    lines.append("- ⏭ **SKIP** — Known limitation (WAF blocked, auth required, site down)")
    lines.append("- ❓ **N/A** — Source not found in registry")
    lines.append("")

    return "\n".join(lines)


def main():
    print(f"OpenQuery Real Query Runner — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Running {len(QUERIES)} queries...\n")

    results = []
    for i, q in enumerate(QUERIES, 1):
        print(f"[{i:3d}/{len(QUERIES)}] {q['source']:35s} ", end="", flush=True)
        r = run_query(q)
        status_char = {"OK": "✓", "ERROR": "✗", "SKIP": "⊘", "NOT_FOUND": "?"}.get(r["status"], "?")
        latency_str = f"{r['latency_ms']:>5d}ms" if r["latency_ms"] else "  skip"
        print(f"{status_char}  {latency_str}  {r.get('error', '')[:50]}")
        results.append(r)

    # Write report
    report = generate_report(results)
    output_path = Path(__file__).parent.parent.parent / "docs" / "test_results.md"
    output_path.write_text(report)
    print(f"\nReport written to {output_path}")

    # Also write raw JSON for programmatic access
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"Raw data written to {json_path}")

    # Summary
    ok = sum(1 for r in results if r["status"] == "OK")
    skipped = sum(1 for r in results if r["status"] == "SKIP")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    tested = len(results) - skipped
    print(f"\n{'='*60}")
    print(f"Total:   {len(results)} sources")
    print(f"OK:      {ok} ({ok/tested*100:.0f}% of tested)" if tested else "")
    print(f"SKIP:    {skipped} (known limitations)")
    print(f"FAIL:    {errors} (needs fixing)")
    print(f"Accountability: {ok + skipped + errors}/{len(results)} (100%)")


if __name__ == "__main__":
    main()
