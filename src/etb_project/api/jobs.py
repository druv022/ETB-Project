"""In-memory async index job tracking.

Jobs exist to make indexing usable for larger PDFs:
- The HTTP request can return quickly with a job id.
- A background task performs the work and updates status.

This is intentionally minimal and process-local (sufficient for docker-compose
single-replica dev). If the retriever is ever run with multiple replicas, job
state should move to a shared store.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Literal

JobStatus = Literal["pending", "running", "completed", "failed"]


@dataclass
class IndexJob:
    job_id: str
    status: JobStatus = "pending"
    message: str | None = None
    error: str | None = None


class JobRegistry:
    """Thread-safe registry of indexing jobs for a single process."""

    def __init__(self) -> None:
        self._jobs: dict[str, IndexJob] = {}
        self._lock = threading.Lock()

    def create(self) -> IndexJob:
        jid = str(uuid.uuid4())
        job = IndexJob(job_id=jid)
        with self._lock:
            self._jobs[jid] = job
        return job

    def get(self, job_id: str) -> IndexJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(
        self,
        job_id: str,
        *,
        status: JobStatus,
        message: str | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            j = self._jobs.get(job_id)
            if j is None:
                return
            j.status = status
            if message is not None:
                j.message = message
            if error is not None:
                j.error = error
