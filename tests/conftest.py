"""Shared pytest fixtures for python-package tests."""

import pytest
import requests
from unittest.mock import Mock


@pytest.fixture
def mock_api_client():
    """Provide a mock HTTP client for testing without real API calls."""
    client = Mock()
    client.post.return_value.status_code = 200
    client.post.return_value.json.return_value = {
        "id": "test123",
        "url": "https://skua.dev/r/test123"
    }
    return client


@pytest.fixture
def sample_matplotlib_figure():
    """Sample matplotlib figure for testing.

    Note: Only available if matplotlib is installed.
    """
    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])
        yield fig
        plt.close(fig)
    except ImportError:
        pytest.skip("matplotlib not installed")


@pytest.fixture
def sample_dataframe():
    """Sample pandas DataFrame for testing.

    Note: Only available if pandas is installed.
    """
    try:
        import pandas as pd
        return pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    except ImportError:
        pytest.skip("pandas not installed")


@pytest.fixture(scope="session")
def backend_url():
    """Backend URL for integration tests; verifies it's running."""
    url = "http://localhost:8000"
    try:
        response = requests.get(f"{url}/health", timeout=1)
        if response.status_code != 200:
            pytest.fail(f"Backend health check failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        pytest.fail("Backend not running on localhost:8000 - run `just dev-backend`")
    except requests.exceptions.Timeout:
        pytest.fail("Backend timeout - check if backend is healthy")
    return url


@pytest.fixture(scope="session")
def http_session():
    """Shared requests.Session for connection pooling in integration tests."""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=0,
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    yield session
    session.close()
