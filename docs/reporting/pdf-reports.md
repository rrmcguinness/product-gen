# Executive PDF Reports

Implemented in [`report.py:generate_pdf_report`](../api/report.md) using the **ReportLab Platypus** framework, this module generates a high-density, print-ready document formatted for 11x17 landscape distribution.

---

## Document Specifications

| Parameter | Specification | Purpose |
| :--- | :--- | :--- |
| **Page Dimensions** | `1224pt x 792pt` (11" x 17" Tabloid Landscape) | Accommodates dense tabular SKU data without line truncation |
| **Color Palette** | Walmart Blue (`#0071dc`), Slate (`#2e2f32`), Ice Blue (`#f2f8fd`) | Enterprise brand alignment |
| **Pagination** | Page 1: Executive KPI Summary; Page 2+: Detailed Product Matrix | Clean executive briefing layout |

---

## Executive Report Content

### Page 1: Summary Statistics
- **Production Metrics**: Total SKUs processed, successful image generations, failed image generations, total retries across run.
- **Token Accounting**: Total input tokens, total output tokens, aggregate token consumption, average tokens consumed per SKU.
- **Cost Projections**: Discounted Vertex AI pricing calculations for input, output, and net total spend.
- **Error Breakdown**: Tabular list of API exceptions or data parsing anomalies encountered during execution.

### Page 2+: Detailed Product Breakdown Matrix
A multi-column table detailing per-product performance metrics:

| Column | Description |
| :--- | :--- |
| **Product ID** | SKU WPID identifier |
| **Category** | Top-level and secondary taxonomy category |
| **Success / Fail** | Binary outcome flag against `PASS_THRESHOLD` |
| **Retries** | Number of retry iterations required |
| **Enrich Tokens** | Tokens consumed by `enrich_product` |
| **Desc Tokens** | Tokens consumed by `describe_product_from_images` |
| **Img1 Tokens** | Tokens consumed during image generation |
| **Judge Tokens** | Tokens consumed by likeness evaluation |
| **Total Tokens** | Rollup token sum |
| **Time (s)** | Net wall-clock execution time |
| **Cost ($)** | Calculated cost for the SKU |
