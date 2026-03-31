# Sources Guide

OpenQuery includes 5 built-in sources for Colombian public data. Each source handles browser automation, CAPTCHA solving, and response parsing automatically.

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
| `total_deuda` | float | Total outstanding debt (COP) |
| `paz_y_salvo` | bool | True if no pending fines |
| `detalles` | list | Individual fine details |
| `historial` | list | Payment history |

**Requirements:** None (no CAPTCHA, no API keys)

---

## co.runt — Vehicle Registry

**Website:** [runt.gov.co](https://www.runt.gov.co/)

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
| `modelo` | int | Year |
| `color` | str | Color |
| `servicio` | str | Service type (particular/publico) |
| `clase` | str | Vehicle class |
| `combustible` | str | Fuel type |
| `cilindraje` | str | Engine displacement |
| `estado` | str | Registration status |
| `soat_vigente` | bool | SOAT insurance active |
| `soat_vencimiento` | str | SOAT expiration date |
| `rtm_vigente` | bool | RTM inspection active |
| `rtm_vencimiento` | str | RTM expiration date |

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

## co.adres — Health System Enrollment

**Website:** [adres.gov.co](https://www.adres.gov.co/)

Queries ADRES (Administradora de los Recursos del SGSS) for health system enrollment status, including EPS affiliation and coverage regime.

```bash
openquery query co.adres --cedula 12345678
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `cedula` | str | Document number queried |
| `afiliado` | bool | True if enrolled in health system |
| `eps` | str | EPS name (health insurer) |
| `regimen` | str | Coverage regime (contributivo/subsidiado) |
| `estado` | str | Enrollment status |
| `mensaje` | str | Additional details |

**Requirements:** None

---

## Querying all sources

You can query multiple sources for the same person:

```bash
# One by one
openquery query co.simit --cedula 12345678
openquery query co.procuraduria --cedula 12345678
openquery query co.policia --cedula 12345678
openquery query co.adres --cedula 12345678
```

Or via the REST API in parallel — see [API Guide](api.md).

## Common options

```bash
# JSON output (for piping to jq, scripts, etc.)
openquery query co.simit --cedula 12345678 --json

# With audit evidence
openquery query co.runt --placa ABC123 --audit --audit-dir ./evidence
```
