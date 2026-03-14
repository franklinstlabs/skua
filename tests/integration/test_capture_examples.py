"""Example integration tests showing decorator usage.

These tests serve multiple purposes:
1. Test that Skua's core capture functionality works
2. Provide documentation examples
3. Seed the demo account with sample findings
4. Generate marketing content

NOTE: These tests require the backend to be running on localhost:8000.
Run `just dev-backend` in another terminal before running these tests.
They will be skipped if the backend is not available.
"""

import pytest
import requests
from skua.testing import docs_example, demo_finding, marketing_snippet


@pytest.fixture(scope="session", autouse=True)
def check_backend_available():
    """Skip all tests in this module if backend is not running."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=1)
        if response.status_code != 200:
            pytest.skip("Backend not healthy")
    except requests.exceptions.RequestException:
        pytest.skip("Backend not running on localhost:8000 - run `just dev-backend`")


@docs_example(
    slug="capture-matplotlib-basic",
    title="Capturing Matplotlib Figures",
    category="getting-started",
    order=10
)
@demo_finding(
    name="trig-functions",
    title="Trigonometric Functions",
    featured=True
)
@marketing_snippet(
    placement="hero",
    caption="From notebook to shareable insight in one line"
)
def test_capture_matplotlib_basic():
    """
    Capture a matplotlib figure to share with your team.

    Skua records the figure and returns a shareable URL that your
    stakeholders can access without any setup.
    """
    import matplotlib.pyplot as plt
    import numpy as np
    import skua

    # Create your visualization
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.linspace(0, 10, 100)
    ax.plot(x, np.sin(x * 2), label='sin(2x)', linewidth=2)
    ax.plot(x, np.cos(x * 2), label='cos(2x)', linewidth=2)
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_title('Trigonometric Functions')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Record it
    result = skua.record(fig, title="Trig Functions")

    # Share the URL
    print(f"View at: {result.url}")

    # Verify it worked
    assert result.url is not None
    assert "skua.dev/f/" in result.url or "localhost:5173/f/" in result.url


@docs_example(
    slug="capture-dataframe",
    title="Capturing Pandas DataFrames",
    category="getting-started",
    order=20
)
@demo_finding(
    name="employee-data",
    title="Employee Dataset Example"
)
def test_capture_dataframe():
    """
    Capture pandas DataFrames with sortable, filterable tables.

    DataFrames are displayed with pagination, sorting, and CSV export.
    """
    import pandas as pd
    import skua

    # Your analysis data
    df = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'Age': [25, 30, 35, 28, 32],
        'City': ['New York', 'San Francisco', 'Chicago', 'Boston', 'Seattle'],
        'Salary': [70000, 85000, 90000, 75000, 95000]
    })

    # Record it
    result = skua.record(df, title="Employee Data")

    print(f"Interactive table at: {result.url}")

    assert result.url is not None


@docs_example(
    slug="capture-text",
    title="Capturing Text and Code",
    category="getting-started",
    order=30
)
def test_capture_text():
    """
    Capture plain text, logs, or code snippets with syntax highlighting.
    """
    import skua

    # Your analysis summary
    summary = """# Q3 Analysis Summary

    Key Findings:
    - Revenue up 15% vs Q2
    - Customer acquisition cost down 8%
    - Churn rate improved to 2.1%

    Recommendation: Increase marketing budget for Q4
    """

    # Record it
    result = skua.record(summary, title="Q3 Summary")

    print(f"Formatted text at: {result.url}")

    assert result.url is not None


@marketing_snippet(
    placement="how-it-works-1",
    caption="Works in Jupyter, VS Code, Colab, or plain Python"
)
def test_simple_workflow():
    """Demonstrates the simplest possible Skua workflow."""
    import skua

    # Your analysis (simplified for marketing)
    results = {"revenue": 142000, "growth": 0.15}

    # Share it
    skua.record(results, title="Q3 Results")
    # → Live at https://skua.dev/f/abc123
