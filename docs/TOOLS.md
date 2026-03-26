# Tools (not installed)

Utility scripts and side projects live under `tools/` and are **not** part of the installed `etb_project` package. They are intended for development and one-off tasks.

## Running tools

Most `tools/` modules are executed from the repo root so Python can resolve imports properly.

Two common patterns:

1) Run a `tools` module with `PYTHONPATH` set:

```bash
PYTHONPATH=. python -m tools.data_generation
```

2) Run a script directly:

```bash
python tools/data_generation/your_script.py
```

## Data generation

Data generation scripts are in `tools/data_generation/`.

- These scripts are not installed with `pip install .`.
- They are typically used to create synthetic datasets and report artifacts for development/demo purposes.

## Image captioning (standalone)

[`tools/test_image_captioning.py`](../tools/test_image_captioning.py) captions a single image file through the same backends as the document processor.

By default it uses **OpenRouter** with the **OpenAI Python SDK** (`openai` package):

- set `OPENROUTER_API_KEY`
- configure `openrouter_image_caption_model` in `settings.yaml` (or pass `--model`)

Example usage:

```bash
export OPENROUTER_API_KEY=…
pip install -e .
python tools/test_image_captioning.py path/to/image.png

# no API keys, deterministic output
python tools/test_image_captioning.py --backend mock path/to/image.png

# direct OpenAI API
python tools/test_image_captioning.py --backend openai path/to/image.png
```

See:

```bash
python tools/test_image_captioning.py --help
```

## Related docs

- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)
- [`DEVELOPMENT.md`](DEVELOPMENT.md)
