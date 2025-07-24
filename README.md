# Divine Dev - Round 1A: Document Outline Extractor

## Team Info

- **Team Name:** Divine Dev
- **Team Leader:** Ankit Mishra
- **Member:** Amit Kumar

## Overview

A Python tool that extracts structured outlines (Title, H1–H3) with 0-based page numbers from PDFs (≤ 50 pages) and outputs them in JSON format.

## Core Features

- **Title & Heading Detection:** Uses font size, boldness, and layout patterns.
- **Numbered Headings:** Identified via regex (e.g., `1.1 Introduction`).
- **Unnumbered Headings:** Detected using boldness, font thresholds, spacing, and alignment.
- **Fast & Lightweight:** Processes 50 pages in ≤ 10s. No ML, GPU, or internet needed.

## Tech Stack

- **Library:** `PyMuPDF (fitz)`
- **Python Built-ins:** `re`, `json`, `os`, `collections`

## 🐳 Run with Docker

### 1. Prepare Files

Ensure your project has:

- `main.py` – solution code
- `Dockerfile`
- `requirements.txt`:

```txt
PyMuPDF==1.23.8
```

### 2. Build Image

```bash
docker build --platform linux/amd64 -t adobe_doc_parser:v1 .
```

### 3. Run Container

```bash
docker run --rm -v "$(pwd)/input":/app/input -v "$(pwd)/output":/app/output --network none adobe_doc_parser:v1
```

Processes every `filename.pdf` from `/input` and outputs `filename.json` to `/output`.

## 🧪 System Compatibility

- **CPU-only**, **no internet**
- Tested on `AMD64`, 8-core CPU, 16 GB RAM
