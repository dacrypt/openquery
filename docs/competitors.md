# Competitive Landscape: OpenQuery vs Alternatives

> Last updated: 2026-04-01

## Tools Overview

### Open Source

| Tool | Language | Countries | Sources | URL |
|------|----------|-----------|---------|-----|
| **OpenQuery** | Python | CO, EC, PE, CL, MX, AR, US, INTL | 100+ | github.com/dacrypt/openquery |
| **peru-consult** | PHP | PE | ~3 | github.com/giansalex/peru-consult |
| **ConsultaCiudadano** | Python/Django | CO | ~5 | github.com/cizaquita |
| **OSINT_in_Colombia** | Link catalog | CO + LATAM | N/A | github.com/BeHackerPro |
| **SpiderFoot** | Python | Global | Generic OSINT | spiderfoot.net |

### Commercial (LATAM-focused)

| Tool | Countries | Est. Sources | Focus | URL |
|------|-----------|-------------|-------|-----|
| **Verifik** | CO, MX, PE, CL, AR, UY, BR, ES | 50+ | KYC/KYB/AML, deep CO | verifik.co |
| **Apitude** | CO, PE, MX, CL | 30+ | Gov API wrapper (closest to OQ) | apitude.co |
| **Truora** | CO, MX, PE, CL, BR, CR, SV | 100+ | Background checks, API-first | truora.com |
| **MetaMap/Incode** | 20+ LATAM | 350+ | GovChecks, ID verification | metamap.com |
| **TusDatos** | CO | 300+ | Judicial/criminal records CO | tusdatos.co |
| **Emptor** | PE, CO, MX, PA, CL, EC, BR, CR | 500+ | ML background checks | emptor.io |
| **Syncfy** | MX, BR, GT, PE, BO, SV | 74+ inst. | Fiscal/SAT, open banking | syncfy.com |
| **Floid** | CL | ~10 | SII, civil registry, CMF | floid.io |
| **Nubarium** | MX | ~15 | CURP, RFC, INE, IMSS bots | nubarium.com |
| **Moffin** | MX | ~10 | Credit bureau + SAT | moffin.mx |

### Commercial (Global with LATAM coverage)

| Tool | LATAM Countries | Focus |
|------|----------------|-------|
| **Trulioo** | ~10 | Global KYC |
| **Sumsub** | ~15 | Global KYC/AML |
| **Jumio** | ~10 | ID verification |

---

## Source Coverage Matrix by Country

### Colombia (CO)

