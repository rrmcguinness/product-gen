# Installation & Setup

---

## Prerequisites

- **Python 3.13**: The project requires Python 3.13 (`requires-python = "==3.13.*"`).
- **uv**: Fast, deterministic package manager by Astral.
- **Google Cloud / Gemini Credentials**: Either a Gemini API Key or active Google Cloud Application Default Credentials (ADC).

---

## 1. Install `uv`

If `uv` is not already installed on your system:

=== "macOS / Linux"
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "Homebrew (macOS)"
    ```bash
    brew install uv
    ```

---

## 2. Clone Repository & Synchronize Dependencies

```bash
# Clone the repository
git clone https://github.com/walmart/product-gen.git
cd product-gen

# Synchronize virtual environment with locked dependencies
uv sync

# Install editable package with docs tools
uv pip install -e .
```

---

## 3. Configure Credentials

Create your `.env` configuration file from the template:

```bash
cp dot_env_example.txt .env
```

Open `.env` and configure your API credentials:

```dotenv
# Option A: Gemini Developer API Key
GEMINI_API_KEY="your-gemini-api-key-here"

# Option B: Google Cloud Vertex AI
GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
GOOGLE_CLOUD_PROJECT_LOCATION="us-central1"
```

Verify authentication using `gcloud` if using Vertex AI:

```bash
gcloud auth application-default login
```
