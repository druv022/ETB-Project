---
name: Unify-LLM-Providers
overview: Refactor LLM construction so the orchestrator uses a single provider registry in etb_project/models.py, with a base provider class extensible to OpenAI-compatible and Ollama (and future providers).
todos:
  - id: models-provider-base
    content: Add ChatModelProvider base + provider registry and get_chat_llm() in src/etb_project/models.py (OpenAI-compatible + Ollama).
    status: completed
  - id: orchestrator-migrate
    content: Update orchestrator to use etb_project.models.get_chat_llm(); remove orchestrator/llm.py and simplify orchestrator/settings.py accordingly.
    status: completed
  - id: compose-docs-update
    content: Update docker-compose.yml and README.md to use global env vars (ETB_LLM_PROVIDER, OPENAI_*, OLLAMA_*).
    status: completed
  - id: tests-update
    content: Update and add unit tests for provider selection and orchestrator behavior using the new model provider abstraction.
    status: completed
isProject: false
---

## Goal

- Remove duplicate LLM construction logic in `[src/etb_project/orchestrator/llm.py](src/etb_project/orchestrator/llm.py)`.
- Centralize all LLM creation behind a **base provider abstraction** in `[src/etb_project/models.py](src/etb_project/models.py)`.
- Support **OpenAI-compatible** + **Ollama** immediately, with a clean extension point for other providers later.
- Use **standardized global env vars** (per your choice): `OPENAI_`*, `OLLAMA_`*, etc.
- Use **OpenRouter via OpenAI-compatible** as the default remote provider, with **StepFun** (`stepfun/step-3.5-flash`) as the default model id.
- Keep the **reporting tools under `tools/` fully separate** from anything in `src/` (no refactors, no shared provider registry, and no changes to `REPORT_LLM_`* behavior as part of this plan).

## Current state (relevant code)

- Orchestrator currently builds an OpenAI-compatible LLM in a dedicated module:
  - `[src/etb_project/orchestrator/llm.py](src/etb_project/orchestrator/llm.py)` `build_openai_compatible_llm(settings)`
- Shared model helpers already exist in `[src/etb_project/models.py](src/etb_project/models.py)`:
  - `get_openai_llm(model="gpt-4o-mini", temperature=0)`
  - `get_ollama_llm(model="qwen3.5:9b", temperature=0)` (honors `OLLAMA_HOST`/`OLLAMA_BASE_URL`)

## Design

### Provider base class

- Add an abstract base class (or Protocol) in `models.py`:
  - `class ChatModelProvider(ABC):`
    - `name: str`
    - `def build_chat_model(self) -> BaseChatModel`
- Implement concrete providers:
  - `OpenAICompatibleProvider`:
    - returns `ChatOpenAI(...)`
    - reads global env vars:
      - `OPENAI_API_KEY`
      - `OPENAI_BASE_URL` (optional; for OpenAI-compatible)
      - `OPENAI_MODEL` (default `stepfun/step-3.5-flash`)
      - `OPENAI_TEMPERATURE` (default `0`)
  - `OllamaChatProvider`:
    - returns `ChatOllama(...)`
    - reads global env vars:
      - `OLLAMA_HOST` or `OLLAMA_BASE_URL` (already supported)
      - `OLLAMA_CHAT_MODEL` (default `qwen3.5:9b`)
      - `OLLAMA_TEMPERATURE` (default `0`)

### Provider selection

- Add `ETB_LLM_PROVIDER` env var, with allowed values e.g.:
  - `openai_compat` (default)
  - `ollama`
- Add a registry:
  - `PROVIDERS: dict[str, ChatModelProvider]`
  - `def get_chat_llm() -> BaseChatModel:` selects provider based on `ETB_LLM_PROVIDER` and returns provider.build_chat_model().

## Orchestrator integration

- Update `[src/etb_project/orchestrator/app.py](src/etb_project/orchestrator/app.py)`:
  - Replace `from etb_project.orchestrator.llm import build_openai_compatible_llm` with `from etb_project.models import get_chat_llm` (new function).
  - Replace `llm = build_openai_compatible_llm(settings)` with `llm = get_chat_llm()`.
- Update `[src/etb_project/orchestrator/settings.py](src/etb_project/orchestrator/settings.py)`:
  - Remove OpenAI-specific fields (`openai`_*) since provider config is now global.
  - Keep orchestrator-only settings (retriever URL, default_k, CORS, session ttl).
- Remove `[src/etb_project/orchestrator/llm.py](src/etb_project/orchestrator/llm.py)` after callers are migrated.

## Docker compose + docs updates

- Update `docker-compose.yml` orchestrator env vars:
  - Remove `ORCH_OPENAI_`* and use:
    - `ETB_LLM_PROVIDER=openai_compat` (or `ollama`)
    - `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_TEMPERATURE`
    - `OLLAMA_HOST` / `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_TEMPERATURE`
- Add an explicit OpenRouter example for `openai_compat`:\n  - `OPENAI_BASE_URL=https://openrouter.ai/api/v1`\n  - `OPENAI_API_KEY=$OPENROUTER_API_KEY`\n  - `OPENAI_MODEL=stepfun/step-3.5-flash`
- Update `[README.md](README.md)` Option A section:
  - Document `ETB_LLM_PROVIDER` and the global env var sets for OpenAI-compatible vs Ollama.
- Clarify in docs that reporting utilities under `tools/` remain independently configured via `tools/data_generation/report_generation/llm_config.yaml` and `REPORT_LLM_*` env vars.

## Tests

- Update `tests/test_orchestrator_api.py` to avoid ORCH-specific env vars:
  - Set `ETB_LLM_PROVIDER=openai_compat`
  - Set `OPENAI_API_KEY` + `OPENAI_MODEL` (defaults to `stepfun/step-3.5-flash`), and set `OPENAI_BASE_URL` when testing OpenRouter mode
- Add unit tests for provider selection in `models.py`:
  - Unknown provider → clear error
  - `openai_compat` builds ChatOpenAI with expected config
  - `ollama` builds ChatOllama with expected config

## Migration/compatibility notes

- Keep `get_openai_llm()` and `get_ollama_llm()` for backward compatibility, but have provider classes call into them to avoid duplication.
- Ensure orchestrator `/v1/ready` reflects provider configuration:
  - e.g., `llm_configured` checks `ETB_LLM_PROVIDER` validity and required env vars presence (minimal validation; no network).
