from __future__ import annotations

import subprocess
from pathlib import Path


def git_commit_eval_artifacts(
    *,
    repo_root: Path,
    paths_to_add: list[Path],
    commit_message: str,
) -> None:
    """Optionally stage + commit eval artifacts.

    This is only called when explicitly enabled via CLI/env.
    """
    rel_paths = [str(p.relative_to(repo_root)) for p in paths_to_add]
    subprocess.run(["git", "add", "--", *rel_paths], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", commit_message], cwd=repo_root, check=True)
