"""Retrieval-specific errors."""


class HybridSparseUnavailableError(Exception):
    """``strategy=hybrid`` requested but sparse corpus is missing or unloadable."""
