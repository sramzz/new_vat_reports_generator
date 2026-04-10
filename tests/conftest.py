import json
import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def pytest_collection_modifyitems(config, items):
    """Skip live tests unless explicitly requested with: pytest -m live"""
    marker_expr = config.getoption("-m", default="")
    if "live" in marker_expr:
        return
    skip_live = pytest.mark.skip(reason="live test — run with: uv run pytest -m live -v -s")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def _patch_media_upload(request, monkeypatch):
    """Patch MediaFileUpload for unit tests (skip for live tests that need real uploads)."""
    if "live" in request.keywords:
        return
    import unittest.mock
    monkeypatch.setattr(
        "drive.upload.MediaFileUpload",
        lambda path, **kwargs: unittest.mock.MagicMock(),
        raising=False,
    )


@pytest.fixture
def sample_query_result():
    with open(os.path.join(FIXTURES_DIR, "sample_query_result.json"), "r") as f:
        return json.load(f)


@pytest.fixture
def sample_store_mapping():
    with open(os.path.join(FIXTURES_DIR, "sample_store_mapping.json"), "r") as f:
        return json.load(f)


@pytest.fixture
def sample_last_run():
    with open(os.path.join(FIXTURES_DIR, "sample_last_run.json"), "r") as f:
        return json.load(f)
