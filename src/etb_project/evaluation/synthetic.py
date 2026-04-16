from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from etb_project.evaluation.schemas import EvalRow
from etb_project.retrieval.loader import load_pdf


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None:
        return default
    v = v.strip()
    return v or default


def _openai_api_key() -> str | None:
    # Allow eval-specific override.
    return _env("ETB_EVAL_OPENAI_API_KEY") or _env("OPENAI_API_KEY")


def _openai_base_url() -> str | None:
    return _env("ETB_EVAL_OPENAI_BASE_URL") or _env("OPENAI_BASE_URL")


def build_generation_models() -> tuple[ChatOpenAI, OpenAIEmbeddings]:
    api_key = _openai_api_key()
    base_url = _openai_base_url()
    model = _env("ETB_EVAL_TESTSET_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
    secret = SecretStr(api_key) if api_key else None
    llm = ChatOpenAI(model=model, api_key=secret, base_url=base_url, temperature=0.2)
    embeddings = OpenAIEmbeddings(api_key=secret, base_url=base_url)
    return llm, embeddings


def generate_synthetic_questions_from_pdf(
    *,
    pdf_path: Path,
    testset_size: int,
) -> list[EvalRow]:
    """Generate a synthetic dataset from a PDF using RAGAS."""
    try:
        from ragas.testset.synthesizers.generate import TestsetGenerator
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            'ragas is not installed. Install with: pip install -e ".[eval]"'
        ) from exc

    docs = load_pdf(str(pdf_path))
    llm, embeddings = build_generation_models()
    generator = TestsetGenerator.from_langchain(llm=llm, embedding_model=embeddings)
    raw: Any = generator.generate_with_langchain_docs(docs, testset_size=testset_size)

    # Testset usually converts cleanly to pandas; keep extraction resilient.
    rows: list[EvalRow] = []
    try:
        df = raw.to_pandas()
        recs = df.to_dict(orient="records")
    except Exception:
        recs = list(getattr(raw, "samples", []))

    for r in recs:
        if isinstance(r, dict):
            q = str(r.get("question") or r.get("query") or "").strip()
            gt = r.get("ground_truth") or r.get("reference") or r.get("answer")
            if not q:
                continue
            rows.append(
                EvalRow(
                    question=q,
                    ground_truth=(
                        str(gt).strip() if isinstance(gt, str) and gt.strip() else None
                    ),
                    metadata={"source_pdf": str(pdf_path)},
                )
            )
    if not rows:
        raise RuntimeError("Synthetic generation produced zero questions.")
    return rows
