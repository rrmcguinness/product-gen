# Product Generation Pipeline

Automated enrichment and image generation pipeline for SKUs.

## Prerequisites

- Python 3.13
- [uv](https://github.com/astral-sh/uv) for dependency management

## Installation

Ensure you have `uv` installed. Then, sync the dependencies:

```bash
uv sync
```

## Usage

Run the pipeline using `uv run`:

```bash
uv run product-gen [options]
```

### Parameters

| Parameter | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--file` | `-f` | String | `data/Google_50_skus_image_generation.xlsx` | Path to the product Excel file. |
| `--max-records` | `-n` | Integer | `None` | Strict limit on records to process. Less than 1 or omitted means all records. |
| `--useReferenceImages` | | Boolean | `True` | Use reference images for generation. Choices: `True`, `False`. |
| `--useImageDescription` | | Boolean | `False` | Generate detailed description from reference images and use for generation. Choices: `True`, `False`. |
| `--force` | | Flag | `False` | Force regeneration of products even if they already exist. |
| `--no-refs` | | Flag | `False` | Do not use reference images or reference text for generation. Overrides `--useReferenceImages` and `--useImageDescription`. |

### Configuration (Environment Variables)

The pipeline relies on several environment variables for model selection and prompt configuration. These can be set in a `.env` file in the project root.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ENRICH_MODEL_PRIMARY` | `gemini-3.1-pro-preview` | Primary model for product enrichment. |
| `ENRICH_MODEL_FALLBACK` | `gemini-3-flash-preview` | Fallback model for product enrichment. |
| `DESCRIBE_MODEL_PRIMARY` | `gemini-3.1-pro-preview` | Primary model for describing products from images. |
| `DESCRIBE_MODEL_FALLBACK` | `gemini-3.1-flash-preview` | Fallback model for describing products from images. |
| `JUDGE_MODEL` | `gemini-2.5-pro` | Model used to judge product likeness. |
| `GENERATE_MODEL` | `gemini-3-pro-image-preview` | Model used for image generation. |
| `API_CALL_TIMEOUT` | `60` | API call timeout in seconds. |
| `PRIMARY_MODEL_RETRIES` | `3` | Number of retries for the primary model before falling back. |
| `PASS_THRESHOLD` | `0.9` | Threshold score for image likeness approval. |
| `THREAD_POOL_SIZE` | `5` | Number of concurrent threads for processing products. |
| `ENRICH_PROMPT` | | Prompt template for product enrichment. |
| `DESCRIBE_PROMPT` | | Prompt template for describing products. |
| `JUDGE_INSTRUCTIONS` | | System instructions for the judge model. |
| `JUDGE_PROMPT` | | Prompt for the judge model. |
| `GENERATE_PROMPT_BASE` | | Base prompt for image generation. |
