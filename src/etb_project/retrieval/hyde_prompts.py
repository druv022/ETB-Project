"""HyDE (Hypothetical Document Embeddings) prompts for the retriever service.

These prompts are deliberately *not* "assistant answers".
The goal is to generate embed-friendly text that resembles an excerpt from the
indexed corpus, because HyDE uses the synthetic passage for retrieval signal.
Answering the user (or emitting lists/markdown) tends to shift the text away
from corpus prose and can hurt retrieval quality.
"""

HYDE_SYSTEM = """You write short passages that could appear in a technical or business document corpus.

Rules:
- Output exactly one paragraph of plain text.
- Write hypothetical document prose that might contain answers related to the topic of the user message.
- Do NOT answer the user directly, give advice, or use markdown headings or bullet lists.
- Do NOT include meta-commentary about what you are doing."""

HYDE_USER_TEMPLATE = """User message (retrieval query):

{query}

Write one paragraph of hypothetical corpus text that would be a plausible excerpt from an indexed document about this topic."""
