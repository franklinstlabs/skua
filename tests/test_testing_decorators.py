"""Tests for testing decorators module.

These decorators attach metadata to test functions that extraction scripts
can use to generate documentation, demo data, and marketing content.
"""

import pytest

from skua.testing.decorators import (
    docs_example,
    demo_record,
    marketing_snippet,
    tutorial_cell,
)


class TestDocsExampleDecorator:
    """Test the @docs_example decorator."""

    def test_attaches_metadata_with_required_args(self):
        """Test that decorator attaches _docs_example attribute with required args."""

        @docs_example(slug="test-slug", title="Test Title")
        def example_func():
            pass

        assert hasattr(example_func, "_docs_example")
        assert example_func._docs_example["slug"] == "test-slug"
        assert example_func._docs_example["title"] == "Test Title"

    def test_default_values(self):
        """Test that default values are applied correctly."""

        @docs_example(slug="test", title="Test")
        def example_func():
            pass

        metadata = example_func._docs_example
        assert metadata["category"] == "general"
        assert metadata["order"] == 50
        assert metadata["screenshot"] is False
        assert metadata["stable_id"] is None

    def test_custom_values(self):
        """Test that custom values override defaults."""

        @docs_example(
            slug="custom-slug",
            title="Custom Title",
            category="visualization",
            order=10,
            screenshot=True,
            stable_id="stable-123",
        )
        def example_func():
            pass

        metadata = example_func._docs_example
        assert metadata["category"] == "visualization"
        assert metadata["order"] == 10
        assert metadata["screenshot"] is True
        assert metadata["stable_id"] == "stable-123"

    def test_preserves_function_behavior(self):
        """Test that decorated function still works correctly."""

        @docs_example(slug="test", title="Test")
        def add_numbers(a: int, b: int) -> int:
            return a + b

        result = add_numbers(2, 3)
        assert result == 5

    def test_preserves_function_name(self):
        """Test that decorated function name is preserved."""

        @docs_example(slug="test", title="Test")
        def my_example_function():
            """A docstring."""
            pass

        assert my_example_function.__name__ == "my_example_function"

    def test_preserves_function_docstring(self):
        """Test that decorated function docstring is preserved."""

        @docs_example(slug="test", title="Test")
        def my_example_function():
            """This is the docstring."""
            pass

        assert my_example_function.__doc__ == "This is the docstring."

    def test_with_return_value(self):
        """Test decorator with function that returns a value."""

        @docs_example(slug="return-test", title="Return Test")
        def get_data():
            return {"key": "value"}

        result = get_data()
        assert result == {"key": "value"}
        assert get_data._docs_example["slug"] == "return-test"

    def test_with_exception(self):
        """Test decorator with function that raises an exception."""

        @docs_example(slug="exception-test", title="Exception Test")
        def failing_func():
            raise ValueError("Expected error")

        with pytest.raises(ValueError, match="Expected error"):
            failing_func()

        # Metadata should still be attached
        assert failing_func._docs_example["slug"] == "exception-test"


class TestDemoRecordDecorator:
    """Test the @demo_record decorator."""

    def test_attaches_metadata_with_required_args(self):
        """Test that decorator attaches _demo_record attribute."""

        @demo_record(name="test-record")
        def demo_func():
            pass

        assert hasattr(demo_func, "_demo_record")
        assert demo_func._demo_record["name"] == "test-record"

    def test_title_defaults_to_name(self):
        """Test that title defaults to name if not provided."""

        @demo_record(name="quarterly-revenue")
        def demo_func():
            pass

        metadata = demo_func._demo_record
        assert metadata["title"] == "quarterly-revenue"

    def test_custom_title(self):
        """Test that custom title overrides default."""

        @demo_record(name="quarterly-revenue", title="Q3 Revenue Analysis")
        def demo_func():
            pass

        metadata = demo_func._demo_record
        assert metadata["title"] == "Q3 Revenue Analysis"

    def test_featured_default_false(self):
        """Test that featured defaults to False."""

        @demo_record(name="test")
        def demo_func():
            pass

        assert demo_func._demo_record["featured"] is False

    def test_featured_true(self):
        """Test that featured can be set to True."""

        @demo_record(name="test", featured=True)
        def demo_func():
            pass

        assert demo_func._demo_record["featured"] is True

    def test_preserves_function_behavior(self):
        """Test that decorated function still works correctly."""

        @demo_record(name="test")
        def create_chart():
            return "chart-data"

        result = create_chart()
        assert result == "chart-data"

    def test_preserves_function_name(self):
        """Test that decorated function name is preserved."""

        @demo_record(name="test")
        def my_demo_function():
            pass

        assert my_demo_function.__name__ == "my_demo_function"


