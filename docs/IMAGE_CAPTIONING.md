# Image captioning

The document processor can optionally generate captions for extracted images via a pluggable captioning interface. Captions can be:

- persisted into `pages.json` alongside extracted image metadata
- attached to LangChain `Document.metadata` so they flow through chunking
- embedded/indexed in a separate vector store (dual retrieval)

## Concepts

### What is captioned?

- Images embedded in PDFs are extracted to an `images/` folder during processing.
- Each extracted image may be sent to a captioning backend (depending on configuration).

### Where do captions show up?

When an image caption is produced:

- Each image record in `pages.json` gains:
  - `caption`: caption text
  - `caption_source`: a label such as `"vlm"` indicating the caption came from a vision-language model
- Page-level `Document.metadata` gains an `image_captions` key containing objects with:
  - `path`: image file path
  - `caption`: generated caption
- Since the LangChain splitter preserves metadata, chunk-level `Document` objects also carry `image_captions`.

If no captioner is configured, the processor behaves the same as without captioning:

- no network calls are made
- caption fields are not added

## Backends and implementations

Captioning implementations live under `etb_project.document_processing.captioning` and follow a shared interface.

### Interface

- `ImageCaptioner`: abstract interface for captioning images.

### Implementations

- `MockImageCaptioner`
  - Deterministic placeholder captions
  - Useful for tests and local development

- `ChatCompletionImageCaptioner`
  - Shared implementation using the official OpenAI Python SDK (`chat.completions` with vision)
  - Supports any OpenAI-compatible endpoint via `base_url`

- `OpenRouterImageCaptioner`
  - Preset for OpenRouter (`base_url` set to `https://openrouter.ai/api/v1`)
  - API key from `OPENROUTER_API_KEY`
  - Default model from `openrouter_image_caption_model` in `settings.yaml`

- `OpenAIImageCaptioner`
  - Preset for OpenAI (default endpoint)
  - API key from `OPENAI_API_KEY`
  - Default model from `openai_image_caption_model` in `settings.yaml`

## Configuration and precedence

Captioner selection is driven by `settings.yaml`.

The CLI chooses a captioner as follows:

- If `openrouter_image_caption_model` is set, it uses `OpenRouterImageCaptioner`.
- Otherwise, if `openai_image_caption_model` is set, it uses `OpenAIImageCaptioner`.

Avoid configuring both at once unless you explicitly intend OpenRouter to take precedence.

See [`CONFIGURATION.md`](CONFIGURATION.md) for example configs.

## Environment variables

Set API keys via environment variables (commonly via `.env`):

- `OPENROUTER_API_KEY`: required for OpenRouter captioning
- `OPENAI_API_KEY`: required for OpenAI captioning

## Failure modes and logging

Vision backends use the `openai` Python package.

On API errors, implementations:

- log a **warning** (including response body text when available, truncated)
- return `None` for that image (so processing continues)

## Standalone captioning script

For quickly captioning a single image file (outside of PDF processing), see [`TOOLS.md`](TOOLS.md).

## Related docs

- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`CONFIGURATION.md`](CONFIGURATION.md)
- [`TOOLS.md`](TOOLS.md)
