"""Print the CHANGELOG section for one version (used by the release workflow).

Usage: python tools/release_notes.py 2.0.0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def section(changelog: str, version: str) -> str:
    pattern = rf"^## \[?{re.escape(version)}\]?.*?$(.*?)(?=^## |\Z)"
    match = re.search(pattern, changelog, flags=re.MULTILINE | re.DOTALL)
    if not match:
        raise SystemExit(f"No CHANGELOG entry for {version}")
    return match.group(1).strip()


if __name__ == "__main__":
    text = (Path(__file__).resolve().parent.parent / "CHANGELOG.md").read_text("utf-8")
    print(section(text, sys.argv[1].lstrip("v")))
