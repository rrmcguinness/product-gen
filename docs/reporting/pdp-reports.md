# Interactive Before & After PDP Reports

Generated automatically by [`pdp.py:generate_pdp_html`](../api/pdp.md), the per-SKU report provides a comprehensive, interactive audit interface for comparing original catalog data against AI-generated assets.

---

## Key Interface Components

```text
+-------------------------------------------------------------------------------+
| HEADER: Product Generation Pipeline: Before & After Report  [ PASS / REVIEW ]  |
+-------------------------------------------------------------------------------+
| GENERATION PROCESS FLOW TIMELINE [ 00:42 ]                                     |
| [Enrich Product] -> [Search Ref URLs] -> [Generate Image] -> [Judge Likeness] |
+---------------------------------------+---------------------------------------+
| LEFT: BEFORE (Original Product)       | RIGHT: AFTER (Generated Product)      |
| - Reference Images Thumbnail Gallery  | - Generated Images Gallery (Pass/Fail)|
| - Origin Product Deep-Link            | - Likeness Quality Score Badge        |
| - Original Product Name               | - Judge's Structured Reasoning        |
| - Original Short Description          | - Enriched Product Name & Description |
| - Original Long Description           | - Standardized Attributes & Features  |
+---------------------------------------+---------------------------------------+
```

---

## Interactive Capabilities

### 1. High-Resolution Comparison Modal
Clicking on any generated thumbnail opens a full-screen comparison modal:
- Left pane displays the reference image gallery.
- Right pane displays the selected generation attempt.
- Bottom card renders the judge's full textual critique and the exact prompt string used for that attempt.

### 2. Status Badge Indication
- **`PASS` (Emerald Green)**: Indicates at least one generated attempt achieved a likeness score $\ge$ `PASS_THRESHOLD` (default `0.90`).
- **`REVIEW` (Crimson Red)**: Indicates all attempts scored below threshold or no reference images were available for automated verification.

### 3. Step-by-Step Latency & Token Flow
The top panel displays a visual flow of all execution steps:
- Step name and applied model ID (`gemini-3.1-pro-preview`, `gemini-3-pro-image-preview`, etc.)
- Execution latency in seconds
- Input and output token counts
- Multimodal conditioning tags (`Image + Prompt` vs `Prompt Only`)
