# Environment Variables Reference

Environment variables are loaded automatically from `.env` in the project root via `python-dotenv`.

---

## Model Selection

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENRICH_MODEL_PRIMARY` | `gemini-3.1-pro-preview` | Primary foundation model for structured product enrichment. |
| `ENRICH_MODEL_FALLBACK` | `gemini-3-flash-preview` | Fallback model if primary enrichment encounters errors. |
| `DESCRIBE_MODEL_PRIMARY` | `gemini-3.1-pro-preview` | Model for extracting detailed physical descriptions from reference images. |
| `DESCRIBE_MODEL_FALLBACK` | `gemini-3.1-flash-preview` | Fallback model for physical description extraction. |
| `GENERATE_MODEL` | `gemini-3-pro-image-preview` | Model used for high-fidelity 2200x2200 studio image generation. |
| `JUDGE_MODEL` | `gemini-2.5-pro` | Multimodal model used to evaluate likeness between generated and reference images. |
| `SEARCH_MODEL` | `gemini-3.1-flash-lite` | Model equipped with Google Search tool to find official reference image URLs. |
| `VERIFY_MODEL` | `gemini-3.1-flash-lite` | Multimodal catalog auditor model verifying downloaded reference images. |

---

## Execution & Concurrency

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `THREAD_POOL_SIZE` | `5` | Number of worker threads executing SKU processing concurrently. |
| `API_CALL_TIMEOUT` | `60` | Timeout in seconds for individual Gemini API calls. |
| `PRIMARY_MODEL_RETRIES` | `3` | Number of retries before switching from primary to fallback model. |
| `PASS_THRESHOLD` | `0.9` | Float likeness score (`0.0` to `1.0`) required for image approval. |

---

## Sampling Parameters (Temperature, Top-P, Top-K)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENRICH_TEMP` | `0.4` | Temperature for product enrichment generation. |
| `ENRICH_TOP_P` | `None` | Optional top-p nucleus sampling for enrichment. |
| `ENRICH_TOP_K` | `None` | Optional top-k sampling for enrichment. |
| `DESCRIBE_TEMP` | `0.4` | Temperature for image physical description generation. |
| `JUDGE_TEMP` | `0.0` | Temperature for the Judge model (set to 0.0 for deterministic scoring). |
| `JUDGE_TOP_P` | `0.7` | Top-p parameter for the Judge model. |
| `JUDGE_TOP_K` | `60` | Top-k parameter for the Judge model. |
| `SEARCH_TEMP` | `0.2` | Temperature for reference image search queries. |
| `VERIFY_TEMP` | `0.0` | Temperature for reference image verification. |

---

## Prompts & System Instructions

| Variable | Default Description |
| :--- | :--- |
| `ENRICH_INSTRUCTIONS` | Merchandising persona guidelines enforcing JSON schema adherence. |
| `ENRICH_PROMPT` | Prompt template containing `{schema}` and `{product_json}` format variables. |
| `DESCRIBE_INSTRUCTIONS` | Marketing persona instructions focusing on fabric, construction, and color hexes. |
| `DESCRIBE_PROMPT` | Text prompt instructing the model to describe physical product attributes. |
| `GENERATE_PROMPT_BASE` | Base prompt template: `Task: A high quality product photograph of '{product_name}'...` |
| `JUDGE_INSTRUCTIONS` | Retail catalog auditor persona specifying quality gates and scoring rules. |
| `JUDGE_PROMPT` | Prompt instructing the judge to evaluate likeness against reference images. |
| `REWRITE_PROMPT` | Prompt engineer persona template used to rewrite prompts based on judge feedback. |
| `SEARCH_PROMPT` | Prompt template for discovering official manufacturer image URLs. |
| `VERIFY_PROMPT` | Prompt for classifying whether an image contains the physical product. |

---

## Google Cloud Credentials

| Variable | Description |
| :--- | :--- |
| `GEMINI_API_KEY` | Gemini Developer API key (if using AI Studio developer endpoints). |
| `GOOGLE_CLOUD_PROJECT` | Google Cloud Project ID (if using Vertex AI). |
| `GOOGLE_CLOUD_PROJECT_LOCATION` | Google Cloud region (default: `us-central1`). |
