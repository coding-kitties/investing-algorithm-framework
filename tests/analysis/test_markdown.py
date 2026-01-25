import unittest
from dataclasses import dataclass

from investing_algorithm_framework.analysis.markdown import (
    create_markdown_table
)


class TestCreateMarkdownTable(unittest.TestCase):
    """Tests for the create_markdown_table function."""

    def test_empty_list_returns_no_data_message(self):
        """Test that an empty list returns a 'No Data' message."""
        result = create_markdown_table([])
        self.assertIn("No Data Available", result)
        self.assertIn("No records found", result)

    def test_none_returns_no_data_message(self):
        """Test that None-like empty data returns a 'No Data' message."""
        result = create_markdown_table([])
        self.assertIn("No Data Available", result)

    def test_single_dict_row(self):
        """Test table creation with a single dictionary row."""
        data = [{"name": "Alice", "age": 30}]
        result = create_markdown_table(data)

        # Check header
        self.assertIn("Name", result)
        self.assertIn("Age", result)

        # Check data
        self.assertIn("Alice", result)
        self.assertIn("30", result)

        # Check structure (3 lines: header, separator, data)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_multiple_dict_rows(self):
        """Test table creation with multiple dictionary rows."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
            {"name": "Charlie", "age": 35}
        ]
        result = create_markdown_table(data)

        # Check all names present
        self.assertIn("Alice", result)
        self.assertIn("Bob", result)
        self.assertIn("Charlie", result)

        # Check structure (5 lines: header, separator, 3 data rows)
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 5)

    def test_float_formatting(self):
        """Test that floats are formatted with 2 decimal places."""
        data = [{"value": 3.14159}]
        result = create_markdown_table(data)
        self.assertIn("3.14", result)
        self.assertNotIn("3.14159", result)

    def test_none_value_shows_na(self):
        """Test that None values are displayed as 'N/A'."""
        data = [{"name": "Alice", "score": None}]
        result = create_markdown_table(data)
        self.assertIn("N/A", result)

    def test_header_titles_formatted(self):
        """Test that header titles have underscores replaced and are titled."""
        data = [{"first_name": "Alice", "last_name": "Smith"}]
        result = create_markdown_table(data)
        self.assertIn("First Name", result)
        self.assertIn("Last Name", result)

    def test_column_widths_accommodate_long_values(self):
        """Test that columns are wide enough for long values."""
        data = [
            {"name": "A", "description": "Short"},
            {"name": "B", "description": "This is a very long description"}
        ]
        result = create_markdown_table(data)

        # The column width should accommodate the longest value
        lines = result.strip().split("\n")

        # All lines should have the same structure
        for line in lines:
            self.assertTrue(line.startswith("|"))
            self.assertTrue(line.endswith("|"))

    def test_column_widths_accommodate_long_headers(self):
        """Test that columns are wide enough for long headers."""
        data = [{"very_long_column_name": "x"}]
        result = create_markdown_table(data)

        # Header should be fully visible
        self.assertIn("Very Long Column Name", result)

    def test_separator_line_matches_column_widths(self):
        """Test that separator line has correct dashes for each column."""
        data = [{"name": "Alice", "age": 30}]
        result = create_markdown_table(data)

        lines = result.strip().split("\n")
        separator = lines[1]

        # Separator should only contain |, -, and spaces
        for char in separator:
            self.assertIn(char, "|- ")

    def test_integer_values(self):
        """Test that integer values are converted to strings."""
        data = [{"count": 42, "total": 100}]
        result = create_markdown_table(data)
        self.assertIn("42", result)
        self.assertIn("100", result)

    def test_boolean_values(self):
        """Test that boolean values are converted to strings."""
        data = [{"active": True, "deleted": False}]
        result = create_markdown_table(data)
        self.assertIn("True", result)
        self.assertIn("False", result)

    def test_string_values(self):
        """Test that string values are preserved."""
        data = [{"message": "Hello, World!"}]
        result = create_markdown_table(data)
        self.assertIn("Hello, World!", result)

    def test_mixed_types(self):
        """Test table with various data types."""
        data = [{
            "name": "Test",
            "count": 5,
            "ratio": 0.75,
            "active": True,
            "notes": None
        }]
        result = create_markdown_table(data)

        self.assertIn("Test", result)
        self.assertIn("5", result)
        self.assertIn("0.75", result)
        self.assertIn("True", result)
        self.assertIn("N/A", result)

    def test_with_dataclass_objects(self):
        """Test table creation with dataclass objects."""
        @dataclass
        class Person:
            name: str
            age: int

        data = [Person(name="Alice", age=30), Person(name="Bob", age=25)]
        result = create_markdown_table(data)

        self.assertIn("Alice", result)
        self.assertIn("Bob", result)
        self.assertIn("30", result)
        self.assertIn("25", result)

    def test_with_regular_objects(self):
        """Test table creation with regular class objects."""
        class Item:
            def __init__(self, id, value):
                self.id = id
                self.value = value

        data = [Item(1, "first"), Item(2, "second")]
        result = create_markdown_table(data)

        self.assertIn("1", result)
        self.assertIn("2", result)
        self.assertIn("first", result)
        self.assertIn("second", result)

    def test_evenly_spaced_columns(self):
        """Test that all rows have consistently spaced columns."""
        data = [
            {"short": "a", "medium": "hello", "long": "this is longer"},
            {"short": "bb", "medium": "hi", "long": "short"}
        ]
        result = create_markdown_table(data)
        lines = result.strip().split("\n")

        # Extract column positions from separator line
        separator = lines[1]
        pipe_positions = [i for i, c in enumerate(separator) if c == '|']

        # All lines should have pipes at the same positions
        for line in lines:
            line_pipes = [i for i, c in enumerate(line) if c == '|']
            self.assertEqual(pipe_positions, line_pipes)

    def test_empty_string_values(self):
        """Test that empty strings are handled correctly."""
        data = [{"name": "", "value": "test"}]
        result = create_markdown_table(data)

        # Should still create a valid table
        lines = result.strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_numeric_string_values(self):
        """Test that numeric strings are preserved as strings."""
        data = [{"code": "12345", "zip": "01onal"}]
        result = create_markdown_table(data)
        self.assertIn("12345", result)


if __name__ == "__main__":
    unittest.main()

