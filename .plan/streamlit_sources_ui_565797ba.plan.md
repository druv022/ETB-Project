---
name: Streamlit sources UI
overview: Improve the Streamlit web chat UI to present retrieved sources in a visually appealing, readable way (cards + tabs + image thumbnails + collapsible raw metadata) without changing retrieval behavior or deduping sources.
todos:
  - id: ui-renderer
    content: Replace dict-style source rendering in `app.py` with card header + tabs (Excerpt/Images/Raw) and thumbnail gallery for `image_captions`.
    status: in_progress
  - id: helpers-tests
    content: If new pure helpers are added, create focused unit tests for them under `tests/`.
    status: pending
  - id: verify-docs
    content: Manually verify in Streamlit; log prompt to `PROMPTS.md` and update `README_chatbot.md` only if you want the UI change documented.
    status: pending
isProject: false
---

# Streamlit sources UI refresh

## Goal

Make the `Sources` section in the Streamlit chat UI visually appealing and scannable by:

- showing a compact citation header (file name + page)
- putting excerpt / images / raw metadata into tabs
- rendering `image_captions` as thumbnails with caption text
- rendering raw metadata via `st.json()` instead of `f"{meta}"`

## Where the current behavior lives

- Streamlit UI renders sources by printing the entire metadata dict:
  - `[app.py](app.py)` lines ~253–261:

```254:261:app.py
if sources:
    with st.expander("Sources", expanded=False):
        for i, s in enumerate(sources, 1):
            content = (s.get("content") or "").strip()
            meta = s.get("metadata") or {}
            st.markdown(f"**{i}.** {meta}")
            if content:
                st.markdown(content)
```

- `image_captions` is attached to chunk metadata during PDF processing (already structured as a list of dicts):
  - `[src/etb_project/document_processing/processor.py](src/etb_project/document_processing/processor.py)` lines ~214–233.

## UI design to implement (Streamlit-native)

Within the existing `Sources` expander, render each source as a “card”:

- **Header**: `N. filename • p.X/Y` (derived from `metadata['source']`, `page`, `total_pages`)
- **Tabs** (`st.tabs`):
  - **Excerpt**: show `s['content']` (existing)
  - **Images**:
    - If `metadata['image_captions']` exists and is a list of `{path, caption}`:
      - show thumbnails in a 2–3 column grid using `st.columns` + `st.image`
      - show caption as `st.caption` with a short clamp (e.g., first 200–300 chars)
    - Else if the source itself is an image-caption document (has `metadata['path']` / `image_index` / `xref` / `caption_source`):
      - show that single image via `st.image` and caption text
  - **Raw**: `st.json(metadata, expanded=False)`

Notes:

- Per your request, **ignore duplicate information** for now (no deduping / grouping changes).
- Keep paths robust: only call `st.image` if the path exists; otherwise show the caption + the path as text.

## Code changes

- Update `[app.py](app.py)`:
  - Add small helper(s) near the top (e.g., `_format_citation(meta)` and `render_source_card(i, s)`), or keep it inline if you prefer.
  - Replace the current loop inside the `Sources` expander with the card+tabs rendering described above.

## Tests

Streamlit UI code isn’t easily unit-testable end-to-end, but to stay consistent with the repo’s strong testing posture:

- If helpers are introduced (pure functions like citation formatting and image-caption extraction), add unit tests under:
  - `[tests/](tests/)`
- Keep UI rendering itself manual-verified.

## Manual verification checklist

- Run `streamlit run app.py`
- Ask a query that returns sources with:
  - normal text chunks (no images)
  - chunks that include `image_captions`
  - image-caption documents (`metadata['path']`, `caption_source`)
- Confirm:
  - the Sources expander opens cleanly
  - no dict blobs appear in the main view
  - images render as thumbnails when paths exist
  - Raw tab shows metadata in a readable collapsed JSON view

## Documentation / prompt logging

- Append this prompt to `PROMPTS.md` (workspace rule).
- If you want, add a short note to `README_chatbot.md` that Sources now render in tabs with image previews.
