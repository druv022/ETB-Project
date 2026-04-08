#!/usr/bin/env python3
"""One-off utility: strip ``[string]`` prefixes from a CSV cell dump.

Edit ``file_path`` to point at the file you want to fix, then run locally.
This is not invoked by CI or the ``etb_project`` package.
"""

from __future__ import annotations

import sys
from pathlib import Path

# TODO: set this to your CSV before running (was a developer-local path).
file_path = Path(
    r"e:\Purdue MBT\Academics\Spring_2026_classes\59000_Emerging_Tech_and Business\AI_Tech_Project\Synthetic_Retail_data\transaction_database_2020_JanFeb.csv"
)


def main() -> None:
    if not file_path.is_file():
        print(f"File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    content = file_path.read_text(encoding="utf-8")
    cleaned_content = content.replace("[string]", "")
    file_path.write_text(cleaned_content, encoding="utf-8")
    print("File cleaned successfully! All [string] prefixes removed.")


if __name__ == "__main__":
    main()
