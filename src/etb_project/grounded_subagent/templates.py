"""Prompt and disclaimer templates for the grounded writer subagent.

Swap ``build_writer_system_prompt`` / tool docstrings here to extend behavior without
changing graph topology. Optional: load overrides from a file path via env in a
follow-up.
"""

from __future__ import annotations

# Prefixed when the writer subgraph falls back to direct grounded generation.
WRITER_FORCE_DIRECT_DISCLAIMER = (
    "[Note: Writer subagent ended early (step limit, missing final tool, or model "
    "did not use tools); answer produced via direct grounded generation.]"
)

WRITER_TOOL_RETRY_PROMPT = (
    "You must respond using your writer tools only. Use record_thought, submit_plan, "
    "retrieve_more as needed, and submit_final_answer when ready. Do not reply with "
    "plain text only."
)


def build_writer_system_prompt(*, max_steps: int, max_retrieve: int) -> str:
    """System prompt injected on every writer LLM call (not persisted in parent session)."""
    return f"""You are a specialized assistant that produces the final answer for an executive RAG workflow.

    You already have an initial context message (question + retrieved passages). You may:
    - record_thought: private reasoning scratchpad (logged for debugging only).
    - submit_plan: outline steps before answering.
    - retrieve_more: search for additional passages when context is thin (budget: up to {max_retrieve} calls this turn).
    - draft_code_hook: placeholder for future code tools (returns a notice; do not rely on execution).
    - submit_final_answer: REQUIRED to finish — pass the complete user-facing answer as plain text.

    Constraints:
    - Ground claims in the provided context when possible; if you use retrieve_more, integrate new facts carefully.
    - Call submit_final_answer when you have a complete response (before internal step budget exhaustion: {max_steps} LLM steps).
    - Keep the final answer professional and concise."""


def tool_description_record_thought() -> str:
    return (
        "Record a short private reasoning note (chain-of-thought scratchpad). "
        "Does not change retrieval context."
    )


def tool_description_submit_plan() -> str:
    return (
        "Submit a brief numbered or bulleted plan for how you will answer the question."
    )


def tool_description_retrieve_more() -> str:
    return (
        "Search the document index for more relevant passages. "
        "Use a precise standalone query string."
    )


def tool_description_draft_code_hook() -> str:
    return (
        "Placeholder for future code-generation or execution tools. "
        "Currently returns a notice only — do not assume code runs."
    )


def tool_description_submit_final_answer() -> str:
    return (
        "Submit the final user-facing answer as plain text. This ends the writer turn."
    )


__all__ = [
    "WRITER_FORCE_DIRECT_DISCLAIMER",
    "WRITER_TOOL_RETRY_PROMPT",
    "build_writer_system_prompt",
    "tool_description_draft_code_hook",
    "tool_description_record_thought",
    "tool_description_retrieve_more",
    "tool_description_submit_final_answer",
    "tool_description_submit_plan",
]
