"""
Tests for natural sorting of area codes.

Tests that area codes are sorted correctly for both:
- Vancouver-style letter codes (A, B, C, ... X)
- Nanaimo-style numeric codes (1, 2, 4A, 4B, 9A, 10, etc.)
"""
import pytest
from models.area_signup_type import natural_sort_key


class TestNaturalSortKey:
    """Test the natural_sort_key function for various area code formats."""

    def test_vancouver_letter_codes_alphabetical(self):
        """Vancouver letter codes (A-X) should sort alphabetically."""
        codes = ['X', 'A', 'M', 'B', 'Z', 'C']
        sorted_codes = sorted(codes, key=natural_sort_key)
        assert sorted_codes == ['A', 'B', 'C', 'M', 'X', 'Z']

    def test_nanaimo_numeric_codes(self):
        """Nanaimo numeric codes should sort numerically, not alphabetically."""
        codes = ['10', '2', '1', '20', '11', '3']
        sorted_codes = sorted(codes, key=natural_sort_key)
        # Should be 1, 2, 3, 10, 11, 20 (numeric order)
        # NOT 1, 10, 11, 2, 20, 3 (alphabetic/string order)
        assert sorted_codes == ['1', '2', '3', '10', '11', '20']

    def test_nanaimo_alphanumeric_codes(self):
        """Nanaimo alphanumeric codes (4A, 4B, 9A, etc.) should sort correctly."""
        codes = ['9C', '4A', '9A', '4B', '9B', '10']
        sorted_codes = sorted(codes, key=natural_sort_key)
        # Should group by number first, then by letter
        assert sorted_codes == ['4A', '4B', '9A', '9B', '9C', '10']

    def test_mixed_numeric_and_alphanumeric(self):
        """Mixed numeric and alphanumeric codes should sort correctly."""
        codes = ['15', '4A', '1', '9B', '10', '2', '4B', '9A']
        sorted_codes = sorted(codes, key=natural_sort_key)
        assert sorted_codes == ['1', '2', '4A', '4B', '9A', '9B', '10', '15']

    def test_full_nanaimo_area_list(self):
        """Test with actual Nanaimo area codes."""
        codes = ['1', '2', '3', '4A', '4B', '5', '6', '7', '8', '9A', '9B', '9C',
                 '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20']
        unsorted = ['10', '9A', '1', '4B', '15', '2', '9C', '4A', '20', '9B',
                    '3', '11', '5', '16', '6', '12', '7', '17', '8', '18', '13', '19', '14']
        sorted_codes = sorted(unsorted, key=natural_sort_key)
        assert sorted_codes == codes

    def test_full_vancouver_area_list(self):
        """Test with actual Vancouver area codes (A-X, no Y which is special)."""
        codes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L',
                 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X']
        unsorted = ['M', 'A', 'X', 'B', 'W', 'C', 'V', 'D', 'U', 'E', 'T', 'F',
                    'S', 'G', 'R', 'H', 'Q', 'I', 'P', 'J', 'O', 'K', 'N', 'L']
        sorted_codes = sorted(unsorted, key=natural_sort_key)
        assert sorted_codes == codes

    def test_case_insensitive(self):
        """Sorting should handle both uppercase and lowercase."""
        codes = ['a', 'B', 'c', 'D']
        sorted_codes = sorted(codes, key=natural_sort_key)
        # Should maintain original case but sort alphabetically
        assert sorted_codes == ['a', 'B', 'c', 'D']

    def test_empty_list(self):
        """Empty list should return empty list."""
        codes = []
        sorted_codes = sorted(codes, key=natural_sort_key)
        assert sorted_codes == []

    def test_single_element(self):
        """Single element list should return unchanged."""
        codes = ['A']
        sorted_codes = sorted(codes, key=natural_sort_key)
        assert sorted_codes == ['A']

    def test_already_sorted(self):
        """Already sorted list should remain sorted."""
        codes = ['1', '2', '3', '4', '5']
        sorted_codes = sorted(codes, key=natural_sort_key)
        assert sorted_codes == ['1', '2', '3', '4', '5']

    def test_reverse_sorted(self):
        """Reverse sorted list should be reversed."""
        codes = ['5', '4', '3', '2', '1']
        sorted_codes = sorted(codes, key=natural_sort_key)
        assert sorted_codes == ['1', '2', '3', '4', '5']

    def test_complex_alphanumeric(self):
        """Complex alphanumeric codes should sort correctly."""
        codes = ['100A', '10B', '10A', '2C', '2B', '2A', '1']
        sorted_codes = sorted(codes, key=natural_sort_key)
        assert sorted_codes == ['1', '2A', '2B', '2C', '10A', '10B', '100A']
