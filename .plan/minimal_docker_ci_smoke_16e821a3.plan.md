---
name: Minimal Docker CI smoke
overview: Add GitHub Actions jobs that build the project Docker image on Linux (Ubuntu) with a `/v1/health` smoke test, and build the same image on Windows to catch host-specific path/context issues; plus `.gitattributes` and docs for all developers.
todos:
  - id: ci-docker-job
    content: "Add `docker-smoke` job on `ubuntu-latest` to `.github/workflows/ci.yml` (build, run, curl /v1/health, logs on fail, cleanup with if: always)"
    status: completed
  - id: ci-docker-windows
    content: Add `docker-build-windows` job on `windows-latest` that runs `docker build` (see plan for setup/optional smoke); include `build` in `needs:` alongside linux job
    status: completed
  - id: gate-build
    content: Wire `build` job `needs:` to include `docker-smoke` and `docker-build-windows` (or document alternative if keeping informational only)
    status: completed
  - id: gitattributes
    content: Add `.gitattributes` with `*.sh text eol=lf` (+ optional Dockerfile)
    status: completed
  - id: docs-dev-readme
    content: Update `docs/DEVELOPMENT.md` + brief README pointer for CI/local Docker smoke and Windows/WSL2 notes
    status: completed
  - id: prompts-readme-rule
    content: Append timestamped entry to `PROMPTS.md` per workspace rule; adjust README only if execution instructions change materially
    status: completed
isProject: false
---

# Minimal Docker smoke test (MVP)

## Goal

Automate the **same Linux-container path** every developer uses (`Dockerfile` → run retriever) so broken installs, bad `COPY`, or startup failures are caught on PRs **before** merge. This does **not** replace pytest; it complements it.

## What the MVP includes


| Piece                                              | Purpose                                                                                                                                                               |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CI job** (`docker-smoke`) on **Ubuntu**          | `docker build` + `docker run` + HTTP GET `[/v1/health](src/etb_project/api/app.py)`                                                                                   |
| **CI job** (`docker-build-windows`) on **Windows** | `docker build` against the same `Dockerfile` and context (Linux container image) to catch Windows-only breakages (paths, `.dockerignore`, line endings, context size) |
| `**.gitattributes`**                               | Force `LF` for shell scripts under `[docker/](docker/)` so Windows checkouts do not break Linux entrypoints (`ollama-entrypoint.sh`, etc.)                            |
| **Docs**                                           | Short section in `[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)` (and a pointer in `[README.md](README.md)` if the README documents CI—keep it one paragraph)            |


Optional one-liner in the same job: `docker compose config` (validates `[docker-compose.yml](docker-compose.yml)` syntax; no containers started).

## CI design (`[.github/workflows/ci.yml](.github/workflows/ci.yml)`)

Add a new job, e.g. `**Docker smoke`**, with:

- `**runs-on: ubuntu-latest`** — GitHub-hosted runners include Docker; this is the canonical environment for the image.
- **Steps (conceptual):**
  1. `actions/checkout@v4`
  2. Build: `docker build -t etb:ci .` (repo root; same context as local dev)
  3. Run detached: map host `8000` → container `8000`, name container for cleanup
  4. Wait for readiness: loop `curl -sf http://127.0.0.1:8000/v1/health` with retries/backoff (uvicorn needs a moment)
  5. On failure: `docker logs` for the named container to surface errors in the Actions log
  6. Always stop/remove the container (use `if: always()` on cleanup step)

**Job ordering:** Run `**docker-smoke` in parallel** with `lint` / `test` / `security` to keep PR feedback fast. For MVP, either:

- **A (recommended):** Add `docker-smoke` to `**build` job’s `needs:`** so a broken Docker path blocks the existing “Build” stage, or
- **B:** Leave `build` unchanged and let `docker-smoke` be informational only (not recommended if you want a hard gate).

Pick **A** unless you explicitly want Docker failures not to block merges.

**Out of scope for MVP:** Full `docker compose up` with Ollama (slow, model pulls, flaky). The retriever image alone + `/v1/health` matches the earlier “minimal” scope.

