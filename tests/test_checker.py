"""
Unit tests for the checker module functions.

These functions are available as builtins in text question checker code.
"""

import pytest
from webquiz.checker import to_int, distance, direction_angle


class TestToInt:
    """Tests for the to_int function."""

    def test_simple_integer(self):
        """Test converting simple integer string."""
        assert to_int("42") == 42

    def test_integer_with_whitespace(self):
        """Test converting integer with leading/trailing whitespace."""
        assert to_int("  42  ") == 42
        assert to_int("\t42\n") == 42

    def test_negative_integer(self):
        """Test converting negative integer."""
        assert to_int("-10") == -10
        assert to_int("  -5  ") == -5

    def test_zero(self):
        """Test converting zero."""
        assert to_int("0") == 0
        assert to_int("  0  ") == 0

    def test_invalid_input_float(self):
        """Test that float string raises ValueError."""
        with pytest.raises(ValueError):
            to_int("3.14")

    def test_invalid_input_text(self):
        """Test that non-numeric string raises ValueError."""
        with pytest.raises(ValueError):
            to_int("abc")

    def test_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError):
            to_int("")

    def test_whitespace_only(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError):
            to_int("   ")


class TestDistance:
    """Tests for the distance function."""

    def test_plain_number(self):
        """Test plain number input."""
        assert distance("2000") == 2000

    def test_number_with_whitespace(self):
        """Test number with whitespace."""
        assert distance("  2000  ") == 2000

    def test_meters_latin(self):
        """Test meters with Latin 'm'."""
        assert distance("2000m") == 2000
        assert distance("500m") == 500

    def test_meters_cyrillic(self):
        """Test meters with Cyrillic 'м'."""
        assert distance("2000м") == 2000
        assert distance("500м") == 500

    def test_kilometers_latin(self):
        """Test kilometers with Latin 'km'."""
        assert distance("2km") == 2000
        assert distance("5km") == 5000

    def test_kilometers_cyrillic(self):
        """Test kilometers with Cyrillic 'км'."""
        assert distance("2км") == 2000
        assert distance("5км") == 5000

    def test_kilometers_float(self):
        """Test fractional kilometers."""
        assert distance("0.5km") == 500
        assert distance("1.5км") == 1500
        assert distance("2.5km") == 2500

    def test_trailing_dot(self):
        """Test input with trailing dot."""
        assert distance("2км.") == 2000
        assert distance("500м.") == 500

    def test_case_insensitive(self):
        """Test that input is case insensitive."""
        assert distance("2KM") == 2000
        assert distance("500M") == 500

    def test_float_meters(self):
        """Test float value in meters."""
        assert distance("1500.0m") == 1500
        assert distance("2500.5") == 2500

    def test_invalid_format(self):
        """Test invalid format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            distance("abc")
        assert "Неверный формат" in str(exc_info.value)

    def test_empty_string(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError):
            distance("")

    def test_mixed_invalid(self):
        """Test mixed invalid input."""
        with pytest.raises(ValueError):
            distance("10xyz")


class TestDirectionAngle:
    """Tests for the direction_angle function.

    The function converts direction angles in degrees format.
    Input "20" means 20 degrees = 2000 (20*100).
    Input "20-30" means 20 degrees 30 minutes = 2030.
    """

    def test_simple_angle(self):
        """Test simple angle number (degrees only)."""
        assert direction_angle("20") == 2000  # 20 degrees = 2000
        assert direction_angle("15") == 1500  # 15 degrees = 1500

    def test_angle_with_whitespace(self):
        """Test angle with whitespace."""
        assert direction_angle("  20  ") == 2000

    def test_dash_format_whole(self):
        """Test dash format with whole numbers (degrees-minutes)."""
        assert direction_angle("20-00") == 2000
        assert direction_angle("15-30") == 1530
        assert direction_angle("0-45") == 45

    def test_dash_format_with_whitespace(self):
        """Test dash format with whitespace around parts."""
        assert direction_angle("20 - 00") == 2000
        assert direction_angle(" 15 - 30 ") == 1530

    def test_single_digit_degrees(self):
        """Test single digit degrees."""
        assert direction_angle("5-00") == 500
        assert direction_angle("1-45") == 145

    def test_two_digit_minutes(self):
        """Test two digit minutes."""
        assert direction_angle("10-15") == 1015
        assert direction_angle("35-59") == 3559

    def test_zero_angle(self):
        """Test zero angle."""
        assert direction_angle("0") == 0
        assert direction_angle("0-00") == 0

    def test_too_many_dashes(self):
        """Test that too many dashes raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            direction_angle("20-30-40")
        assert "Неверный формат" in str(exc_info.value)

    def test_invalid_number(self):
        """Test invalid number raises ValueError."""
        with pytest.raises(ValueError):
            direction_angle("abc")

    def test_empty_string(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError):
            direction_angle("")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
