"""Decorators for marking tests as documentation/demo sources.

These decorators attach metadata to test functions that extraction scripts
can use to generate documentation, demo data, and marketing content.
"""

import functools
from typing import Callable, Optional


def docs_example(
    slug: str,
    title: str,
    category: str = "general",
    order: int = 50,
    screenshot: bool = False,
    stable_id: Optional[str] = None
) -> Callable:
    """Mark a test as a documentation example.

    The test's docstring becomes the prose description, and the test code
    (minus assertions) becomes the example code.

    Args:
        slug: Unique identifier for this example (used in filenames)
        title: Human-readable title for the example
        category: Documentation category (e.g., "getting-started", "visualization")
        order: Sort order within category (lower numbers appear first)
        screenshot: Whether to take an automated screenshot of the result
        stable_id: Force a stable ID for documentation consistency

    Example:
        @docs_example(
            slug="capture-matplotlib",
            title="Capturing Matplotlib Figures",
            category="visualization",
            order=10
        )
        def test_capture_matplotlib():
            '''Skua captures matplotlib figures with a single function call.'''
            import matplotlib.pyplot as plt
            import skua

            fig, ax = plt.subplots()
            ax.plot([1, 2, 3], [1, 4, 9])

            rec = skua.record(fig, "my-plot")
            assert rec.url is not None
    """
    def decorator(func: Callable) -> Callable:
        func._docs_example = {
            'slug': slug,
            'title': title,
            'category': category,
            'order': order,
            'screenshot': screenshot,
            'stable_id': stable_id,
        }
        return func
    return decorator


def demo_record(
    name: str,
    title: Optional[str] = None,
    featured: bool = False
) -> Callable:
    """Mark a test to create a record in demo mode.

    When pytest runs with --demo-mode, this test will create an actual
    record in the demo workspace instead of using mocks.

    Args:
        name: Unique name for this demo record
        title: Display title (defaults to name)
        featured: Whether to highlight this record in demo account

    Example:
        @demo_record(
            name="quarterly-revenue",
            title="Q3 Revenue Analysis",
            featured=True
        )
        def test_revenue_chart():
            '''Creates revenue chart for demo account.'''
            # ... create chart ...
            rec = skua.record(fig, "quarterly-revenue")
            assert rec.id is not None
    """
    def decorator(func: Callable) -> Callable:
        func._demo_record = {
            'name': name,
            'title': title or name,
            'featured': featured,
        }
        # Also mark with pytest marker for filtering
        return func
    return decorator


# Silent back-compat alias — `demo_record` is the canonical name now.
demo_finding = demo_record


def marketing_snippet(
    placement: str,
    caption: str = ""
) -> Callable:
    """Mark code for extraction into marketing materials.

    The test code is extracted and can be used in marketing pages,
    hero sections, "how it works" sections, etc.

    Args:
        placement: Where this snippet should appear (e.g., "hero", "how-it-works-1")
        caption: Caption or tagline for marketing use

    Example:
        @marketing_snippet(
            placement="hero",
            caption="Share analysis results in one line of code"
        )
        def test_simple_capture():
            import skua
            results = analyze_data()
            skua.record(results, "analysis")
            # → Live at https://skua.dev/r/abc123
    """
    def decorator(func: Callable) -> Callable:
        func._marketing_snippet = {
            'placement': placement,
            'caption': caption,
        }
        return func
    return decorator


def tutorial_cell(
    notebook: str,
    order: int,
    cell_type: str = "code",
    markdown_before: str = ""
) -> Callable:
    """Mark test code for inclusion in a generated tutorial notebook.

    Args:
        notebook: Name of tutorial notebook (e.g., "getting-started")
        order: Cell position in notebook (lower = earlier)
        cell_type: Jupyter cell type ("code" or "markdown")
        markdown_before: Optional markdown to insert before this cell

    Example:
        @tutorial_cell(
            notebook="getting-started",
            order=20,
            markdown_before="## Step 2: Capture Your First Record"
        )
        def test_first_capture():
            import skua
            rec = skua.record("Hello, Skua!", "first-record")
            print(f"View at: {rec.url}")
    """
    def decorator(func: Callable) -> Callable:
        func._tutorial_cell = {
            'notebook': notebook,
            'order': order,
            'cell_type': cell_type,
            'markdown_before': markdown_before,
        }
        return func
    return decorator
