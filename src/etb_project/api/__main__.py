"""Run the retriever API with uvicorn: ``python -m etb_project.api``."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("ETB_API_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("PORT", os.environ.get("ETB_API_PORT", "8000")))
    # factory=True: each worker gets a fresh app (correct lifespan + test isolation).
    uvicorn.run(
        "etb_project.api.app:create_app",
        factory=True,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