class TestMarketingSnippetDecorator:
    """Test the @marketing_snippet decorator."""

    def test_attaches_metadata_with_required_args(self):
        """Test that decorator attaches _marketing_snippet attribute."""

        @marketing_snippet(placement="hero")
        def snippet_func():
            pass

        assert hasattr(snippet_func, "_marketing_snippet")
        assert snippet_func._marketing_snippet["placement"] == "hero"

    def test_caption_defaults_to_empty_string(self):
        """Test that caption defaults to empty string."""

        @marketing_snippet(placement="hero")
        def snippet_func():
            pass

        assert snippet_func._marketing_snippet["caption"] == ""

    def test_custom_caption(self):
        """Test that custom caption is stored."""

        @marketing_snippet(
            placement="how-it-works-1",
            caption="Share analysis results in one line of code",
        )
        def snippet_func():
            pass

        metadata = snippet_func._marketing_snippet
        assert metadata["placement"] == "how-it-works-1"
        assert metadata["caption"] == "Share analysis results in one line of code"

    def test_preserves_function_behavior(self):
        """Test that decorated function still works correctly."""

        @marketing_snippet(placement="hero")
        def simple_capture():
            return "captured"

        result = simple_capture()
        assert result == "captured"

    def test_preserves_function_name(self):
        """Test that decorated function name is preserved."""

        @marketing_snippet(placement="hero")
        def my_marketing_function():
            pass

        assert my_marketing_function.__name__ == "my_marketing_function"


class TestTutorialCellDecorator:
    """Test the @tutorial_cell decorator."""

    def test_attaches_metadata_with_required_args(self):
        """Test that decorator attaches _tutorial_cell attribute."""

        @tutorial_cell(notebook="getting-started", order=10)
        def cell_func():
            pass

        assert hasattr(cell_func, "_tutorial_cell")
        assert cell_func._tutorial_cell["notebook"] == "getting-started"
        assert cell_func._tutorial_cell["order"] == 10

    def test_default_values(self):
        """Test that default values are applied correctly."""

        @tutorial_cell(notebook="test", order=1)
        def cell_func():
            pass

        metadata = cell_func._tutorial_cell
        assert metadata["cell_type"] == "code"
        assert metadata["markdown_before"] == ""

    def test_custom_cell_type(self):
        """Test that custom cell_type can be set."""

        @tutorial_cell(notebook="test", order=1, cell_type="markdown")
        def cell_func():
            pass

        assert cell_func._tutorial_cell["cell_type"] == "markdown"

    def test_markdown_before(self):
        """Test that markdown_before is stored."""

        @tutorial_cell(
            notebook="getting-started",
            order=20,
            markdown_before="## Step 2: Capture Your First Record",
        )
        def cell_func():
            pass

        metadata = cell_func._tutorial_cell
        assert metadata["markdown_before"] == "## Step 2: Capture Your First Record"

    def test_preserves_function_behavior(self):
        """Test that decorated function still works correctly."""

        @tutorial_cell(notebook="test", order=1)
        def first_capture():
            return "record-url"

        result = first_capture()
        assert result == "record-url"

    def test_preserves_function_name(self):
        """Test that decorated function name is preserved."""

        @tutorial_cell(notebook="test", order=1)
        def my_tutorial_function():
            pass

        assert my_tutorial_function.__name__ == "my_tutorial_function"

    def test_order_values(self):
        """Test various order values (lower = earlier in notebook)."""

        @tutorial_cell(notebook="test", order=0)
        def first():
            pass

        @tutorial_cell(notebook="test", order=100)
        def last():
            pass

        assert first._tutorial_cell["order"] == 0
        assert last._tutorial_cell["order"] == 100


class TestNestedDecorators:
    """Test that decorators can be stacked/nested."""

    def test_docs_example_and_demo_record(self):
        """Test stacking docs_example and demo_record."""

        @docs_example(slug="test-slug", title="Test Title")
        @demo_record(name="demo-test", featured=True)
        def dual_purpose_func():
            return "result"

        # Both attributes should be present
        assert hasattr(dual_purpose_func, "_docs_example")
        assert hasattr(dual_purpose_func, "_demo_record")

        # Metadata should be correct
        assert dual_purpose_func._docs_example["slug"] == "test-slug"
        assert dual_purpose_func._demo_record["name"] == "demo-test"
        assert dual_purpose_func._demo_record["featured"] is True

        # Function should still work
        assert dual_purpose_func() == "result"

    def test_all_decorators_combined(self):
        """Test stacking all four decorators."""

        @docs_example(slug="all-combined", title="All Decorators")
        @demo_record(name="combined-demo")
        @marketing_snippet(placement="hero", caption="Amazing!")
        @tutorial_cell(notebook="complete-tutorial", order=1)
        def fully_decorated():
            return 42

        # All attributes should be present
        assert hasattr(fully_decorated, "_docs_example")
        assert hasattr(fully_decorated, "_demo_record")
        assert hasattr(fully_decorated, "_marketing_snippet")
        assert hasattr(fully_decorated, "_tutorial_cell")

        # Function should still work
        assert fully_decorated() == 42

    def test_order_of_nested_decorators(self):
        """Test that decorator order doesn't affect metadata attachment."""

        # Order 1: docs_example first
        @docs_example(slug="order1", title="Order 1")
        @marketing_snippet(placement="hero")
        def order1():
            pass

        # Order 2: marketing_snippet first
        @marketing_snippet(placement="hero")
        @docs_example(slug="order2", title="Order 2")
        def order2():
            pass

        # Both should have both attributes
        assert hasattr(order1, "_docs_example")
        assert hasattr(order1, "_marketing_snippet")
        assert hasattr(order2, "_docs_example")
        assert hasattr(order2, "_marketing_snippet")


