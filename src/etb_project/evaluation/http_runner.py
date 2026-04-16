from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, cast

import httpx

from etb_project.evaluation.schemas import EvalRow


@dataclass(frozen=True)
class OrchestratorClient:
    base_url: str
    timeout_s: float = 60.0
    api_key: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    def chat(self, *, message: str, k: int | None = None) -> dict[str, Any]:
        url = self.base_url.rstrip("/") + "/v1/chat"
        payload: dict[str, Any] = {
            "session_id": str(uuid.uuid4()),
            "message": message,
            "return_sources": True,
        }
        if k is not None:
            payload["k"] = k
        with httpx.Client(timeout=self.timeout_s, headers=self._headers()) as client:
            resp = client.post(url, json=payload)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())


def collect_answers(
    *,
    base_rows: list[EvalRow],
    orchestrator_base_url: str,
    k: int | None = None,
    api_key: str | None = None,
    timeout_s: float = 60.0,
) -> list[EvalRow]:
    client = OrchestratorClient(orchestrator_base_url, timeout_s, api_key)
    out: list[EvalRow] = []
    for row in base_rows:
        resp = client.chat(message=row.question, k=k)
        answer = str(resp.get("answer") or "")
        sources = resp.get("sources") or []
        contexts: list[str] = []
        for s in sources:
            if isinstance(s, dict):
                c = s.get("content")
                if isinstance(c, str) and c.strip():
                    contexts.append(c)
        meta = dict(row.metadata)
        if isinstance(resp.get("phase"), str):
            meta["phase"] = resp["phase"]
        out.append(
            EvalRow(
                question=row.question,
                answer=answer,
                contexts=contexts,
                ground_truth=row.ground_truth,
                metadata=meta,
            )
        )
    return out
