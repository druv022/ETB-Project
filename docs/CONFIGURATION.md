# Configuration

The ETB-project RAG app reads its primary configuration from YAML and supplements it with environment variables (for secrets like API keys).

This page documents:

- where config is loaded from
- the core settings in `src/config/settings.yaml`
- environment variables used by the project

## Config file: `src/config/settings.yaml`

### How the app finds the config

The main app reads configuration from `src/config/settings.yaml`.

Resolution behavior:

- It looks for this file relative to the **current working directory** first (so running from the repo root works).
- It also supports locating the file relative to the installed package location (so running from inside `src/` works).
- You can override the config path with `ETB_CONFIG` (absolute path to another YAML file).

### Core keys

The root README keeps only a minimal subset of these. This page is the full reference.

| Key | Type | Description |
|---|---:|---|
| `pdf` | string/null | Path to the PDF to index and query (absolute or relative to current working directory). |
| `query` | string | Single query to run; leave empty for interactive mode. |
| `retriever_k` | int | Number of chunks to retrieve per query (typically 1–100). |
| `log_level` | string | Logging level: DEBUG, INFO, WARNING, ERROR. |
| `vector_store_path` | string | Directory path where persisted vector indices live (used by `etb_project.main` for load-only retrieval). |
| `openrouter_image_caption_model` | string/empty | If set, enables OpenRouter captioning and selects the model name. |
| `openai_image_caption_model` | string/empty | If set (and OpenRouter model is not set), enables OpenAI captioning and selects the model name. |

Notes:

- `pdf` must point to an existing file. The app exits with an error if it is missing or not found.
- Captioning model keys control which captioner backend is used (see [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)).

### Example: interactive mode

```yaml
pdf: data/your-document.pdf
query: ""   # leave empty for interactive mode
retriever_k: 10
log_level: INFO
vector_store_path: data/vector_index
```

### Example: single-query mode

```yaml
pdf: data/your-document.pdf
query: "Summarize the key points in section 2."
retriever_k: 10
log_level: INFO
vector_store_path: data/vector_index
```

### Example: enable OpenRouter captioning

```yaml
openrouter_image_caption_model: "google/gemini-2.0-flash"
openai_image_caption_model: ""
```

### Example: enable OpenAI captioning

```yaml
openrouter_image_caption_model: ""
openai_image_caption_model: "gpt-4.1-mini"
```

## Environment variables

### Config selection

- `ETB_CONFIG`
  - Absolute path to a YAML file to use instead of `src/config/settings.yaml`.

### Captioning secrets

- `OPENROUTER_API_KEY`
  - Required for `OpenRouterImageCaptioner`.
- `OPENAI_API_KEY`
  - Required for `OpenAIImageCaptioner` and OpenAI-compatible endpoints (when not using OpenRouter).

Common workflow:

```bash
cp .env.example .env
```

Then set the keys in `.env` (do not commit secrets).

## Related docs

- [`USAGE.md`](USAGE.md)
- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)
