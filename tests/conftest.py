import json
import os
import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


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
