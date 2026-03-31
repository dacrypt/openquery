# CAPTCHA Solving Guide

OpenQuery handles two types of CAPTCHAs automatically:

1. **Image CAPTCHAs** (RUNT) — alphanumeric text in distorted images
2. **Knowledge CAPTCHAs** (Procuraduria) — math and general knowledge questions

## Image CAPTCHA Engines

OpenQuery auto-detects installed OCR engines and builds the best solver chain:

```
PaddleOCR (100%) → VotingSolver(EasyOCR+Tesseract, 90%) → HuggingFace OCR → 2Captcha
```

Each engine is tried in order. If the first succeeds, the rest are skipped. If it fails (wrong answer rejected by server), RUNT retries up to 3 times.

### PaddleOCR (recommended)

**Accuracy: 100%** | **Speed: ~130ms** | **Model size: ~50MB**

Uses Baidu's PP-OCRv5 model, the latest generation of PaddlePaddle OCR. Dramatically outperforms all other engines on RUNT captchas.

```bash
pip install "openquery[paddleocr]"
```

First run downloads models from HuggingFace (~50MB). Subsequent runs use cached models.

### EasyOCR

**Accuracy: 85% alone, 90% with voting** | **Speed: ~110ms** | **Model size: ~30MB**

Uses JaidedAI's CRNN-based model. When combined with Tesseract via the VotingSolver, character-level majority voting pushes accuracy to 90%.

```bash
pip install "openquery[easyocr]"
```

### Tesseract

**Accuracy: 80%** | **Speed: ~390ms** | **Included by default**

Uses Google's Tesseract OCR with multiple preprocessing pipelines (different thresholds, scaling, filters). Included in core dependencies.

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# Fedora/RHEL
sudo dnf install tesseract
```

### HuggingFace OCR (cloud)

Uses `microsoft/trocr-base-printed` via HuggingFace Inference API. Requires `HF_TOKEN`.

```bash
pip install "openquery[huggingface]"
export HF_TOKEN="hf_your_token_here"
```

### 2Captcha (paid, last resort)

Human-powered CAPTCHA solving service. ~$3 per 1000 CAPTCHAs, ~15s per solve.

```bash
pip install "openquery[captcha]"
export TWO_CAPTCHA_API_KEY="your_key_here"
```

## How VotingSolver works

When both EasyOCR and Tesseract are installed, OpenQuery combines them with character-level majority voting:

```
EasyOCR:    "5bc12"
Tesseract:  "Sbc12"
            ─────────
Voted:      position 0: '5' vs 'S' → needs tiebreaker (first wins)
            position 1: 'b' vs 'b' → 'b'
            position 2: 'c' vs 'c' → 'c'
            position 3: '1' vs '1' → '1'
            position 4: '2' vs '2' → '2'
```

With 3 engines, true majority voting works:

```
PaddleOCR:  "5bc12"
EasyOCR:    "5bc12"
Tesseract:  "Sbc12"
            ─────────
Voted:      "5bc12"  (2 vs 1 at position 0)
```

## Knowledge CAPTCHA (LLM)

The Procuraduria source uses text-based CAPTCHAs:

- Math: "Cuanto es 7 x 8?" → "56"
- Names: "Escriba las dos primeras letras del primer nombre" → "DA"
- Knowledge: "Capital de Antioquia?" → "Medellin"

Math and name questions are solved with regex (no LLM needed). Knowledge questions require an LLM backend.

### LLM Backend Priority

```
Regex (math/names) → Ollama (local) → HuggingFace → Anthropic → OpenAI
```

### Ollama (recommended)

Free, local, private. Zero Python dependencies (uses httpx which is already a core dep).

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a small model (~1.3GB)
ollama pull llama3.2:1b

# OpenQuery auto-detects Ollama at localhost:11434
openquery query co.procuraduria --cedula 12345678
```

Custom model or URL:

```python
from openquery.core.llm import OllamaQA
solver = OllamaQA(model="mistral:7b", base_url="http://remote-server:11434")
```

### HuggingFace

Free tier (~30 req/min). Requires signup at [huggingface.co](https://huggingface.co/).

```bash
pip install "openquery[huggingface]"
export HF_TOKEN="hf_..."
```

### Anthropic / OpenAI

Paid APIs. Uses the cheapest models (claude-haiku-4-5-20251001, gpt-4o-mini).

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# or
export OPENAI_API_KEY="sk-..."
```

## Benchmarking

Run the OCR benchmark against real captcha fixtures:

```bash
uv run python tests/e2e/bench_ocr_engines.py
```

Output includes:
- Per-sample accuracy comparison
- Confusion analysis (which characters each engine gets wrong)
- Complementarity analysis (could combining engines help?)
- Speed statistics (avg, P95)

Run diagnostic tests:

```bash
uv run pytest tests/test_captcha_diagnostics.py -v -s
```

## Accuracy Results (20 real RUNT captchas)

| Engine | Exact Match | Char Accuracy | Avg Speed |
|--------|-------------|---------------|-----------|
| PaddleOCR PP-OCRv5 | 20/20 (100%) | 100/100 (100%) | 130ms |
| EasyOCR + Tesseract (voting) | 18/20 (90%) | 96/100 (96%) | 500ms |
| EasyOCR alone | 17/20 (85%) | 93/100 (93%) | 111ms |
| Tesseract (3 pipelines) | 16/20 (80%) | 89/100 (89%) | 393ms |

### Common confusion pairs (Tesseract)

| Expected | Got | Frequency |
|----------|-----|-----------|
| 5 | S | High |
| 8 | B | Medium |
| T | I | Medium |
| c | e | Low |
