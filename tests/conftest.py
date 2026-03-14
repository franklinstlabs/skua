"""
Shared pytest fixtures for python-package tests.
"""

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
        "url": "https://skua.dev/s/test123"
    }
    return client


@pytest.fixture
def sample_matplotlib_figure():
    """
    Provide a sample matplotlib figure for testing.

    Note: Only available if matplotlib is installed (optional dependency).
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
    """
    Provide a sample pandas DataFrame for testing.

    Note: Only available if pandas is installed (optional dependency).
    """
    try:
        import pandas as pd
        return pd.DataFrame({
            "a": [1, 2, 3],
            "b": [4, 5, 6]
        })
    except ImportError:
        pytest.skip("pandas not installed")


@pytest.fixture(scope="session")
def backend_url():
    """
    Provide backend URL and verify it's available.

    Integration tests expect backend to be running on localhost:8000.
    Run `just dev-backend` in another terminal before running tests.
    """
    url = "http://localhost:8000"

    # Quick health check to fail fast if backend isn't running
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
    """
    Provide a shared requests.Session for connection pooling.

    Reusing connections significantly speeds up integration tests.
    Session is closed after all tests complete.
    """
    session = requests.Session()
    # Configure connection pooling
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=0  # Don't retry in tests
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    yield session

    session.close()
