---
name: Fix image rendering after Docker deploy
overview: Ensure image sources returned by retrieval are addressable in a containerized deployment by (a) always emitting `asset_path` (relative) in metadata, (b) serving bytes via `/v1/assets/...` from the retriever through the orchestrator proxy, and (c) persisting/mounting `ETB_DOCUMENT_OUTPUT_DIR` so assets exist at runtime.
todos:
  - id: inspect-metadata
    content: Capture a failing source’s Raw metadata and identify whether `asset_path` is missing vs assets endpoint returning 404.
    status: completed
  - id: persist-artifacts
    content: Standardize `ETB_DOCUMENT_OUTPUT_DIR`/`ETB_UPLOAD_DIR` and ensure persistent mount exists for retriever artifacts in the deployment environment.
    status: completed
  - id: guarantee-asset-path
    content: Update document processing / indexing so image-related metadata always includes relative `asset_path` values.
    status: completed
  - id: ui-harden-fallbacks
    content: Update Streamlit image rendering to prefer `/v1/assets/...` and only use local filesystem paths when they are valid inside the container.
    status: completed
  - id: verify-end-to-end
    content: Validate `/v1/assets/...` works and UI renders images after redeploy.
    status: completed
isProject: false
---

# Fix image rendering after Docker deploy

## Diagnosis (what’s happening)

- The Streamlit UI renders images from source metadata in `app.py`.
- If a record contains `asset_path`, the UI fetches bytes from the orchestrator proxy (`/v1/assets/{asset_path}`) and calls `st.image(data, ...)`.
- If `asset_path` is missing or the fetch fails, the UI falls back to a local `path` and prints it when it doesn’t exist in the container (exact behavior with host absolute paths).

Key code paths:

- UI fetch & fallback: `[app.py](app.py)` (`_fetch_asset_bytes`, `_render_images_tab`)
- Orchestrator asset proxy: `[src/etb_project/orchestrator/app.py](src/etb_project/orchestrator/app.py)` (`GET /v1/assets/{asset_path:path}`)
- Retriever asset serving: `[src/etb_project/api/app.py](src/etb_project/api/app.py)` (`GET /v1/assets/{asset_path:path}` reads from `ETB_DOCUMENT_OUTPUT_DIR`)
- Caption doc metadata creation: `[src/etb_project/document_processing/processor.py](src/etb_project/document_processing/processor.py)` (sets both `path` and `asset_path`)

## Target outcome

- The UI **never relies on absolute host paths** for rendering images in deployed mode.
- Every image reference shown in Sources resolves to a working `GET /v1/assets/...` call.

## Data-flow to enforce

```mermaid
flowchart LR
  ui[Streamlit_UI] -->|POST_/v1/chat| orch[Orchestrator]
  orch -->|POST_/v1/retrieve| ret[Retriever]
  ui -->|GET_/v1/assets/{asset_path}| orch
  orch -->|GET_/v1/assets/{asset_path}| ret
  ret -->|FileResponse_from_ETB_DOCUMENT_OUTPUT_DIR| orch
```



## Implementation plan

- **Confirm the failing metadata shape**
  - In the UI’s “Raw” tab for a failing source, verify whether you see:
    - `image_captions[*].asset_path` present (good) vs missing (bad)
    - a `path` that is a host absolute path (bad in Docker)
  - This tells whether the failure is primarily **metadata** (no `asset_path`) or **storage** (assets not actually present/served).
- **Make assets persistent and consistently located in Docker**
  - Standardize on container paths:
    - `ETB_DOCUMENT_OUTPUT_DIR=/app/data/document_output`
    - `ETB_UPLOAD_DIR=/app/data/uploads`
  - Ensure the retriever service has a persistent volume mounted at `/app/data` (Compose already has `etb_data:/app/data` in `docker-compose.yml`).
  - If your deployment is not Compose, replicate this by attaching persistent storage at `/app/data` (or whichever path you set) so extracted images survive restarts.
- **Ensure retriever indexing writes `asset_path` as relative**
  - In `processor.py`, caption docs already compute `asset_path = str(info.path.relative_to(output_root))` with a fallback.
  - Add a hard guarantee: whenever you produce image metadata for retrieval/UI, include `asset_path` and keep it **relative to `ETB_DOCUMENT_OUTPUT_DIR`** (e.g. `images/page1_image1.png`).
  - Also ensure no downstream step drops `asset_path` during serialization/persistence or retrieval merge.
- **Ensure the retriever returns the right metadata for image results**
  - Verify the retriever returns caption documents (not only text chunks) when captioning is enabled.
  - Confirm `image_captions` records include `asset_path` (not just `path`).
  - If retrieval currently returns image records only via some other key (like `images` from `pages.json`), adapt the retrieval metadata to expose `image_captions` or update the UI to also consume that key.
- **Harden the UI behavior for deployed mode**
  - In `app.py`, change the image rendering logic so:
    - If `asset_path` is missing but `path` points under a known output root, derive `asset_path` from it.
    - If `path` is an absolute path on the host (not valid inside the container), do not attempt `Path.exists()`; instead show a clear error and the expected `asset_path` format.
- **Verification steps (post-fix)**
  - From inside the UI container (or from the host hitting exposed ports), verify:
    - `GET orchestrator:/v1/assets/images/<name>.png` returns `200` with `content-type: image/...`.
  - In the UI, “Images” tab should show the actual image (not a printed path).

## Files likely to change

- `[app.py](app.py)`
- `[src/etb_project/document_processing/processor.py](src/etb_project/document_processing/processor.py)`
- Potentially retriever persistence/loading layer if `asset_path` is being dropped (under `src/etb_project/vectorstore/` and `src/etb_project/api/state.py`).
- Deployment wiring (if not using Compose): environment variables + persistent storage attachment.