| Category / Source | OpenQuery | Verifik | Apitude | Truora | MetaMap | TusDatos |
|-------------------|:---------:|:-------:|:-------:|:------:|:-------:|:--------:|
| **IDENTITY** | | | | | | |
| Registraduria (cedula status) | Y | Y | Y | Y | Y | Y |
| Full name by cedula | Y | Y | Y | Y | Y | Y |
| Cedula extranjeria | Y | Y | ? | Y | Y | Y |
| Voting station | Y | Y | ? | ? | ? | ? |
| Civil registry / death records | Y | ? | ? | ? | ? | ? |
| Military booklet | Y | ? | ? | ? | ? | ? |
| Migration PPT | Y | ? | ? | ? | ? | ? |
| **BACKGROUND CHECKS** | | | | | | |
| National Police | Y | Y | Y | Y | Y | Y |
| Procuraduria | Y | Y | Y | Y | Y | Y |
| Contraloria | Y | Y | Y | Y | Y | Y |
| RNMC (corrective measures) | Y | Y | ? | Y | ? | Y |
| INPEC (prison system) | Y | ? | ? | ? | ? | Y |
| Judicial processes (Rama Judicial) | Y | ? | ? | Y | ? | Y |
| JEP (transitional justice) | Y | ? | ? | ? | ? | ? |
| Tutelas | Y | ? | ? | ? | ? | ? |
| **COMPLIANCE / AML** | | | | | | |
| PEP (politically exposed persons) | Y | Y | ? | Y | Y | Y |
| DIAN fictitious providers | Y | ? | ? | ? | ? | Y |
| RNE (do not call registry) | Y | ? | ? | ? | ? | ? |
| OFAC / UN sanctions | Y | Y | ? | Y | Y | Y |
| **TAX & BUSINESS** | | | | | | |
| DIAN RUT | Y | Y | Y | Y | Y | Y |
| RUES (business registry) | Y | Y | ? | Y | Y | Y |
| SECOP (public procurement) | Y | ? | ? | ? | ? | Y |
| CUFE (electronic invoices) | Y | ? | ? | ? | ? | ? |
| Camara de Comercio Medellin | Y | ? | ? | ? | ? | ? |
| eInforma | Y | ? | ? | ? | ? | ? |
| Directorio Empresas | Y | ? | ? | ? | ? | ? |
| Google Maps businesses | Y | ? | ? | ? | ? | ? |
| **VEHICLES** | | | | | | |
| RUNT (plate/owner) | Y | Y | Y | ? | Y | ? |
| RUNT driver (license) | Y | Y | ? | ? | ? | ? |
| SOAT (insurance) | Y | Y | ? | ? | ? | ? |
| RTM (vehicle inspection) | Y | ? | ? | ? | ? | ? |
| SIMIT (traffic fines) | Y | Y | Y | Y | ? | Y |
| Comparendos (violations) | Y | ? | ? | Y | ? | Y |
| FASECOLDA (reference prices) | Y | ? | ? | ? | ? | ? |
| Pico y placa | Y | ? | ? | ? | ? | ? |
| Vehicle retention | Y | ? | ? | ? | ? | ? |
| Fuel prices | Y | ? | ? | ? | ? | ? |
| EV charging stations | Y | ? | ? | ? | ? | ? |
| Recalls | Y | ? | ? | ? | ? | ? |
| Crash hotspots | Y | ? | ? | ? | ? | ? |
| Tolls | Y | ? | ? | ? | ? | ? |
| Fleet data | Y | ? | ? | ? | ? | ? |
| **SOCIAL SECURITY** | | | | | | |
| ADRES (health enrollment) | Y | Y | ? | ? | Y | Y |
| Colpensiones (pensions) | Y | ? | ? | ? | ? | Y |
| RUAF (affiliates) | Y | ? | ? | ? | ? | Y |
| SISBEN (socioeconomic) | Y | Y | ? | ? | Y | Y |
| RETHUS (health workforce) | Y | ? | ? | ? | ? | ? |
| SOI (parafiscal payments) | Y | ? | ? | ? | ? | Y |
| FOPEP (pension payroll) | Y | ? | ? | ? | ? | ? |
| Seguridad social integrada | Y | ? | ? | ? | ? | ? |
| Compensation fund affiliates | Y | ? | ? | ? | ? | ? |
| Health provider licenses | Y | ? | ? | ? | ? | ? |
| **PROPERTY** | | | | | | |
| SNR (property index) | Y | ? | ? | ? | ? | ? |
| Certificado tradicion y libertad | Y | ? | ? | ? | ? | ? |
| Garantias mobiliarias | Y | ? | ? | ? | ? | ? |
| Cambio de estrato | Y | ? | ? | ? | ? | ? |
| **PROFESSIONAL COUNCILS** | | | | | | |
| COPNIA (engineering) | Y | ? | ? | ? | ? | Y |
| CONALTEL (electrical tech) | Y | ? | ? | ? | ? | ? |
| Consejo Mecanica | Y | ? | ? | ? | ? | ? |
| CPAE (business admin) | Y | ? | ? | ? | ? | ? |
| CPIP (petroleum) | Y | ? | ? | ? | ? | ? |
| CPIQ (chemical) | Y | ? | ? | ? | ? | ? |
| CPNAA (architecture) | Y | ? | ? | ? | ? | ? |
| CPNT (topography) | Y | ? | ? | ? | ? | ? |
| CPBiol (biology) | Y | ? | ? | ? | ? | ? |
| Veterinario | Y | ? | ? | ? | ? | ? |
| URNA (law professionals) | Y | ? | ? | ? | ? | ? |
| **OTHER** | | | | | | |
| Mi Casa Ya (housing subsidies) | Y | ? | ? | ? | ? | ? |
| Tarifas energia | Y | ? | ? | ? | ? | ? |
| RNT Turismo | Y | ? | ? | ? | ? | ? |

### Peru (PE)

| Source | OpenQuery | peru-consult | Apitude | Truora | MetaMap | Emptor |
|--------|:---------:|:------------:|:-------:|:------:|:-------:|:------:|
| SUNAT (RUC) | Y | Y | Y | Y | Y | Y |
| RENIEC (DNI) | - | Y | Y | Y | Y | Y |
| Poder Judicial | Y | - | - | Y | - | Y |
| SUNARP (vehicles/property) | Y | - | Y | - | - | Y |
| Sanctions / PEP | Y | - | - | Y | Y | Y |

