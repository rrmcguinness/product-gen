# Walmart Product Generation Pipeline

Automated multimodal SKU enrichment, 2200x2200 studio image generation, likeness evaluation, and reporting pipeline powered by Google Gemini.

## Prerequisites

- Python 3.13
- [uv](https://github.com/astral-sh/uv) for fast, deterministic package management
- Gemini API Key (`GEMINI_API_KEY`) or Google Cloud ADC (`GOOGLE_CLOUD_PROJECT`)

## Installation

```bash
# Clone and sync dependencies
uv sync

# Install editable package
uv pip install -e .
```

## Available Execution Scripts

The project defines executable CLI targets via `pyproject.toml`:

```bash
# 1. Run the end-to-end product generation pipeline
uv run product-gen [options]

# 2. Generate aggregated HTML dashboard and executive PDF report
uv run product-gen-report --dir output/Google_50_skus_image_generation

# 3. Generate responsive glassmorphic product gallery
uv run product-gen-gallery --dir output/Google_50_skus_image_generation

# 4. Launch the MkDocs documentation server (live reload)
uv run docs-serve

# 5. Build the MkDocs documentation site
uv run docs-build

# 6. Package documentation into single-file offline bundles (HTML / MHTML / ZIP)
uv run docs-package
```

### Pipeline Parameters (`product-gen`)

| Parameter | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--file` | `-f` | String | `data/Google_50_skus_image_generation.xlsx` | Path to the product Excel file. |
| `--max-records` | `-n` | Integer | `None` | Strict limit on records to process. |
| `--use-reference-images` | | Flag | `False` | Pass reference images directly to image generator. |
| `--use-image-description` | | Flag | `False` | Generate detailed description from reference images before generation. |
| `--no-product-description` | | Flag | `False` | Exclude product text description from generation prompt. |
| `--force` | | Flag | `False` | Force regeneration of products even if already processed. |
| `--output` | `-o` | String | `None` | Custom output directory path. |
| `--threads` | `-j` | Integer | `None` | Worker threads (overrides `THREAD_POOL_SIZE`). |

## Documentation Site

The full technical workflow, system architecture diagrams, data schemas, and API references are documented in the **MkDocs** site.

To start the documentation server:

```bash
uv run docs-serve
```

Then navigate to `http://127.0.0.1:8000/`.

