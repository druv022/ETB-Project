"""
LLM client utilities for report narratives.

This module provides a thin wrapper around a reasoning-capable chat
model so that the reporting workflow can remain largely
provider-agnostic. It is intentionally lightweight: configuration is
driven by environment variables, and the public interface is a single
`generate_report_narrative` function.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, TypedDict

import pandas as pd
import yaml
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI


@dataclass(frozen=True)
class LLMConfig:
    """Configuration for the narrative LLM backend."""

    backend: str = "openai"
    model: str | None = None
    api_base: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    timeout: int | None = 60

    @classmethod
    def from_file(
        cls,
        backend_override: str | None = None,
        model_override: str | None = None,
    ) -> LLMConfig:
        """
        Build an `LLMConfig` from a YAML file under this tools package,
        with environment variables and explicit overrides layered on top.

        Precedence (highest → lowest):
        - explicit overrides
        - environment variables
        - YAML file values
        - hardcoded defaults
        """

        config_path = Path(__file__).with_name("llm_config.yaml")
        file_data: dict[str, Any] = {}
        if config_path.exists():
            try:
                loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            except Exception:
                loaded = None
            if isinstance(loaded, dict):
                file_data = loaded

        env_backend = os.getenv("REPORT_LLM_BACKEND")
        env_model = os.getenv("REPORT_LLM_MODEL")
        env_api_base = os.getenv("REPORT_LLM_API_BASE")
        env_api_key_env = os.getenv("REPORT_LLM_API_KEY_ENV")

        backend = (
            backend_override or env_backend or file_data.get("backend") or "openai"
        )
        model = model_override or env_model or file_data.get("model")
        api_base = env_api_base or file_data.get("api_base")
        api_key_env = env_api_key_env or file_data.get("api_key_env")

        temperature = float(file_data.get("temperature", 0.2))
        max_tokens_val = file_data.get("max_tokens")
        timeout_val = file_data.get("timeout", 60)

        return cls(
            backend=backend,
            model=model,
            api_base=api_base,
            api_key_env=api_key_env,
            temperature=temperature,
            max_tokens=max_tokens_val,
            timeout=int(timeout_val),
        )


class EvaluationConfig(TypedDict, total=False):
    evaluation_enabled: bool
    evaluation_min_score: float
    max_regeneration_attempts: int
    evaluation_system_prompt: str
    rewrite_system_prompt: str


def load_evaluation_config() -> EvaluationConfig:
    """
    Load optional evaluation-related settings from llm_config.yaml.
    """

    config_path = Path(__file__).with_name("llm_config.yaml")
    if not config_path.exists():
        return {}

    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(loaded, dict):
        return {}

    cfg: EvaluationConfig = {}
    if "evaluation_enabled" in loaded:
        cfg["evaluation_enabled"] = bool(loaded.get("evaluation_enabled"))
    if "evaluation_min_score" in loaded:
        try:
            cfg["evaluation_min_score"] = float(loaded.get("evaluation_min_score"))
        except (TypeError, ValueError):
            pass
    if "max_regeneration_attempts" in loaded:
        try:
            cfg["max_regeneration_attempts"] = int(
                loaded.get("max_regeneration_attempts")
            )
        except (TypeError, ValueError):
            pass
    if "evaluation_system_prompt" in loaded:
        cfg["evaluation_system_prompt"] = str(
            loaded.get("evaluation_system_prompt") or ""
        )
    if "rewrite_system_prompt" in loaded:
        cfg["rewrite_system_prompt"] = str(loaded.get("rewrite_system_prompt") or "")

    return cfg


@dataclass(frozen=True)
class ReportLLMPrompts:
    """Prompts for report narrative, evaluation, and rewrite (tools-local YAML)."""

    narrative_system_parts: tuple[str, ...]
    narrative_user_template: str
    evaluation_user_template: str
    rewrite_user_template: str


def _read_llm_config_yaml() -> dict[str, Any]:
    config_path = Path(__file__).with_name("llm_config.yaml")
    if not config_path.exists():
        return {}
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


_DEFAULT_NARRATIVE_SYSTEM_PARTS: tuple[str, ...] = (
    "You are an expert retail analytics consultant.",
    "Write clear, business-friendly PDF report narratives in plain English.",
    "Base all statements strictly on the provided data.",
    "When the data is insufficient to support a claim, explicitly state the limitation instead of guessing.",
)

_DEFAULT_NARRATIVE_USER_TEMPLATE = (
    "You are preparing a narrative for a PDF analytics report.\n\n"
    "Use the JSON data below to write a cohesive narrative that includes:\n"
    "1) a short executive summary,\n"
    "2) key drivers and patterns you see in the data,\n"
    "3) any notable anomalies, risks, or data gaps, and\n"
    "4) 2–4 concrete, action-oriented recommendations for retail stakeholders.\n\n"
    "Keep the language concise and non-technical. "
    "Aim for roughly {target_words} words, but do not pad with obviously generic filler. "
    "Work strictly from the provided data and clearly mark any assumptions.\n\n"
    "Here is the data as JSON:\n\n"
    "{context_json}"
)

_DEFAULT_EVALUATION_USER_TEMPLATE = (
    "Evaluate the quality of the following report.\n"
    "Provide three things in plain text:\n"
    "1) A numeric score from 0 to 10.\n"
    "2) A short justification (2–4 sentences).\n"
    "3) 3–5 concrete bullet-point suggestions for improvement.\n\n"
    "Here is the report context as JSON:\n\n"
    "{payload_json}"
)

_DEFAULT_REWRITE_USER_TEMPLATE = (
    "Rewrite the report narrative to address the evaluator's feedback.\n"
    "Do not invent new facts; stay consistent with the original narrative's data.\n\n"
    "Here is the context as JSON:\n\n"
    "{payload_json}"
)


def load_report_llm_prompts() -> ReportLLMPrompts:
    """Load narrative/eval/rewrite user templates from ``llm_config.yaml``."""
    data = _read_llm_config_yaml()
    raw_parts = data.get("narrative_system_parts")
    if (
        isinstance(raw_parts, list)
        and raw_parts
        and all(isinstance(x, str) for x in raw_parts)
    ):
        narrative_parts = tuple(str(x) for x in raw_parts)
    else:
        narrative_parts = _DEFAULT_NARRATIVE_SYSTEM_PARTS

    nut = data.get("narrative_user_template")
    narrative_user = (
        str(nut).strip()
        if isinstance(nut, str) and str(nut).strip()
        else _DEFAULT_NARRATIVE_USER_TEMPLATE
    )

    eut = data.get("evaluation_user_template")
    evaluation_user = (
        str(eut).strip()
        if isinstance(eut, str) and str(eut).strip()
        else _DEFAULT_EVALUATION_USER_TEMPLATE
    )

    rut = data.get("rewrite_user_template")
    rewrite_user = (
        str(rut).strip()
        if isinstance(rut, str) and str(rut).strip()
        else _DEFAULT_REWRITE_USER_TEMPLATE
    )

    return ReportLLMPrompts(
        narrative_system_parts=narrative_parts,
        narrative_user_template=narrative_user,
        evaluation_user_template=evaluation_user,
        rewrite_user_template=rewrite_user,
    )


def summarise_stats_for_llm(
    stats: Mapping[str, object],
    max_rows: int = 5,
) -> dict[str, Any]:
    """
    Convert heterogeneous stats into a JSON-serialisable summary.

    - `pandas.DataFrame` → list of row dicts (head only)
    - `pandas.Series` → dict of key → value (head only)
    - `Mapping` → plain dict
    - everything else is passed through as-is
    """

    summary: dict[str, Any] = {}

    for key, value in stats.items():
        if isinstance(value, pd.DataFrame):
            summary[key] = value.head(max_rows).to_dict(orient="records")
        elif isinstance(value, pd.Series):
            summary[key] = value.head(max_rows).to_dict()
        elif isinstance(value, Mapping):
            summary[key] = dict(value)
        else:
            summary[key] = value

    return summary


def generate_report_narrative(
    *,
    category: str,
    period_label: str,
    period_start: date,
    period_end: date,
    granularity: str | None,
    stats: Mapping[str, object],
    baseline_narrative: str | None,
    target_words: int,
    backend: str | None = None,
    model: str | None = None,
    style: str | None = None,
) -> str:
    """
    Generate a narrative for a single report period using an LLM.

    The function is intentionally opinionated but minimal:

    - it shapes the `stats` dict into a compact JSON payload
    - it constructs a prompt that asks for an executive summary,
      key drivers, anomalies, and concrete recommendations
    - it calls a chat model (currently OpenAI via `langchain-openai`)
    - it returns the model's text content or raises on failure
    """

    config = LLMConfig.from_file(backend_override=backend, model_override=model)

    provider = config.backend
    if provider not in {"openai", "openrouter", "ollama"}:
        raise ValueError(f"Unsupported LLM backend: {provider}")

    model_name = config.model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    structured_stats = summarise_stats_for_llm(stats)
    rp = load_report_llm_prompts()

    system_parts = list(rp.narrative_system_parts)
    if style:
        system_parts.append(f"Preferred narrative style: {style}")
    system_prompt = " ".join(system_parts)

    context = {
        "category": category,
        "period_label": period_label,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "granularity": granularity,
        "target_words": target_words,
        "stats": structured_stats,
        "baseline_narrative": baseline_narrative,
    }

    user_prompt = rp.narrative_user_template.format(
        target_words=target_words,
        context_json=json.dumps(context, default=str, ensure_ascii=False),
    )

    if provider == "ollama":
        llm = ChatOllama(
            model=model_name,
            base_url=config.api_base or "http://localhost:11434",
        )
    else:
        # OpenAI-style HTTP APIs, including OpenRouter via a custom base URL.
        openai_kwargs: dict[str, Any] = {}
        if config.api_base:
            openai_kwargs["base_url"] = config.api_base
        if config.api_key_env:
            api_key = os.getenv(config.api_key_env)
            if api_key:
                openai_kwargs["api_key"] = api_key

        llm = ChatOpenAI(
            model=model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
            **openai_kwargs,
        )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    content = getattr(response, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM returned an empty narrative.")
    return content.strip()


def _build_llm_client(
    *,
    backend: str | None = None,
    model: str | None = None,
) -> tuple[Any, LLMConfig]:
    """
    Internal helper to construct an LLM client using the same config logic.
    """

    config = LLMConfig.from_file(backend_override=backend, model_override=model)
    provider = config.backend
    if provider not in {"openai", "openrouter", "ollama"}:
        raise ValueError(f"Unsupported LLM backend: {provider}")

    model_name = config.model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if provider == "ollama":
        llm = ChatOllama(
            model=model_name,
            base_url=config.api_base or "http://localhost:11434",
        )
    else:
        openai_kwargs: dict[str, Any] = {}
        if config.api_base:
            openai_kwargs["base_url"] = config.api_base
        if config.api_key_env:
            api_key = os.getenv(config.api_key_env)
            if api_key:
                openai_kwargs["api_key"] = api_key

        llm = ChatOpenAI(
            model=model_name,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
            **openai_kwargs,
        )

    return llm, config


def evaluate_report_quality(
    *,
    category: str,
    granularity: str | None,
    period_label: str,
    period_start: date,
    period_end: date,
    narrative_text: str,
    chart_titles: list[str] | None = None,
    backend: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    Use an LLM to rate the quality of a generated report.

    Returns a dict with at least:
    - score (float)
    - justification (str)
    - suggestions (list[str])
    - raw_text (str)
    """

    eval_cfg = load_evaluation_config()
    rp = load_report_llm_prompts()
    system_prompt = eval_cfg.get(
        "evaluation_system_prompt",
        "You are a senior management consultant evaluating PDF report quality.",
    )

    payload = {
        "category": category,
        "granularity": granularity,
        "period_label": period_label,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "narrative_text": narrative_text,
        "chart_titles": chart_titles or [],
    }

    user_prompt = rp.evaluation_user_template.format(
        payload_json=json.dumps(payload, ensure_ascii=False, default=str),
    )

    llm, _ = _build_llm_client(backend=backend, model=model)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    text = getattr(response, "content", "") or ""
    text = str(text).strip()

    # Simple heuristic parsing to extract a numeric score.
    score: float | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Look for something like "Score: 7.5" or "7.5/10"
        for token in (
            line.replace("Score", "").replace("score", "").replace(":", " ").split()
        ):
            try:
                val = float(token.replace("/10", ""))
                if 0.0 <= val <= 10.0:
                    score = val
                    break
            except ValueError:
                continue
        if score is not None:
            break

    result: dict[str, Any] = {
        "raw_text": text,
        "score": score,
    }
    return result


