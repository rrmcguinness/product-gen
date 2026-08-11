# Troubleshooting & FAQ

---

## Common Issues & Resolutions

### 1. HTTP `429 Too Many Requests` (Quota Exhaustion)

**Symptom:**
```text
[Warning] Enrich Product failed (API Error 429): Resource has been exhausted (e.g. check quota).
```

**Root Cause:**
Outbound request volume exceeds the Google Cloud Vertex AI or Gemini Developer API rate quota.

**Remediation:**
1. Lower `THREAD_POOL_SIZE` in `.env` or pass `--threads 2` via CLI.
2. The built-in rate limiter (`check_rate_limit`) automatically enforces a 25 RPM cap. If your tier is lower (e.g., free tier 15 RPM), modify `check_rate_limit` in `utils.py`.
3. Verify that `PRIMARY_MODEL_RETRIES` is set to $\ge 3$ so transient rate spikes back off exponentially.

---

### 2. Missing Reference Images & Automatic "Need Review" Flagging

**Symptom:**
```text
[Warning] No reference images found for WPID_123. Proceeding with text-only generation.
No reference images to judge likeness. Flagging for review.
```

**Root Cause:**
Neither Google Search nor the spreadsheet payload contained valid, unblocked image URLs, or downloaded images were classified as non-product content by `verify_reference_image`.

**Behavior:**
- The pipeline proceeds to generate an image based solely on the textual enrichment.
- The judge assigns a likeness score of `0.0` and marks the item for human merchandising audit.
- The product is safely included in the dashboard under the `Need Review` category.

---

### 3. Model Returns No Inline Image Data

**Symptom:**
```text
Warning: No inline image data returned by the model.
```

**Root Cause:**
The image generation prompt may have triggered an internal safety block or the upstream model returned empty candidate parts.

**Remediation:**
The pipeline automatically increments the retry counter and re-invokes the model with exponential delay. Check `image_constraints.md` to ensure prompt terms do not violate safety policies.

---

### 4. Excel Parsing Anomaly / WPID Collision

**Symptom:**
Fewer records processed than total rows in spreadsheet.

**Root Cause:**
`product_reader.py` automatically deduplicates rows sharing the same `wpid` to prevent file overwrite collisions:
```python
df.drop_duplicates(subset=["wpid"], keep="first", inplace=True)
```

**Remediation:**
Ensure source data assigns distinct `wpid` identifiers to distinct SKUs.
