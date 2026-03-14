"""Testing utilities for Skua.

This module provides decorators and fixtures for writing tests that also
serve as documentation examples, demo data sources, and marketing content.
"""

from .decorators import (
    docs_example,
    demo_finding,
    marketing_snippet,
    tutorial_cell,
)

__all__ = [
    "docs_example",
    "demo_finding",
    "marketing_snippet",
    "tutorial_cell",
]