### Mexico (MX)

| Source | OpenQuery | Nubarium | Syncfy | Moffin | MetaMap | Truora |
|--------|:---------:|:--------:|:------:|:------:|:-------:|:------:|
| CURP / RENAPO | Y | Y | - | - | Y | Y |
| SAT (RFC) | Y | Y | Y | Y | Y | - |
| SIEM (business registry) | Y | - | - | - | - | - |
| Repuve (vehicles) | Y | - | - | - | - | - |
| INE | - | Y | - | - | Y | - |
| IMSS / ISSSTE | - | Y | - | - | - | - |
| Buro de credito | - | - | - | Y | - | - |
| CFDI (invoices) | - | - | Y | - | - | - |

### Ecuador (EC)

| Source | OpenQuery | MetaMap | Truora |
|--------|:---------:|:-------:|:------:|
| SRI (RUC / tax) | Y | Y | Y |
| ANT (traffic) | Y | - | - |
| CNE (voter registry) | Y | - | - |
| Funcion Judicial | Y | - | Y |
| IESS (social security) | Y | - | - |
| Registro Civil | Y | Y | - |

### Chile (CL)

| Source | OpenQuery | Floid | MetaMap |
|--------|:---------:|:-----:|:-------:|
| SII (RUT / tax) | Y | Y | Y |
| Poder Judicial | Y | - | - |
| Traffic fines | Y | - | - |
| Registro Civil | - | Y | Y |
| CMF (financial) | - | Y | - |

### Argentina (AR)

| Source | OpenQuery | MetaMap | Truora |
|--------|:---------:|:-------:|:------:|
| AFIP (CUIT / tax) | Y | Y | Y |
| Poder Judicial | Y | - | - |
| DNRPA (vehicles) | Y | - | - |

### USA / International

| Source | OpenQuery | MetaMap | Truora |
|--------|:---------:|:-------:|:------:|
| NHTSA (VIN decode/recalls) | Y | - | - |
| OFAC sanctions | Y | Y | Y |
| EPA fuel economy | Y | - | - |
| UN sanctions | Y | Y | Y |
| MarineTraffic (vessels) | Y | - | - |

---

## Summary Comparison

| Dimension | OpenQuery | Verifik | Apitude | Truora | MetaMap | TusDatos |
|-----------|:---------:|:-------:|:-------:|:------:|:-------:|:--------:|
| **Type** | OSS | Commercial | Commercial | Commercial | Commercial | Commercial |
| **Total sources** | 100+ | 50+ | 30+ | 100+ | 350+ | 300+ |
| **Countries** | 8 | 8 | 4 | 7 | 20+ | 1 (CO) |
| **CO depth** | +++++ | ++++ | +++ | ++++ | +++ | +++++ |
| **LATAM breadth** | ++++ | +++ | ++ | +++ | +++++ | + |
| **Vehicles** | +++++ | +++ | ++ | ++ | ++ | + |
| **Social security** | +++++ | ++ | + | + | ++ | +++ |
| **Property** | ++++ | + | + | + | + | + |
| **Prof. councils** | +++++ | + | + | + | + | ++ |
| **Biometrics/ID doc** | No | Yes | Yes | Yes | Yes | No |
| **Price** | Free | $$$ | $$ | $$$ | $$$$ | $$ |

---

## OpenQuery Differentiators

1. **Only multi-country OSS tool** -- no other open-source project covers 8 countries
2. **Vehicle depth** -- 15 CO sources (full RUNT, SIMIT, FASECOLDA, pico y placa, EV stations, tolls, recalls)
3. **Social security completeness** -- 10 sources (ADRES, Colpensiones, RUAF, SISBEN, RETHUS, SOI, FOPEP)
4. **11 professional councils** -- no competitor covers this exhaustively
5. **Property records** -- SNR, tradicion y libertad, garantias mobiliarias
6. **Free & self-hosted** -- competitors charge $0.05-$2.00 per query

## Gaps vs Commercial Platforms

1. **Biometric verification** -- no face match or liveness detection
2. **Document OCR** -- no data extraction from document photos
3. **Credit bureaus** -- no Buro de Credito (MX), DataCredito (CO)
4. **SLA/uptime** -- scraping-based, not official API partnerships
5. **Dashboard/UI** -- CLI and REST API only

---

*Legend: Y = confirmed, - = not available, ? = unconfirmed/unclear*
