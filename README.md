# Submittal Extractor

AI-powered extraction of product variants from construction submittal PDFs using a two-stage LLM+Vision pipeline.

### Python Requirements

- Python 3.9+
- Dependencies listed in `requirements.txt`

## Setup

### 1. Install System Dependencies

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# CentOS/RHEL  
sudo yum install poppler-utils
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and set your API keys:

```bash
cp .env.example .env
```

Edit `.env` file:

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DATALAB_API_KEY=your_datalab_api_key_here
ANTHROPIC_MODEL=claude-sonnet-4-20250514
LOGFIRE_TOKEN=your_logfire_token_here  # Optional
```

## Usage

### Command Line Interface

```bash
python cli.py path/to/document.pdf
```

### Web Dashboard

```bash
python gradio_app.py
```

Then open http://localhost:7860 in your browser.

### Quick Start

1. Install system deps and Python packages
2. Configure environment
   - Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`, `DATALAB_API_KEY` (optional: `ANTHROPIC_MODEL`)
3. Run
   - CLI: `python cli.py path/to/document.pdf`
   - Dashboard: `python gradio_app.py` and open `http://localhost:7860`
   - The dashboard accepts any PDF via the Upload control and shows pages, stage outputs, and final results.

### Python API

```python
from src.pipeline import SubmittalExtractor

extractor = SubmittalExtractor()
products = extractor.extract_products("document.pdf")
```

## Architecture

Two-stage AI pipeline:

1. **Stage 1**: High-recall candidate extraction (LLM)
2. **Stage 2**: Visual selection judgment (Multimodal LLM)

See `ARCHITECTURE.md` for detailed system design and Mermaid diagrams.

### Pipeline Overview

1. **Stage 1**: Extracts all product variants from document text (high recall)
2. **Stage 2**: Uses vision to identify which variants have visual selection marks
3. **Evaluation**: Compares results against ground truth (when available)

Supported annotation types:

- Highlights (most common)
- Boxes
- Circles
- (any many more that Claude Sonnet 4 can understand )

## Features

- Two-stage extraction pipeline (candidate + visual selection)
- Supports highlights, boxes, circles annotations
- Real-time evaluation with ground truth
- Modular, production-ready architecture
- Caching for cost optimization
- Logfire integration for observability

## Troubleshooting

- Poppler / pdf2image
  - Check Poppler: `which pdftoppm` should print a path
  - If missing, install Poppler (see System Requirements)
  - Ensure Python deps installed: `pip install -r requirements.txt`
- Environment variables
  - Quick check:
    ```bash
    python -c "import os; from dotenv import load_dotenv; load_dotenv();\
    print(bool(os.getenv('ANTHROPIC_API_KEY')), bool(os.getenv('DATALAB_API_KEY')), os.getenv('ANTHROPIC_MODEL'))"
    ```
- Dashboard accepts any PDF
  - Use the Upload control to select any local PDF; results and images will render on completion.
