# Command-Line Interface Reference

The project registers five executable console script entrypoints via `pyproject.toml`.

---

## 1. `product-gen` (Pipeline Orchestrator)

Runs the complete product enrichment, image generation, judging, and reporting pipeline.

```bash
uv run product-gen [OPTIONS]
```

### Options

| Flag | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--file` | `-f` | String | `data/Google_50_skus_image_generation.xlsx` | Path to the source Excel catalog spreadsheet. |
| `--max-records` | `-n` | Integer | `None` | Strict limit on records to process (processes all if omitted or $\le 0$). |
| `--use-reference-images` | | Flag | `False` | Pass downloaded reference images directly to the image generator. *(Note: Disables image indemnification).* |
| `--use-image-description` | | Flag | `False` | Generate detailed physical text description from reference images before generation. |
| `--no-product-description`| | Flag | `False` | Exclude the product text description from the image generation prompt. |
| `--force` | | Flag | `False` | Force regeneration of products even if `output/WPID/index.html` exists. |
| `--output` | `-o` | String | `None` | Custom output directory path (defaults to `output/<file_stem>`). |
| `--threads` | `-j` | Integer | `None` | Number of concurrent worker threads. Overrides `THREAD_POOL_SIZE`. |

### Execution Examples

```bash
# Process first 5 records with multi-threading
uv run product-gen -f data/Google_50_skus_image_generation.xlsx -n 5 -j 4

# Force complete regeneration with image-based description enabled
uv run product-gen -n 10 --force --use-image-description
```

---

## 2. `product-gen-report` (Report Generator)

Scans an existing output folder and generates both the aggregated HTML execution dashboard and the executive PDF report.

```bash
uv run product-gen-report [OPTIONS]
```

### Options

| Flag | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--dir` | `-d` | String | `output` | Directory containing product output folders. |

---

## 3. `product-gen-gallery` (Gallery Builder)

Scans an output folder and generates a responsive, glassmorphic HTML product gallery.

```bash
uv run product-gen-gallery [OPTIONS]
```

### Options

| Flag | Short | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--dir` | `-d` | String | `output` | Directory containing product output folders. |

---

## 4. `docs-serve` (Documentation Server)

Launches a local MkDocs live-reloading development server.

```bash
uv run docs-serve [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--dev-addr` | `-a` | `127.0.0.1:8000` | Local network binding address and port. |
| `--config-file` | `-c` | `mkdocs.yml` | Path to custom MkDocs YAML configuration. |
| `--no-livereload` | | `False` | Disable live reload server. |
| `--dirty` | | `False` | Fast incremental rebuild of modified pages only. |

---

## 5. `docs-build` (Documentation Builder)

Compiles the MkDocs markdown files into static HTML ready for web hosting.

```bash
uv run docs-build [OPTIONS]
```

### Options

| Flag | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--clean` | | `True` | Clean the output directory before building. |
| `--strict` | | `False` | Enable strict mode (treat warnings as errors). |
| `--site-dir` | `-d` | `site/` | Destination directory for compiled HTML assets. |

---

## 6. `docs-package` (Documentation Web Archive Packager)

Packages the compiled documentation into standalone single-file offline bundles (`.html`, `.mhtml`, `.zip`).

```bash
uv run docs-package [OPTIONS]
```

### Options

| Flag | Short | Choices | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `--output-dir` | `-o` | String | Project Root | Directory to place generated archive files. |
| `--format` | | `all`, `html`, `mhtml`, `zip` | `all` | Specific bundle format to produce. |

