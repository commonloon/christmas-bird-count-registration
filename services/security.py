# Updated by Claude AI on 2025-09-13
"""
Security utilities for input sanitization and validation.
Provides functions to prevent XSS attacks and ensure data integrity.
"""

import html
import re
from typing import Optional, Any
import logging
from config.areas import get_all_areas

logger = logging.getLogger(__name__)

def sanitize_html(text: str) -> str:
    """
    Sanitize text input by escaping HTML entities to prevent XSS attacks.
    
    Args:
        text: Input text that may contain HTML
        
    Returns:
        HTML-escaped text safe for display
    """
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    
    # First strip whitespace
    text = text.strip()
    
    # Escape HTML entities
    escaped = html.escape(text, quote=True)
    
    return escaped

def sanitize_text_input(text: str, max_length: int = None, allow_newlines: bool = False) -> str:
    """
    Sanitize general text input with length limits and character restrictions.
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length (None for no limit)
        allow_newlines: Whether to allow newline characters
        
    Returns:
        Sanitized text
    """
    if not isinstance(text, str):
        return ""
    
    # Strip whitespace from start/end
    text = text.strip()
    
    # Remove null bytes and other control characters (except newlines if allowed)
    if allow_newlines:
        # Keep newlines but remove other control chars
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    else:
        # Remove all control characters including newlines
        text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    
    # Apply length limit if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
        logger.warning(f"Text input truncated to {max_length} characters")
    
    return text

def sanitize_name(name: str) -> str:
    """
    Sanitize name fields (first_name, last_name).
    
    Args:
        name: Name to sanitize
        
    Returns:
        Sanitized name (max 100 chars, alphanumeric + spaces, hyphens, apostrophes)
    """
    if not isinstance(name, str):
        return ""
    
    # Basic sanitization
    name = sanitize_text_input(name, max_length=100, allow_newlines=False)
    
    # Allow only letters, spaces, hyphens, apostrophes, and basic accented characters
    # This pattern allows for international names while blocking obvious script injection
    name = re.sub(r"[^a-zA-Z\s\-'àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]", "", name)
    
    # Remove multiple consecutive spaces
    name = re.sub(r'\s+', ' ', name)
    
    return name.strip()

def sanitize_phone(phone: str) -> str:
    """
    Sanitize phone number input.
    
    Args:
        phone: Phone number to sanitize
        
    Returns:
        Sanitized phone number (digits, spaces, hyphens, parentheses, plus sign only)
    """
    if not isinstance(phone, str):
        return ""
    
    # Basic sanitization
    phone = sanitize_text_input(phone, max_length=20, allow_newlines=False)
    
    # Allow only digits, spaces, hyphens, parentheses, and plus sign
    phone = re.sub(r'[^0-9\s\-\(\)\+]', '', phone)
    
    # Remove excessive spaces
    phone = re.sub(r'\s+', ' ', phone)
    
    return phone.strip()

def sanitize_email(email: str) -> str:
    """
    Sanitize email address input.

    Args:
        email: Email to sanitize

    Returns:
        Sanitized email (lowercase, trimmed, basic validation)

    Note:
        Removes percent signs (%) and exclamation marks (!) for security.
        These are obsolete email syntax that could be used for attacks.
    """
    if not isinstance(email, str):
        return ""

    # Basic sanitization
    email = sanitize_text_input(email, max_length=254, allow_newlines=False)

    # Convert to lowercase
    email = email.lower()

    # Remove any characters that could be used for injection
    # Keep only valid email characters (alphanumeric, @, dot, underscore, plus, hyphen)
    # Explicitly exclude: percent (%), exclamation (!) for security
    email = re.sub(r'[^a-z0-9@._+-]', '', email)

    return email


