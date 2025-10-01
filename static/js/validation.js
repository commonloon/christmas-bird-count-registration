/* Updated by Claude AI on 2025-09-30 */
/**
 * Shared validation utilities for CBC Registration System
 *
 * This module provides centralized validation functions used across
 * all forms (public registration, admin participant edit, admin leader edit).
 *
 * IMPORTANT: Email validation regex must match the Python version in
 * services/security.py::validate_email_format() for consistency.
 */

/**
 * Email format validation with security restrictions.
 *
 * Validates:
 * - Proper character set (alphanumeric, dots, underscores, plus, hyphens)
 * - No consecutive dots in local part
 * - No dots at start/end of local part
 * - Proper domain format with TLD
 * - Standard length limits (64 local, 255 domain, 254 total)
 * - SECURITY: Rejects percent signs (obsolete, potential encoding attacks)
 * - SECURITY: Rejects exclamation marks (bang paths, obsolete UUCP routing)
 *
 * @param {string} email - Email address to validate
 * @returns {boolean} True if email format is valid, false otherwise
 *
 * @example
 * validateEmailFormat('user@example.com')  // returns true
 * validateEmailFormat('user+tag@example.com')  // returns true
 * validateEmailFormat('user%name@example.com')  // returns false (security)
 * validateEmailFormat('user!name@example.com')  // returns false (security)
 */
function validateEmailFormat(email) {
    if (!email || typeof email !== 'string' || email.length > 254) {
        return false;
    }

    // Security check: Reject percent signs (obsolete, potential encoding attacks)
    if (email.includes('%')) {
        return false;
    }

    // Security check: Reject exclamation marks (bang paths, obsolete UUCP routing)
    if (email.includes('!')) {
        return false;
    }

    // Check for consecutive dots
    if (email.includes('..')) {
        return false;
    }

    // Split on @ - must have exactly one @
    const parts = email.split('@');
    if (parts.length !== 2) {
        return false;
    }

    const [local, domain] = parts;

    // Local part validation (before @)
    if (!local || local.length > 64) {
        return false;
    }

    // Local part cannot start or end with dot
    if (local.startsWith('.') || local.endsWith('.')) {
        return false;
    }

    // Local part pattern: alphanumeric, dots, underscores, plus, hyphens
    // Note: Percent and exclamation excluded for security (checked above)
    // Note: This pattern matches the Python version in services/security.py
    const localPattern = /^[a-zA-Z0-9._+-]+$/;
    if (!localPattern.test(local)) {
        return false;
    }

    // Domain part validation (after @)
    if (!domain || domain.length > 255) {
        return false;
    }

    // Domain must have at least one dot and end with 2+ letter TLD
    const domainPattern = /^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
    if (!domainPattern.test(domain)) {
        return false;
    }

    // Domain cannot start or end with dot or hyphen
    if (domain.startsWith('.') || domain.endsWith('.') ||
        domain.startsWith('-') || domain.endsWith('-')) {
        return false;
    }

    return true;
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { validateEmailFormat };
}
