# Email Validation Test Suite
# Created by Claude AI on 2025-09-30

"""
Comprehensive email validation tests for the Christmas Bird Count system.
Tests the centralized email validation logic in services/security.py.

This test suite is separate from the main regression tests and can be run independently.
Focus: Verify RFC 5322 compliance, especially plus sign (+) support.
"""

import pytest
import sys
import os

# Add project root to path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from services.security import validate_email_format


class TestEmailValidationBackend:
    """Unit tests for Python email validation (services/security.py::validate_email_format)"""

    @pytest.mark.parametrize("valid_email", [
        # Standard formats
        "user@example.com",
        "user.name@example.com",
        "user_name@example.com",
        "user-name@example.com",

        # Plus sign support (PRIMARY TEST - RFC 5322 compliance)
        "user+tag@example.com",
        "harvey.dueck+rabbit@gmail.com",
        "test+multiple+plus@example.com",

        # Complex valid patterns
        "first.last+tag@sub.domain.com",
        "a.b.c@example.co.uk",
        "test_user-name+tag@mail.example.com",

        # Numeric patterns
        "123@example.com",
        "user123@example.com",
        "123user@example.com",

        # Short patterns
        "a@example.com",
        "a@b.co",

        # Case sensitivity (should be lowercased by sanitization but validation should accept)
        "User@Example.Com",
        "USER+TAG@EXAMPLE.COM",
    ])
    def test_valid_emails_accepted(self, valid_email):
        """Test that RFC 5322 compliant emails are accepted."""
        assert validate_email_format(valid_email) == True, \
            f"Valid email '{valid_email}' was incorrectly rejected"

    @pytest.mark.parametrize("invalid_email,reason", [
        # Consecutive dots
        ("test..test@example.com", "consecutive_dots_in_local"),
        ("test@example..com", "consecutive_dots_in_domain"),

        # Leading/trailing dots
        (".test@example.com", "leading_dot_in_local"),
        ("test.@example.com", "trailing_dot_in_local"),
        ("test@.example.com", "leading_dot_in_domain"),
        ("test@example.com.", "trailing_dot_in_domain"),

        # Missing parts
        ("test@", "missing_domain"),
        ("@example.com", "missing_local"),
        ("test", "missing_at_sign"),
        ("test@example", "missing_tld"),

        # Spaces
        ("test @example.com", "space_in_local"),
        ("test@exam ple.com", "space_in_domain"),
        (" test@example.com", "leading_space"),
        ("test@example.com ", "trailing_space"),

        # Multiple @ signs
        ("test@@example.com", "double_at_sign"),
        ("test@test@example.com", "multiple_at_signs"),

        # Invalid characters
        ("test!user@example.com", "exclamation_in_local_security_risk"),
        ("test%user@example.com", "percent_in_local_security_risk"),
        ("test#user@example.com", "hash_in_local"),
        ("test$user@example.com", "dollar_in_local"),
        ("test&user@example.com", "ampersand_in_local"),
        ("test*user@example.com", "asterisk_in_local"),

        # Hyphens at domain boundaries
        ("test@-example.com", "leading_hyphen_in_domain"),
        # Note: "test@example-.com" is technically valid per RFC (hyphen before dot is allowed in label)

        # Empty string
        ("", "empty_string"),

        # None (if passed as string "None")
        # Note: None type should be handled before validation
    ])
    def test_invalid_emails_rejected(self, invalid_email, reason):
        """Test that invalid email patterns are correctly rejected."""
        assert validate_email_format(invalid_email) == False, \
            f"Invalid email '{invalid_email}' was incorrectly accepted (reason: {reason})"

    def test_email_local_part_length_limits(self):
        """Test email local part (before @) length limits."""
        # 64 characters is maximum for local part
        valid_local_64 = "a" * 64 + "@example.com"
        assert validate_email_format(valid_local_64) == True, \
            "64-character local part should be accepted"

        # 65 characters exceeds limit
        invalid_local_65 = "a" * 65 + "@example.com"
        assert validate_email_format(invalid_local_65) == False, \
            "65-character local part should be rejected"

    def test_email_domain_length_limits(self):
        """Test email domain (after @) length limits."""
        # 255 characters is maximum for domain part
        # Note: Single-label domains (without dots except before TLD) may fail pattern matching
        # Use a realistic multi-label domain that's close to 255 chars
        # Format: a@subdomain.example.com where subdomain is very long
        long_subdomain = "b" * 240  # Long subdomain
        valid_long_domain = f"a@{long_subdomain}.example.com"
        domain_part = f"{long_subdomain}.example.com"

        # Should be accepted (within 255 char limit)
        assert len(domain_part) < 255, f"Domain part is {len(domain_part)} chars"
        assert validate_email_format(valid_long_domain) == True, \
            f"Long domain ({len(domain_part)} chars) should be accepted"

        # Create a domain that exceeds 255 characters
        very_long_subdomain = "b" * 256  # Exceeds limit
        invalid_long_domain = f"a@{very_long_subdomain}.example.com"
        domain_part_invalid = f"{very_long_subdomain}.example.com"

        assert len(domain_part_invalid) > 255, f"Domain part should exceed 255, got {len(domain_part_invalid)}"
        assert validate_email_format(invalid_long_domain) == False, \
            f"Domain exceeding 255 chars ({len(domain_part_invalid)}) should be rejected"

    def test_email_total_length_limits(self):
        """Test total email length limits (RFC 5321 limit is 254 characters)."""
        # 254 characters total (maximum)
        # Format: [60 chars]@[189 chars].com = 254 total
        valid_254 = ("a" * 60) + "@" + ("b" * 189) + ".com"
        assert len(valid_254) == 254
        assert validate_email_format(valid_254) == True, \
            "254-character email should be accepted"

        # 255 characters exceeds limit
        invalid_255 = ("a" * 61) + "@" + ("b" * 189) + ".com"
        assert len(invalid_255) == 255
        assert validate_email_format(invalid_255) == False, \
            "255-character email should be rejected"

    def test_plus_sign_in_various_positions(self):
        """Test plus sign (+) placement throughout local part."""
        # Plus sign at start of local part
        assert validate_email_format("+user@example.com") == True

        # Plus sign at end of local part
        assert validate_email_format("user+@example.com") == True

        # Multiple plus signs
        assert validate_email_format("user+tag+extra@example.com") == True

        # Plus sign with dots
        assert validate_email_format("user.name+tag@example.com") == True

        # Plus sign alone
        assert validate_email_format("+@example.com") == True

    def test_tld_requirements(self):
        """Test TLD (top-level domain) requirements."""
        # Valid 2-character TLD
        assert validate_email_format("user@example.co") == True

        # Valid 3-character TLD
        assert validate_email_format("user@example.com") == True

        # Valid long TLD
        assert validate_email_format("user@example.museum") == True

        # Invalid 1-character TLD
        assert validate_email_format("user@example.c") == False

        # No TLD
        assert validate_email_format("user@example") == False

    def test_subdomain_support(self):
        """Test multi-level subdomain support."""
        assert validate_email_format("user@mail.example.com") == True
        assert validate_email_format("user@mail.sub.example.com") == True
        assert validate_email_format("user@a.b.c.d.example.com") == True

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Single character local and domain parts
        assert validate_email_format("a@b.co") == True

        # All numbers
        assert validate_email_format("123@456.com") == True

        # Mixed valid characters (no percent or exclamation for security)
        assert validate_email_format("user._-+@example.com") == True

        # Dot before plus
        assert validate_email_format("user.name+tag@example.com") == True

        # Underscore with plus
        assert validate_email_format("user_name+tag@example.com") == True

    def test_security_restrictions(self):
        """Test security-based rejection of obsolete characters."""
        # Percent signs rejected (obsolete, potential encoding attacks)
        assert validate_email_format("user%name@example.com") == False
        assert validate_email_format("user%40domain@example.com") == False
        assert validate_email_format("test%test@example.com") == False

        # Exclamation marks rejected (bang paths, obsolete UUCP routing)
        assert validate_email_format("user!name@example.com") == False
        assert validate_email_format("site!user@example.com") == False
        assert validate_email_format("host!host!user@example.com") == False

    def test_real_world_emails(self):
        """Test real-world email patterns from major providers."""
        # Gmail with plus addressing
        assert validate_email_format("user+receipts@gmail.com") == True
        assert validate_email_format("first.last+work@gmail.com") == True

        # Outlook/Hotmail
        assert validate_email_format("user@outlook.com") == True
        assert validate_email_format("user+tag@hotmail.com") == True

        # Yahoo
        assert validate_email_format("user@yahoo.com") == True

        # Corporate domains
        assert validate_email_format("employee.name@company.co.uk") == True
        assert validate_email_format("employee+dept@company.com") == True

        # Educational
        assert validate_email_format("student@university.edu") == True
        assert validate_email_format("student+course@university.edu") == True

    def test_user_reported_case(self):
        """Test the specific email that prompted this validation review."""
        # This is the email that was being incorrectly rejected
        assert validate_email_format("harvey.dueck+rabbit@gmail.com") == True, \
            "The user-reported email 'harvey.dueck+rabbit@gmail.com' should be accepted"
