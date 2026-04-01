# Getting Started

This guide walks you through installing OpenQuery and running your first consultation.

## 1. Install OpenQuery

```bash
pip install openquery
```

Or with [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv add openquery
```

## 2. Install Playwright browsers

OpenQuery uses Playwright for browser automation. Install Chromium:

```bash
playwright install chromium
```

## 3. Install a CAPTCHA engine

Some sources (like RUNT) require solving image CAPTCHAs. Install at least one engine:

```bash
# Option A: PaddleOCR (recommended — 100% accuracy)
pip install "openquery[paddleocr]"

# Option B: Tesseract (included by default, 80% accuracy)
# macOS
brew install tesseract
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Option C: EasyOCR (85% alone, 90% combined with Tesseract)
pip install "openquery[easyocr]"
```

OpenQuery auto-detects installed engines and builds the best solver chain automatically.

## 4. Run your first query

```bash
# Check what sources are available
openquery sources

# Query traffic fines
openquery query co.simit --cedula 12345678

# Query vehicle registry
openquery query co.runt --placa ABC123

# Get JSON output
openquery query co.simit --cedula 12345678 --json
```

## 5. (Optional) Set up LLM for knowledge CAPTCHAs

The Procuraduria source uses knowledge-based CAPTCHAs ("What is the capital of Antioquia?"). You need an LLM backend:

```bash
# Option A: Ollama (free, local, recommended)
# Install from https://ollama.com
ollama pull llama3.2:1b

# Option B: HuggingFace (free tier)
export HF_TOKEN="hf_your_token_here"

# Option C: Anthropic (paid)
export ANTHROPIC_API_KEY="sk-ant-..."

# Option D: OpenAI (paid)
export OPENAI_API_KEY="sk-..."
```

Then query:

```bash
openquery query co.procuraduria --cedula 12345678
```

## 6. Try the instant vehicle/transport sources

These sources use open data APIs — no browser or CAPTCHA needed:

```bash
# Is my plate restricted today? (pure logic, instant)
openquery query co.pico_y_placa --placa ABC123

# Vehicle fleet lookup by plate
openquery query co.vehiculos --placa ABC123

# Toll tariffs
openquery query co.peajes --custom tolls --extra '{"peaje": "ALVARADO"}'

# Fuel prices in Bogota
openquery query co.combustible --custom fuel --extra '{"municipio": "BOGOTA"}'

# EV charging stations in Medellin
openquery query co.estaciones_ev --custom ev --extra '{"ciudad": "Medellin"}'

# Road crash hotspots
openquery query co.siniestralidad --custom stats \
  --extra '{"departamento": "CUNDINAMARCA"}'
```

## 7. (Optional) Generate audit evidence

For compliance, generate screenshots and PDF reports:

```bash
openquery query co.runt --placa ABC123 --audit --audit-dir ./evidence
```

This creates:
```
evidence/
  co.runt_ABC123_20260331_103000/
    report.pdf              # Full evidence report
    screenshot_form.png     # Screenshot of the form
    screenshot_result.png   # Screenshot of the result
    metadata.json           # Query metadata (no base64 blobs)
```

## Next steps

- [Sources Guide](sources.md) — detailed documentation for each data source
- [CAPTCHA Guide](captcha.md) — deep dive into OCR engines and configuration
- [Audit Guide](audit.md) — evidence system for compliance workflows
- [API Guide](api.md) — REST API reference and deployment
