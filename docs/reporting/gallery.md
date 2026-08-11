# Enterprise GenAI Gallery

The enterprise gallery built by [`build_gallery.py`](../api/build_gallery.md) produces a visual showcase displaying generated lifestyle and studio assets across all processed catalog items.

---

## Design & Interface Features

- **Glassmorphic Aesthetic**: Translucent card backgrounds (`backdrop-filter: blur(10px)`), subtle radial background patterns, and hover elevations (`transform: translateY(-8px)`).
- **Responsive Layout**: CSS Grid dynamically scaling from mobile viewports to ultra-wide displays (`repeat(auto-fill, minmax(280px, 1fr))`).
- **Performance Optimized**: Implements native HTML `loading="lazy"` on all generated imagery.
- **Deep-Linking**: Direct links on card images navigate immediately to the corresponding SKU's Before/After PDP audit page.

---

## Generation & Usage

Generate or rebuild the gallery at any time:

```bash
uv run product-gen-gallery --dir output/Google_50_skus_image_generation
```

Output is written to `output/<run_name>/index.html` (or `gallery.html` when customized).
