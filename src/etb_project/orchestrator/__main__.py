"""Run the orchestrator API with uvicorn: ``python -m etb_project.orchestrator``.

Loads ``create_app`` (agentic ``POST /v1/chat``, health, asset proxy). Bind via ``ETB_ORCH_HOST`` / ``PORT`` / ``ETB_ORCH_PORT``.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("ETB_ORCH_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("PORT", os.environ.get("ETB_ORCH_PORT", "8001")))
    uvicorn.run(
        "etb_project.orchestrator.app:create_app",
        factory=True,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