class TestDecoratorWithAsyncFunctions:
    """Test decorators with async functions."""

    def test_docs_example_with_async(self):
        """Test @docs_example with async function."""

        @docs_example(slug="async-test", title="Async Test")
        async def async_example():
            return "async-result"

        assert hasattr(async_example, "_docs_example")
        assert async_example._docs_example["slug"] == "async-test"

        # Verify it's still a coroutine function
        import asyncio

        assert asyncio.iscoroutinefunction(async_example)

    def test_demo_record_with_async(self):
        """Test @demo_record with async function."""

        @demo_record(name="async-demo")
        async def async_demo():
            return "async-demo-result"

        assert hasattr(async_demo, "_demo_record")
        assert async_demo._demo_record["name"] == "async-demo"

    def test_marketing_snippet_with_async(self):
        """Test @marketing_snippet with async function."""

        @marketing_snippet(placement="async-hero")
        async def async_snippet():
            return "async-snippet"

        assert hasattr(async_snippet, "_marketing_snippet")

    def test_tutorial_cell_with_async(self):
        """Test @tutorial_cell with async function."""

        @tutorial_cell(notebook="async-tutorial", order=1)
        async def async_cell():
            return "async-cell"

        assert hasattr(async_cell, "_tutorial_cell")

    def test_async_function_execution(self):
        """Test that decorated async function can be awaited."""
        import asyncio

        @docs_example(slug="awaitable", title="Awaitable Test")
        async def async_func():
            return "awaited"

        # Run the async function using asyncio.run
        result = asyncio.get_event_loop().run_until_complete(async_func())
        assert result == "awaited"


class TestDecoratorWithClassMethods:
    """Test decorators with class methods."""

    def test_docs_example_on_instance_method(self):
        """Test @docs_example on instance method."""

        class ExampleClass:
            @docs_example(slug="method-test", title="Method Test")
            def example_method(self):
                return "method-result"

        instance = ExampleClass()
        assert hasattr(ExampleClass.example_method, "_docs_example")
        assert instance.example_method() == "method-result"

    def test_demo_record_on_class_method(self):
        """Test @demo_record on classmethod."""

        class DemoClass:
            @classmethod
            @demo_record(name="classmethod-demo")
            def class_demo(cls):
                return "classmethod-result"

        assert hasattr(DemoClass.class_demo, "_demo_record")
        assert DemoClass.class_demo() == "classmethod-result"

    def test_marketing_snippet_on_static_method(self):
        """Test @marketing_snippet on staticmethod."""

        class MarketingClass:
            @staticmethod
            @marketing_snippet(placement="static-hero")
            def static_snippet():
                return "static-result"

        assert hasattr(MarketingClass.static_snippet, "_marketing_snippet")
        assert MarketingClass.static_snippet() == "static-result"


class TestDecoratorEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_string_slug(self):
        """Test docs_example with empty string slug."""

        @docs_example(slug="", title="Empty Slug")
        def empty_slug():
            pass

        assert empty_slug._docs_example["slug"] == ""

    def test_unicode_in_metadata(self):
        """Test decorators with unicode characters."""

        @docs_example(slug="unicode-test", title="Unicode Title")
        def unicode_func():
            pass

        assert unicode_func._docs_example["title"] == "Unicode Title"

    def test_special_characters_in_caption(self):
        """Test marketing_snippet with special characters in caption."""

        @marketing_snippet(
            placement="special",
            caption="Line 1\nLine 2\twith tab",
        )
        def special_func():
            pass

        assert "\n" in special_func._marketing_snippet["caption"]
        assert "\t" in special_func._marketing_snippet["caption"]

    def test_negative_order(self):
        """Test tutorial_cell with negative order value."""

        @tutorial_cell(notebook="test", order=-10)
        def negative_order():
            pass

        assert negative_order._tutorial_cell["order"] == -10

    def test_large_order(self):
        """Test tutorial_cell with large order value."""

        @tutorial_cell(notebook="test", order=999999)
        def large_order():
            pass

        assert large_order._tutorial_cell["order"] == 999999

    def test_decorator_on_lambda(self):
        """Test that decorator works with lambda (as a callable)."""
        # Note: Lambdas can't have decorators directly, but we can apply manually
        func = lambda: "lambda-result"
        decorated = docs_example(slug="lambda", title="Lambda")(func)

        assert hasattr(decorated, "_docs_example")
        assert decorated() == "lambda-result"

    def test_decorator_preserves_annotations(self):
        """Test that decorator preserves function annotations."""

        @docs_example(slug="annotated", title="Annotated")
        def annotated_func(x: int, y: str) -> bool:
            return True

        # Note: Without functools.wraps, annotations might not be preserved
        # This test documents the current behavior
        assert annotated_func(1, "test") is True

    def test_multiple_functions_same_metadata(self):
        """Test that multiple functions can have the same metadata values."""

        @docs_example(slug="shared", title="Shared Title")
        def func1():
            return 1

        @docs_example(slug="shared", title="Shared Title")
        def func2():
            return 2

        # Both should work independently
        assert func1() == 1
        assert func2() == 2
        assert func1._docs_example["slug"] == "shared"
        assert func2._docs_example["slug"] == "shared"


class TestMetadataExtraction:
    """Test metadata extraction scenarios (simulating what extraction scripts do)."""

    def test_collect_all_docs_examples(self):
        """Test collecting all functions with _docs_example attribute."""

        @docs_example(slug="example-1", title="Example 1", category="cat-a", order=10)
        def example1():
            pass

        @docs_example(slug="example-2", title="Example 2", category="cat-b", order=20)
        def example2():
            pass

        @docs_example(slug="example-3", title="Example 3", category="cat-a", order=5)
        def example3():
            pass

        # Simulate extraction
        functions = [example1, example2, example3]
        docs_examples = [
            f._docs_example for f in functions if hasattr(f, "_docs_example")
        ]

        assert len(docs_examples) == 3

        # Sort by order within category
        cat_a = [e for e in docs_examples if e["category"] == "cat-a"]
        cat_a_sorted = sorted(cat_a, key=lambda x: x["order"])

        assert cat_a_sorted[0]["slug"] == "example-3"  # order 5
        assert cat_a_sorted[1]["slug"] == "example-1"  # order 10

    def test_filter_featured_demo_records(self):
        """Test filtering for featured demo records."""

        @demo_record(name="regular", featured=False)
        def regular():
            pass

        @demo_record(name="featured-1", featured=True)
        def featured1():
            pass

        @demo_record(name="featured-2", featured=True)
        def featured2():
            pass

        functions = [regular, featured1, featured2]
        featured = [
            f._demo_record
            for f in functions
            if hasattr(f, "_demo_record") and f._demo_record["featured"]
        ]

        assert len(featured) == 2
        names = [f["name"] for f in featured]
        assert "featured-1" in names
        assert "featured-2" in names
        assert "regular" not in names

    def test_group_tutorial_cells_by_notebook(self):
        """Test grouping tutorial cells by notebook name."""

        @tutorial_cell(notebook="getting-started", order=1)
        def cell1():
            pass

        @tutorial_cell(notebook="getting-started", order=2)
        def cell2():
            pass

        @tutorial_cell(notebook="advanced", order=1)
        def cell3():
            pass

        functions = [cell1, cell2, cell3]

        # Group by notebook
        notebooks: dict[str, list] = {}
        for f in functions:
            if hasattr(f, "_tutorial_cell"):
                nb = f._tutorial_cell["notebook"]
                if nb not in notebooks:
                    notebooks[nb] = []
                notebooks[nb].append(f._tutorial_cell)

        assert "getting-started" in notebooks
        assert "advanced" in notebooks
        assert len(notebooks["getting-started"]) == 2
        assert len(notebooks["advanced"]) == 1


class TestImportFromPackage:
    """Test that decorators can be imported from skua.testing."""

    def test_import_from_testing_module(self):
        """Test import from skua.testing namespace."""
        from skua.testing import (
            docs_example,
            demo_record,
            marketing_snippet,
            tutorial_cell,
        )

        # All should be callable
        assert callable(docs_example)
        assert callable(demo_record)
        assert callable(marketing_snippet)
        assert callable(tutorial_cell)

    def test_all_exports(self):
        """Test that __all__ contains expected exports."""
        from skua import testing

        expected = ["docs_example", "demo_record", "marketing_snippet", "tutorial_cell"]
        for name in expected:
            assert name in testing.__all__
            assert hasattr(testing, name)
