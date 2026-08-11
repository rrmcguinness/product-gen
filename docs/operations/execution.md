# Execution Guide

---

## Standard Production Run

To process all SKUs in the default catalog spreadsheet with 5 worker threads:

```bash
uv run product-gen
```

---

## Execution Recipes

### 1. Test Run on Subset of SKUs
Process only the first 3 records to verify API credentials and output formats:

```bash
uv run product-gen --max-records 3
```

### 2. High-Throughput Batch Processing
Process records utilizing 8 concurrent threads with custom output directory:

```bash
uv run product-gen \
  --file data/Google_50_skus_image_generation.xlsx \
  --threads 8 \
  --output output/production_batch_01
```

### 3. High-Fidelity Run with Image Description
Extract detailed physical descriptions from reference images to condition prompt generation:

```bash
uv run product-gen \
  --max-records 10 \
  --use-image-description \
  --force
```

### 4. Forcing Complete Regeneration
By default, the pipeline skips products that already have an `index.html` report. Use `--force` to re-execute all stages:

```bash
uv run product-gen --force
```

---

## Standalone Reporting Operations

### Generate Summary Dashboard & PDF
To rebuild reports from an existing output folder without making API calls:

```bash
uv run product-gen-report --dir output/Google_50_skus_image_generation
```

### Generate Visual Product Gallery
To build a glassmorphic catalog showcase:

```bash
uv run product-gen-gallery --dir output/Google_50_skus_image_generation
```

---

## Documentation Operations

### Serve Documentation Locally
Launch the live-reloading MkDocs documentation server:

```bash
uv run docs-serve
```

Navigate to `http://127.0.0.1:8000/` in your browser.

### Build Static Documentation
Compile static HTML assets into the `site/` folder:

```bash
uv run docs-build
```

### Package as Single-File Web Archive / Offline Bundle
Package the entire documentation into single-file portable formats (MHTML, standalone HTML, and ZIP):

```bash
uv run docs-package
```

This generates:
- `product_gen_docs.html`: Standalone single-file HTML bundle with offline SPA navigation (double-click to open in Chrome without a server).
- `product_gen_docs.mhtml`: Native Chrome MHTML Web Archive format.
- `product_gen_docs.zip`: Static site portable ZIP package.

