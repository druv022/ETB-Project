"""HyDE prompts — backward-compatible exports.

Prefer :func:`etb_project.prompts_config.load_prompts` for new code.
Strings are loaded from ``src/config/prompts.yaml``.
"""

from __future__ import annotations

from etb_project.prompts_config import load_prompts

_hp = load_prompts()
HYDE_SYSTEM = _hp.hyde_system
HYDE_USER_TEMPLATE = _hp.hyde_user_template

__all__ = ["HYDE_SYSTEM", "HYDE_USER_TEMPLATE"]
