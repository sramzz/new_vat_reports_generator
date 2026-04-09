import json
import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


@pytest.fixture(autouse=True)
def tmp_report_xlsx(tmp_path, monkeypatch):
    """Ensure /tmp/report.xlsx and similar test paths exist for Drive upload tests."""
    import unittest.mock
    # Patch MediaFileUpload so it doesn't open a real file during unit tests
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
