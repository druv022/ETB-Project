"""Orchestrator prompts — backward-compatible exports.

Prefer :func:`etb_project.prompts_config.load_prompts` for new code.
Strings are loaded from ``src/config/prompts.yaml``.
"""

from __future__ import annotations

from etb_project.prompts_config import load_prompts

ORION_SYSTEM_PROMPT = load_prompts().orion_system

__all__ = ["ORION_SYSTEM_PROMPT"]
