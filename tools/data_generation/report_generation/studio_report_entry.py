"""LangGraph Studio entrypoint for the reporting workflow.

This module exposes ``build_report_graph`` via a simple factory function so
that LangGraph Studio (and ``langgraph dev``) can discover and run the
reporting graph.
"""

from __future__ import annotations

from tools.data_generation.report_generation.report_langgraph import build_report_graph


def report_app():
    """Return the compiled reporting graph for LangGraph Studio."""

    return build_report_graph()


__all__ = ["report_app"]