def rewrite_report_narrative(
    *,
    category: str,
    granularity: str | None,
    period_label: str,
    period_start: date,
    period_end: date,
    original_narrative: str,
    evaluation_feedback: str,
    backend: str | None = None,
    model: str | None = None,
) -> str:
    """
    Use an LLM to rewrite a report narrative based on evaluation feedback.
    """

    eval_cfg = load_evaluation_config()
    rp = load_report_llm_prompts()
    system_prompt = eval_cfg.get(
        "rewrite_system_prompt",
        "You are a senior consultant improving report narratives.",
    )

    payload = {
        "category": category,
        "granularity": granularity,
        "period_label": period_label,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "original_narrative": original_narrative,
        "evaluation_feedback": evaluation_feedback,
    }

    user_prompt = rp.rewrite_user_template.format(
        payload_json=json.dumps(payload, ensure_ascii=False, default=str),
    )

    llm, _ = _build_llm_client(backend=backend, model=model)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]
    response = llm.invoke(messages)
    content = getattr(response, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM returned an empty rewritten narrative.")
    return content.strip()


__all__ = [
    "LLMConfig",
    "ReportLLMPrompts",
    "summarise_stats_for_llm",
    "generate_report_narrative",
    "load_evaluation_config",
    "load_report_llm_prompts",
    "evaluate_report_quality",
    "rewrite_report_narrative",
]
