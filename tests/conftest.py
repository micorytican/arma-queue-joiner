import os

import pytest

# CI runners have no interactive desktop; Qt renders off screen there.
if os.environ.get("CI"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_appdata(tmp_path, monkeypatch):
    """Never touch the real %APPDATA%\\ArmaQueueJoiner during tests."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    return tmp_path / "appdata"


def pytest_collection_modifyitems(config, items):
    if not os.environ.get("CI"):
        return
    skip = pytest.mark.skip(reason="needs a real desktop session")
    for item in items:
        if "desktop" in item.keywords:
            item.add_marker(skip)
