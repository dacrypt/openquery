# Audit & Evidence Guide

OpenQuery can capture screenshots, network traffic, and generate PDF evidence reports for each query. This is useful for compliance, legal proceedings, and audit trails.

## Quick Start

```bash
# Generate evidence for a RUNT query
openquery query co.runt --placa ABC123 --audit --audit-dir ./evidence
```

## What gets captured

### Screenshots

Automatic screenshots at key stages:

| Stage | When | Purpose |
|-------|------|---------|
| `form_filled` | After filling the form, before submit | Proves what was queried |
| `captcha_attempt_N` | After each CAPTCHA solve attempt | Shows CAPTCHA interaction |
| `result` | After receiving the result | Proves what was returned |
| `error` | On failure | Documents the error state |

### Network Log

Every HTTP request/response during the query:

- Method, URL, headers
- Request body (for POSTs)
- Response status code
- Timing (duration in ms)
- Data URLs (images, fonts) are excluded to keep logs clean

### Integrity Hash

The query result is hashed with SHA-256. This proves the result hasn't been modified after capture. The hash is included in the PDF report and metadata JSON.

### PDF Report

A professional PDF evidence report containing:

- Query metadata (source, document, timestamps)
- Integrity hash
- Formatted query result
- All screenshots (embedded)
- Network log table
- Generation timestamp

## CLI Usage

```bash
# Basic audit
openquery query co.runt --placa ABC123 --audit

# Custom output directory
openquery query co.runt --placa ABC123 --audit --audit-dir /path/to/evidence

# Works with all sources
openquery query co.simit --cedula 12345678 --audit
openquery query co.procuraduria --cedula 12345678 --audit
openquery query co.policia --cedula 12345678 --audit
openquery query co.adres --cedula 12345678 --audit
```

### Output structure

```
evidence/
  co.runt_ABC123_20260331_103000/
    report.pdf              # Full PDF evidence report
    screenshot_form.png     # Form filled screenshot
    screenshot_result.png   # Result screenshot
    metadata.json           # Machine-readable metadata
```

The `metadata.json` contains everything except base64 blobs (screenshots and PDF are saved as separate files):

```json
{
  "id": "a1b2c3d4-...",
  "source": "co.runt",
  "document_number": "****C123",
  "queried_at": "2026-03-31T10:30:00Z",
  "completed_at": "2026-03-31T10:30:12Z",
  "duration_ms": 12345,
  "result_hash": "sha256:ab12cd34...",
  "page_url": "https://www.runt.gov.co/...",
  "screenshots_count": 2,
  "network_requests_count": 15
}
```

## REST API Usage

Include `"audit": true` in the query request:

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "source": "co.runt",
    "document_type": "placa",
    "document_number": "ABC123",
    "audit": true
  }'
```

The response includes an `audit` field with the full audit record:

```json
{
  "ok": true,
  "source": "co.runt",
  "data": { ... },
  "audit": {
    "id": "a1b2c3d4-...",
    "source": "co.runt",
    "result_hash": "sha256:ab12cd34...",
    "screenshots": [
      {
        "label": "form_filled",
        "timestamp": "2026-03-31T10:30:05Z",
        "png_base64": "iVBORw0KGgo...",
        "width": 1280,
        "height": 720
      }
    ],
    "network_log": [ ... ],
    "pdf_base64": "JVBERi0xLjQ..."
  }
}
```

## Python API

```python
from openquery.core.audit import AuditCollector
from openquery.core.browser import BrowserManager

browser = BrowserManager()
async with browser.page() as page:
    collector = AuditCollector(source="co.runt", document="ABC123")
    collector.attach(page)

    # ... perform your query ...

    collector.screenshot(page, "result")
    record = collector.build_record(page, result_data={"placa": "ABC123"})

    # Generate PDF
    pdf_bytes = await collector.generate_pdf(page, record)
```

## Privacy

- Document numbers are automatically masked in metadata: `12345678` becomes `****5678`
- Full document numbers are NOT stored in audit records
- Network request bodies may contain sensitive data — handle audit files accordingly
- Screenshots may show personal information — store securely

## Storage Recommendations

| Scenario | Recommendation |
|----------|---------------|
| Local development | `--audit-dir ./evidence` (gitignored) |
| Production server | S3/GCS bucket with encryption at rest |
| Legal/compliance | Immutable storage with retention policy |
| CI/CD | Artifact upload to pipeline |

Add to `.gitignore`:

```
evidence/
*.pdf
```
