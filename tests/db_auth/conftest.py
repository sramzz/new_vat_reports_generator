import pytest

from tests.db_auth._helpers import load_config


@pytest.fixture
def cfg():
    return load_config()