### Windows image build job (`docker-build-windows`)

Add a **second** job, e.g. `**docker-build-windows`**, with:

- `**runs-on: windows-latest`** (or `windows-2022` if you pin the image for stability).

**Minimum scope (required):**

- Checkout, then `**docker build -t etb:ci-win .`** at repo root — same `Dockerfile` and build context as Linux. This validates that developers on **Windows + Docker Desktop** (Linux containers) do not hit unique failures when building.

**Implementation caveat (verify at implementation time):** GitHub-hosted **Windows** runners may **not** include a working Docker daemon by default; the implementer should confirm against the current [runner-images](https://github.com/actions/runner-images) Windows software list. If Docker is missing, add an **explicit setup** step using a supported pattern (e.g. official Docker or Microsoft docs for Docker on GHA Windows, or a maintained community action that installs Docker Engine/CLI for Windows). If Windows Docker setup proves **too slow or flaky** for PRs, document a fallback: keep Ubuntu smoke + document manual Windows `docker build`, and make the Windows job **continue-on-error** or move it to a scheduled workflow — only as a last resort after trying a standard install path.

**Optional stretch (if the runner supports Linux containers reliably after build):**

- `docker run -d -p 8000:8000 ...` then `**Invoke-WebRequest`** (PowerShell) to `http://127.0.0.1:8000/v1/health` with retries, plus cleanup with `if: always()`. If this is brittle on `windows-latest`, **omit** and rely on Ubuntu for the HTTP smoke.

**Gate:** Include `**docker-build-windows`** in the `**build` job’s `needs:`** alongside `**docker-smoke`** so both platforms must pass before the Python sdist/wheel build stage (same policy as the Linux-only recommendation above).

## `.gitattributes` (cross-platform hygiene)

Add at repo root (file does not exist today):

- `*.sh text eol=lf`
- Optionally: `Dockerfile text eol=lf` and `*.dockerignore` as text

This reduces “works on Linux CI but breaks on Windows clone” for scripts mounted into containers.

## Requirements by audience

### MVP / CI (what must be true)

- Nothing new to **install in the repo** — no extra Python deps.
- **Ubuntu job:** Docker available on `ubuntu-latest` (typical).
- **Windows job:** Docker CLI + daemon (or equivalent) must be available or installed in the workflow; no Python deps.

### Developers — Linux / macOS

- **Docker Engine** or **Docker Desktop** installed; **Compose v2** (`docker compose`).
- Reproduce CI locally from repo root:
  - `docker build -t etb:ci .`
  - `docker run --rm -p 8000:8000 etb:ci` then `curl -s http://127.0.0.1:8000/v1/health`
- Git: avoid committing CRLF into `*.sh` (`.gitattributes` helps).

### Developers — Windows

- **Docker Desktop** with **WSL2 backend** (recommended path for bind mounts and Linux containers).
- Use the **same** `docker build` / `docker run` / `curl` flow from a shell that can reach Docker (PowerShell, cmd, or WSL — document that **WSL or Git Bash** is simplest for `curl` parity with docs).
- Same `.gitattributes` benefit for `[docker/*.sh](docker/)`.

### What this does **not** guarantee

- **Windows job** proves `**docker build` from a Windows host** in CI, not every edge case of Docker Desktop on a developer laptop (licensing, VPN, hypervisor).
- It does **not** validate the full stack (Ollama + orchestrator + UI); that remains manual or a future nightly workflow.

## Documentation edits

- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** — Under **Docker**, add: (1) “CI runs Docker build on **Ubuntu** (with `/v1/health` smoke) and `**docker build` on Windows**”; (2) copy-paste commands to mirror locally; (3) one sentence on Windows + WSL2 + line endings.
- `**[README.md](README.md)`** — One line under Contributing/CI or Docker pointing to DEVELOPMENT for the Docker smoke details (only if it fits existing structure; avoid duplicating long instructions).

## Verification after implementation

- Open a test PR or push to a branch that runs CI; confirm the new job passes and fails intentionally if `Dockerfile` CMD or health route regresses.
