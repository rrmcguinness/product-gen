# Architecture Overview

The **Walmart Product Generation Pipeline** implements an autonomous, multi-stage processing pipeline built around Google Gemini generative foundation models and Pydantic schema validation.

---

## High-Level Block Diagram

```mermaid
graph TD
    subgraph Data Layer
        A[Excel Source File\n.xlsx] --> B[Product Reader\nproduct_reader.py]
        B --> C[Normalized Product Records\nProductImageGenerationData]
    end

    subgraph Execution & Orchestration
        C --> D[Process Orchestrator\nprocess.py]
        D -->|Concurrent ThreadPool| E[Single Product Worker]
    end

    subgraph GenAI Processing Pipeline
        E --> F[1. GenAI Enrichment\ngemini-3.1-pro-preview]
        F --> G[2. Reference Acquisition\nImageFinder + Gemini Grounding]
        G --> H[3. Multimodal Verification\ngemini-3.1-flash-lite]
        H --> I[4. Constrained Image Generation\ngemini-3-pro-image-preview]
        I --> J[5. Likeness Judge\ngemini-2.5-pro]
        J -->|Score < 0.90\nAttempt < 3| K[6. Prompt Self-Refinement\ngemini-3.1-pro-preview]
        K --> I
        J -->|Score >= 0.90 or\nMax Retries| L[7. Persist Artifacts\nproduct_detail.json & Images]
    end

    subgraph Reporting & Visualization
        L --> M[Per-SKU HTML PDP\npdp.py]
        L --> N[Summary Dashboard\ngenerate_report.py]
        L --> O[Executive PDF Report\nreport.py]
        L --> P[Product Gallery\nbuild_gallery.py]
    end
```

---

## Architectural Principles

### 1. Strict Schema Adherence via Pydantic
All data passing through the system is strictly typed using Pydantic v2 models. GenAI requests use structured outputs with `response_schema` and `response_mime_type="application/json"` to eliminate schema drift and parsing anomalies.

### 2. Multi-Tier Model Fallback & Resiliency
Model interactions are encapsulated in a robust execution wrapper [`call_gemini`](../api/utils.md) that provides:
- **Primary to Fallback Switching**: If primary pro models (`gemini-3.1-pro-preview`) encounter quota exhaustion or upstream service errors, the pipeline automatically falls back to flash models (`gemini-3-flash-preview` / `gemini-2.5-flash`).
- **Exponential Backoff**: Transient network and HTTP errors trigger exponential backoff with jitter.
- **Sliding-Window Rate Limiting**: Global thread-safe rate limiter restricting outbound calls to 25 requests per minute to maintain API quota compliance.

### 3. Closed-Loop Visual Feedback Control
Rather than generating an image in an open-loop fashion, the pipeline introduces an automated quality control auditor:
- The **Judge** multimodal model acts as an objective quality inspector, comparing the generated image to downloaded ground-truth manufacturer images.
- If the likeness score falls below the configurable threshold (`PASS_THRESHOLD`, default `0.90`), the judge's reasoning is injected into an automated prompt rewriting model that diagnoses visual deficiencies and issues a corrected image generation prompt.

### 4. Comprehensive Telemetry & Observability
Every execution step records granular telemetry within [`StepMetrics`](data-models.md#stepmetrics) and [`PipelineMetrics`](data-models.md#pipelinemetrics):
- Execution time in seconds
- Input token counts
- Output token counts
- HTTP error tallies mapped by status code
- Applied model IDs
- Multimodal conditioning flags (Image + Prompt vs. Prompt Only)
