"""Map LangChain / OpenAI-compatible provider failures to orchestrator API errors."""

from __future__ import annotations

from etb_project.orchestrator.exceptions import OrchestratorAPIError


def map_provider_invoke_error(exc: BaseException) -> OrchestratorAPIError | None:
    """If ``exc`` is a LangChain OpenAI error payload, return a stable API error.

    ``langchain_openai`` raises ``ValueError`` with the provider ``error`` object
    as the sole argument when the HTTP response contains an error body (e.g.
    OpenRouter / Cloudflare 524 upstream timeout).
    """
    if not isinstance(exc, ValueError) or not exc.args:
        return None
    payload = exc.args[0]
    if not isinstance(payload, dict):
        return None
    message = str(payload.get("message") or "LLM provider returned an error.")
    code = payload.get("code")
    detail = str(payload)[:2000]

    # Cloudflare 524: edge timed out waiting for origin (common via OpenRouter).
    if code == 524 or code == "524":
        return OrchestratorAPIError(
            502,
            "LLM_UPSTREAM_TIMEOUT",
            "The chat provider timed out before completing the request (HTTP 524). "
            "Try a faster model, increase ETB_LLM_REQUEST_TIMEOUT_S, set ETB_ORION_CLARIFY=0 "
            "to skip the Orion pre-step, or use ETB_LLM_PROVIDER=ollama with local Ollama.",
            detail,
        )

    return OrchestratorAPIError(
        502,
        "LLM_PROVIDER_ERROR",
        message,
        detail,
    )
