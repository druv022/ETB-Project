from __future__ import annotations

import os

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from etb_project.evaluation.schemas import RunRecord


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None:
        return default
    v = v.strip()
    return v or default


def _openai_api_key() -> str | None:
    return _env("ETB_EVAL_OPENAI_API_KEY") or _env("OPENAI_API_KEY")


def _openai_base_url() -> str | None:
    return _env("ETB_EVAL_OPENAI_BASE_URL") or _env("OPENAI_BASE_URL")


def _notes_model() -> str:
    return _env("ETB_EVAL_NOTES_MODEL", "gpt-4o-mini") or "gpt-4o-mini"


def _format_metrics(m: dict[str, float]) -> str:
    keys = sorted(m.keys())
    parts: list[str] = []
    for k in keys:
        parts.append(f"{k}={m[k]:.4f}")
    return ", ".join(parts)


def generate_notes_ai(
    *,
    previous: RunRecord | None,
    current: RunRecord,
    max_chars: int = 600,
) -> str:
    """Generate a short human-readable summary of what changed vs previous run."""
    if previous is None:
        return "First recorded run: no previous baseline to compare."

    key = _openai_api_key()
    llm = ChatOpenAI(
        model=_notes_model(),
        api_key=SecretStr(key) if key else None,
        base_url=_openai_base_url(),
        temperature=0.2,
    )

    prompt = (
        "You are generating short release-notes for a RAG evaluation dashboard.\n"
        "Summarize what changed from the previous run to the current run.\n"
        "Be concise, focus on metric deltas and likely causes; do not invent facts.\n\n"
        f"Previous aggregate metrics: {_format_metrics(previous.aggregate_metrics)}\n"
        f"Current aggregate metrics: {_format_metrics(current.aggregate_metrics)}\n"
        f"Metric deltas (current - previous): {_format_metrics(current.metric_delta_vs_previous)}\n"
    )

    msg = llm.invoke(prompt)
    text = getattr(msg, "content", "")
    if isinstance(text, list):
        text = " ".join(str(x) for x in text)
    out = str(text).strip()
    if not out:
        out = "No Notes generated."
    if len(out) > max_chars:
        out = out[: max_chars - 3].rstrip() + "..."
    return out