def validate_email_format(email: str) -> bool:
    """
    Email format validation with security restrictions.

    Centralized email validation function used across all routes.
    Validates:
    - Proper character set (alphanumeric, dots, underscores, plus, hyphens)
    - No consecutive dots in local part
    - No dots at start/end of local part
    - Proper domain format with TLD
    - Standard length limits (64 local, 255 domain, 254 total)
    - SECURITY: Rejects percent signs (obsolete, potential encoding attacks)
    - SECURITY: Rejects exclamation marks (bang paths, obsolete UUCP routing)

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid, False otherwise

    Examples:
        >>> validate_email_format('user@example.com')
        True
        >>> validate_email_format('user+tag@example.com')
        True
        >>> validate_email_format('user%name@example.com')
        False  # Percent signs rejected for security
        >>> validate_email_format('user!name@example.com')
        False  # Bang paths rejected for security
    """
    if not email or not isinstance(email, str) or len(email) > 254:
        return False

    # Security check: Reject percent signs (obsolete, potential encoding attacks)
    if '%' in email:
        return False

    # Security check: Reject exclamation marks (bang paths, obsolete UUCP routing)
    if '!' in email:
        return False

    # Check for consecutive dots
    if '..' in email:
        return False

    # Split on @ - must have exactly one @
    try:
        local, domain = email.rsplit('@', 1)
    except ValueError:
        return False

    # Local part validation (before @)
    if not local or len(local) > 64:
        return False

    # Local part cannot start or end with dot
    if local.startswith('.') or local.endswith('.'):
        return False

    # Local part pattern: alphanumeric, dots, underscores, plus, hyphens
    # Note: Percent and exclamation excluded for security (checked above)
    # Note: This pattern matches the JavaScript version in validation.js
    local_pattern = r'^[a-zA-Z0-9._+-]+$'
    if not re.match(local_pattern, local):
        return False

    # Domain part validation (after @)
    if not domain or len(domain) > 255:
        return False

    # Domain must have at least one dot and end with 2+ letter TLD
    domain_pattern = r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(domain_pattern, domain):
        return False

    # Domain cannot start or end with dot or hyphen
    if domain.startswith('.') or domain.endswith('.') or domain.startswith('-') or domain.endswith('-'):
        return False

    return True

def sanitize_notes(notes: str) -> str:
    """
    Sanitize notes/comments field with more lenient rules.
    
    Args:
        notes: Notes text to sanitize
        
    Returns:
        Sanitized notes (max 1000 chars, allows newlines)
    """
    if not isinstance(notes, str):
        return ""
    
    # Allow newlines in notes but limit length
    notes = sanitize_text_input(notes, max_length=1000, allow_newlines=True)
    
    return notes

def validate_area_code(area_code: str) -> bool:
    """
    Validate area code against configured areas.

    Args:
        area_code: Area code to validate

    Returns:
        True if valid area code (exists in AREA_CONFIG or is "UNASSIGNED")
    """
    if not isinstance(area_code, str):
        return False

    # Valid area codes are any configured area or UNASSIGNED
    valid_areas = get_all_areas()
    return area_code in valid_areas or area_code == "UNASSIGNED"

def validate_skill_level(skill_level: str) -> bool:
    """
    Validate skill level selection.
    
    Args:
        skill_level: Skill level to validate
        
    Returns:
        True if valid skill level
    """
    valid_levels = ['Newbie', 'Beginner', 'Intermediate', 'Expert']
    return skill_level in valid_levels

def validate_experience(experience: str) -> bool:
    """
    Validate CBC experience selection.

    Args:
        experience: Experience level to validate

    Returns:
        True if valid experience level
    """
    valid_experience = ['None', '1-2 counts', '3+ counts']
    return experience in valid_experience

def validate_participation_type(participation_type: str) -> bool:
    """
    Validate participation type selection.
    
    Args:
        participation_type: Participation type to validate
        
    Returns:
        True if valid participation type
    """
    valid_types = ['regular', 'FEEDER']
    return participation_type in valid_types

def is_suspicious_input(text: str) -> bool:
    """
    Check if input contains suspicious patterns that might indicate an attack.
    
    Args:
        text: Text to check
        
    Returns:
        True if input appears suspicious
    """
    if not isinstance(text, str):
        return False
    
    # Check for common script injection patterns
    suspicious_patterns = [
        r'<script[^>]*>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe[^>]*>',
        r'<object[^>]*>',
        r'<embed[^>]*>',
        r'eval\s*\(',
        r'document\.',
        r'window\.',
        r'alert\s*\(',
        r'confirm\s*\(',
        r'prompt\s*\(',
    ]
    
    text_lower = text.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            logger.warning(f"Suspicious input detected: {pattern}")
            return True
    
    return False

def log_security_event(event_type: str, details: str, user_email: str = None):
    """
    Log security-related events for monitoring.
    
    Args:
        event_type: Type of security event
        details: Details about the event
        user_email: Email of user involved (if applicable)
    """
    log_msg = f"SECURITY: {event_type} - {details}"
    if user_email:
        log_msg += f" - User: {user_email}"
    
    logger.warning(log_msg)