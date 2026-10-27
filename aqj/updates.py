"""Checks GitHub Releases for a newer version. Sends nothing but the request itself."""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import __version__, net

LATEST_URL = "https://api.github.com/repos/micorytican/arma-queue-joiner/releases/latest"


@dataclass(frozen=True)
class Release:
    version: str
    url: str


def parse_version(text: str) -> tuple[int, ...]:
    """'v2.10.1' -> (2, 10, 1). Anything after the numbers (e.g. '-beta') is ignored."""
    match = re.match(r"^v?(\d+(?:\.\d+)*)", text.strip())
    if not match:
        raise ValueError(f"not a version: {text!r}")
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(candidate: str, current: str = __version__) -> bool:
    a, b = parse_version(candidate), parse_version(current)
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def latest_release() -> Release | None:
    """Return the latest release if it is newer than this build, else None."""
    data = net.get_json(LATEST_URL, headers={"Accept": "application/vnd.github+json"})
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name", ""))
    url = str(data.get("html_url", ""))
    if not tag or not url.startswith("https://github.com/"):
        return None
    return Release(tag.lstrip("v"), url) if is_newer(tag) else None
