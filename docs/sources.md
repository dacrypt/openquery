# Sources Guide

For the current America-first rollout, the machine-readable inventory/status snapshot is tracked in
`docs/americas-source-inventory.json`. It currently tracks **282** Americas runtime connectors
across **17** countries, with explicit rollout statuses (`implemented`, `broken`, `blocked`, `excluded`, `queued`). Use it to see current America coverage and to keep
future source-expansion work explicit.

Public inventory counts in this guide are derived from the America snapshot. Callable `INTL`
runtime connectors remain outside the America completeness contract until a separate global
inventory contract is introduced. `docs/test_results.md` is a live accountability report and is not
the source of truth for inventory counts.

OpenQuery includes built-in runtime sources across the Americas plus callable `INTL` connectors.
Sources are organized by country with categories like identity, judicial, tax/business, vehicles,
and compliance.

## co.simit — Traffic Fines

**Website:** [simit.org.co](https://www.simit.org.co/)

Queries the SIMIT (Sistema Integrado de Multas e Infracciones de Transito) for traffic violations, fines, and payment status.

```bash
# By cedula
openquery query co.simit --cedula 12345678

# By license plate
openquery query co.simit --placa ABC123
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `comparendos` | int | Number of traffic violations |
| `multas` | int | Number of fines |
| `acuerdos_pago` | int | Number of payment agreements |
| `total_deuda` | float | Total outstanding debt (COP) |
| `paz_y_salvo` | bool | True if no pending fines |
| `historial` | list | Payment history |

**Requirements:** None (no CAPTCHA, no API keys)

---

## co.runt — Vehicle Registry

**Website:** [portalpublico.runt.gov.co](https://portalpublico.runt.gov.co/)

Queries the RUNT (Registro Unico Nacional de Transito) for vehicle information, SOAT insurance, RTM inspection, and ownership.

```bash
# By license plate
openquery query co.runt --placa ABC123

# By VIN
openquery query co.runt --vin 5YJ3E1EA1PF000001

# By cedula (owner lookup)
openquery query co.runt --cedula 12345678
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `placa` | str | License plate |
| `marca` | str | Brand |
| `linea` | str | Model line |
| `modelo_ano` | str | Model year |
| `color` | str | Color |
| `tipo_servicio` | str | Service type (particular/publico) |
| `clase_vehiculo` | str | Vehicle class |
| `tipo_combustible` | str | Fuel type |
| `cilindraje` | str | Engine displacement |
| `estado` | str | Registration status |
| `soat_vigente` | bool | SOAT insurance active |
| `soat_vencimiento` | str | SOAT expiration date |
| `tecnomecanica_vigente` | bool | RTM inspection active |
| `tecnomecanica_vencimiento` | str | RTM expiration date |

**Requirements:** At least one OCR engine for image CAPTCHA (see [CAPTCHA Guide](captcha.md))

---

## co.procuraduria — Disciplinary Records

**Website:** [procuraduria.gov.co](https://www.procuraduria.gov.co/)

Queries the Procuraduria General de la Nacion for disciplinary records (antecedentes disciplinarios). Reports whether a person has active disciplinary sanctions.

```bash
openquery query co.procuraduria --cedula 12345678
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `cedula` | str | Document number queried |
| `tiene_antecedentes` | bool | True if active records found |
| `mensaje` | str | Official result message |

**Requirements:** LLM backend for knowledge CAPTCHAs. The Procuraduria uses math and general knowledge questions instead of image CAPTCHAs. You need at least one of:

- Ollama running locally (`ollama pull llama3.2:1b`)
- `HF_TOKEN` for HuggingFace
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`

---

## co.policia — Criminal Background

**Website:** [policia.gov.co](https://www.policia.gov.co/)

Queries the Colombian National Police for criminal background records (antecedentes penales).

```bash
openquery query co.policia --cedula 12345678
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `cedula` | str | Document number queried |
| `tiene_antecedentes` | bool | True if active records found |
| `mensaje` | str | Official result message |

**Requirements:** None

---

## co.adres — Health System Enrollment (**Deprecated**)

> **Deprecated (2026-04):** aplicaciones.adres.gov.co returns 403 Forbidden — blocked by WAF.

**Website:** [adres.gov.co](https://www.adres.gov.co/)

Previously queried ADRES for health system enrollment status. This source is currently non-functional due to WAF blocking.

**Requirements:** None

---

# Vehicle & Transport Sources

These sources query open data APIs and require **no browser** — responses are instant.

---

## co.pico_y_placa — Driving Restrictions

**Pure logic** — no network calls, instant response.

Calculates whether a vehicle is restricted from driving based on its license plate, city, and date. Supports Bogota, Medellin, and Cali with their respective 2026 rules. Includes Colombian public holidays.

```bash
# Is my plate restricted today in Bogota?
openquery query co.pico_y_placa --placa ABC123

# Check a specific city and date
openquery query co.pico_y_placa --placa ABC123 \
  --extra '{"ciudad": "medellin", "fecha": "2026-04-06"}'
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `placa` | str | License plate queried |
| `ultimo_digito` | str | Last digit of plate |
| `ciudad` | str | City (bogota, medellin, cali) |
| `fecha` | str | Date queried (ISO format) |
| `restringido` | bool | True if driving is restricted |
| `horario` | str | Restriction hours (e.g., "6:00-21:00") |
| `motivo` | str | Why restricted or allowed |
| `exento` | bool | True if exempt (EV/hybrid) |

**City rules:**

| City | System | Hours | Schedule |
|------|--------|-------|----------|
| Bogota | Par/impar by calendar day | 6AM-9PM | Even day: 1-5 restricted; Odd: 6-0 |
| Medellin | Fixed rotation by weekday | 5AM-8PM | Mon:1,7 Tue:0,3 Wed:4,6 Thu:5,9 Fri:2,8 |
| Cali | Fixed rotation by weekday | 6AM-7PM | Mon:1,2 Tue:3,4 Wed:5,6 Thu:7,8 Fri:9,0 |

**Requirements:** None

---

## co.peajes — Toll Road Tariffs

**Data source:** [datos.gov.co](https://www.datos.gov.co/resource/7gj8-j6i3.json) (ANI)

Queries toll booth tariffs from the Agencia Nacional de Infraestructura. Returns prices by vehicle category for all concession tolls in Colombia.

```bash
# All tolls
openquery query co.peajes --custom tolls

# Filter by toll name
openquery query co.peajes --custom tolls --extra '{"peaje": "ALVARADO"}'

# Filter by vehicle category (I-VII)
openquery query co.peajes --custom tolls --extra '{"categoria": "I"}'
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `peaje` | str | Toll booth name |
| `categoria` | str | Vehicle category (I-VII) |
| `valor` | int | Toll price in COP |
| `fecha_actualizacion` | str | Last price update |
| `resultados` | list | All matching toll records |

**Requirements:** None (API-based)

---

## co.combustible — Fuel Prices

**Data source:** [datos.gov.co](https://www.datos.gov.co/resource/gjy9-tpph.json)

Queries gasoline and diesel prices by city, station, and brand.

```bash
# Fuel prices in Bogota
openquery query co.combustible --custom fuel \
  --extra '{"municipio": "BOGOTA"}'

# Filter by department
openquery query co.combustible --custom fuel \
  --extra '{"departamento": "ANTIOQUIA"}'

# Filter by fuel type
openquery query co.combustible --custom fuel \
  --extra '{"producto": "GASOLINA CORRIENTE OXIGENADA"}'
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `departamento` | str | Department name |
| `municipio` | str | Municipality name |
| `estaciones` | list | Stations with name, brand, address, product, price |
| `total_estaciones` | int | Number of stations returned |

**Requirements:** None (API-based)

---

## co.estaciones_ev — EV Charging Stations

**Data source:** [datos.gov.co](https://www.datos.gov.co/resource/qqm3-dw2u.json) (EPM)

Queries the registry of electric vehicle charging stations with location, connector type, and operating hours.

```bash
# All EV stations
openquery query co.estaciones_ev --custom ev

# Filter by city
openquery query co.estaciones_ev --custom ev \
  --extra '{"ciudad": "Medellin"}'
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `ciudad` | str | City name |
| `estaciones` | list | Stations: name, address, type (rapida/semi-rapida), hours, connector, lat, lon |
| `total` | int | Number of stations returned |

**Requirements:** None (API-based)

---

## co.siniestralidad — Road Crash Hotspots

**Data source:** [datos.gov.co](https://www.datos.gov.co/resource/rs3u-8r4q.json) (ANSV)

Queries critical road safety sectors from the Agencia Nacional de Seguridad Vial. Returns crash hotspots with fatality counts and geospatial data.

```bash
# By department
openquery query co.siniestralidad --custom stats \
  --extra '{"departamento": "CUNDINAMARCA"}'

# By municipality
openquery query co.siniestralidad --custom stats \
  --extra '{"municipio": "BOGOTA"}'
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `departamento` | str | Department name |
| `municipio` | str | Municipality name |
| `sectores` | list | Hotspots: road name, fatalities, lat/lon, km marker |
| `total_sectores` | int | Number of critical sectors |
| `total_fallecidos` | int | Total fatalities across sectors |

**Requirements:** None (API-based)

---

## co.vehiculos — National Vehicle Fleet

**Data source:** [datos.gov.co](https://www.datos.gov.co/resource/g7i9-xkxz.json) (RUNT open data)

Queries the national vehicle fleet registry (40M+ records) from datos.gov.co. Look up vehicles by plate or search by brand.

```bash
# Lookup by plate
openquery query co.vehiculos --placa ABC123

# Search by brand (e.g., find all Teslas in Colombia)
openquery query co.vehiculos --custom brand \
  --extra '{"marca": "TESLA"}'
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `placa` | str | License plate |
| `clase` | str | Vehicle class (AUTOMOVIL, CAMIONETA, etc.) |
| `marca` | str | Brand |
| `modelo` | str | Model year |
| `servicio` | str | Service type (PARTICULAR, PUBLICO) |
| `cilindraje` | int | Engine displacement (cc) |
| `resultados` | list | All matching records |
| `total` | int | Number of results |

**Requirements:** None (API-based)

---

## co.fasecolda — Vehicle Reference Prices

**Website:** [fasecolda.com](https://www.fasecolda.com/fasecolda-guia-de-valores/)

Queries the Fasecolda Guia de Valores for official vehicle reference prices. These prices are used by insurance companies, tax authorities, and buyers/sellers across Colombia. Covers 17,000+ vehicle references.

```bash
openquery query co.fasecolda --custom price \
  --extra '{"marca": "TESLA", "modelo": "2026"}'
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `marca` | str | Brand |
| `linea` | str | Model line |
| `modelo` | int | Year |
| `valor` | int | Reference price in COP |
| `cilindraje` | int | Engine displacement |
| `combustible` | str | Fuel type |
| `transmision` | str | Transmission type |
| `puertas` | int | Number of doors |
| `pasajeros` | int | Passenger capacity |
| `codigo_fasecolda` | str | Fasecolda reference code |
| `resultados` | list | All matching references |

**Requirements:** Browser (Playwright)

---

## co.recalls — Vehicle Safety Recalls

**Website:** [SIC](https://sedeelectronica.sic.gov.co/temas/proteccion-al-consumidor/consumo-seguro/campanas-de-seguridad/automotores)

Queries the Superintendencia de Industria y Comercio for active vehicle safety recall campaigns. Search by brand to find affected models and components.

```bash
openquery query co.recalls --custom recall \
  --extra '{"marca": "TESLA"}'
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `marca` | str | Brand searched |
| `modelo` | str | Model (if specified) |
| `total_campanias` | int | Number of active recalls |
| `campanias` | list | Recalls: component, description, affected years, manufacturer URL |

**Requirements:** Browser (Playwright). Note: SIC site may have SSL issues; errors include the manual lookup URL.

---

## Querying multiple sources

**Person background check (all by cedula):**

```bash
openquery query co.simit --cedula 12345678
openquery query co.procuraduria --cedula 12345678
openquery query co.policia --cedula 12345678
openquery query co.adres --cedula 12345678
```

**Vehicle report (all by plate):**

```bash
openquery query co.runt --placa ABC123
openquery query co.pico_y_placa --placa ABC123
openquery query co.vehiculos --placa ABC123
openquery query co.simit --placa ABC123
```

Or via the REST API in parallel — see [API Guide](api.md).

## Common options

```bash
# JSON output (for piping to jq, scripts, etc.)
openquery query co.simit --cedula 12345678 --json

# With audit evidence
openquery query co.runt --placa ABC123 --audit --audit-dir ./evidence
```
