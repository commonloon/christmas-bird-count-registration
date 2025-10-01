// Email Validation Test Suite (JavaScript)
// Created by Claude AI on 2025-09-30

/**
 * Comprehensive email validation tests for the Christmas Bird Count system.
 * Tests the centralized email validation logic in static/js/validation.js.
 *
 * This test suite mirrors the Python backend tests and can be run independently.
 * Focus: Verify RFC 5322 compliance and consistency with Python validation.
 */

const { validateEmailFormat } = require('../static/js/validation.js');

describe('Email Validation Frontend (JavaScript)', () => {

    describe('Valid emails should be accepted', () => {
        const validEmails = [
            // Standard formats
            'user@example.com',
            'user.name@example.com',
            'user_name@example.com',
            'user-name@example.com',

            // Plus sign support (PRIMARY TEST - RFC 5322 compliance)
            'user+tag@example.com',
            'harvey.dueck+rabbit@gmail.com',
            'test+multiple+plus@example.com',

            // Complex valid patterns
            'first.last+tag@sub.domain.com',
            'a.b.c@example.co.uk',
            'test_user-name+tag@mail.example.com',

            // Numeric patterns
            '123@example.com',
            'user123@example.com',
            '123user@example.com',

            // Short patterns
            'a@example.com',
            'a@b.co',

            // Case sensitivity (should be lowercased by sanitization but validation should accept)
            'User@Example.Com',
            'USER+TAG@EXAMPLE.COM',
        ];

        test.each(validEmails)('should accept %s', (email) => {
            expect(validateEmailFormat(email)).toBe(true);
        });
    });

    describe('Invalid emails should be rejected', () => {
        const invalidEmails = [
            // Consecutive dots
            ['test..test@example.com', 'consecutive_dots_in_local'],
            ['test@example..com', 'consecutive_dots_in_domain'],

            // Leading/trailing dots
            ['.test@example.com', 'leading_dot_in_local'],
            ['test.@example.com', 'trailing_dot_in_local'],
            ['test@.example.com', 'leading_dot_in_domain'],
            ['test@example.com.', 'trailing_dot_in_domain'],

            // Missing parts
            ['test@', 'missing_domain'],
            ['@example.com', 'missing_local'],
            ['test', 'missing_at_sign'],
            ['test@example', 'missing_tld'],

            // Spaces
            ['test @example.com', 'space_in_local'],
            ['test@exam ple.com', 'space_in_domain'],
            [' test@example.com', 'leading_space'],
            ['test@example.com ', 'trailing_space'],

            // Multiple @ signs
            ['test@@example.com', 'double_at_sign'],
            ['test@test@example.com', 'multiple_at_signs'],

            // Invalid characters
            ['test!user@example.com', 'exclamation_in_local_security_risk'],
            ['test%user@example.com', 'percent_in_local_security_risk'],
            ['test#user@example.com', 'hash_in_local'],
            ['test$user@example.com', 'dollar_in_local'],
            ['test&user@example.com', 'ampersand_in_local'],
            ['test*user@example.com', 'asterisk_in_local'],

            // Hyphens at domain boundaries
            ['test@-example.com', 'leading_hyphen_in_domain'],

            // Empty string
            ['', 'empty_string'],
        ];

        test.each(invalidEmails)('should reject %s (%s)', (email, reason) => {
            expect(validateEmailFormat(email)).toBe(false);
        });
    });

    describe('Email local part length limits', () => {
        test('should accept 64-character local part', () => {
            const valid64 = 'a'.repeat(64) + '@example.com';
            expect(validateEmailFormat(valid64)).toBe(true);
        });

        test('should reject 65-character local part', () => {
            const invalid65 = 'a'.repeat(65) + '@example.com';
            expect(validateEmailFormat(invalid65)).toBe(false);
        });
    });

    describe('Email domain length limits', () => {
        test('should accept long domain within 255 char limit', () => {
            // Create a realistic multi-label domain close to 255 chars
            const longSubdomain = 'b'.repeat(240);
            const validLongDomain = `a@${longSubdomain}.example.com`;
            const domainPart = `${longSubdomain}.example.com`;

            expect(domainPart.length).toBeLessThan(255);
            expect(validateEmailFormat(validLongDomain)).toBe(true);
        });

        test('should reject domain exceeding 255 chars', () => {
            // Create a domain that exceeds 255 characters
            const veryLongSubdomain = 'b'.repeat(256);
            const invalidLongDomain = `a@${veryLongSubdomain}.example.com`;
            const domainPart = `${veryLongSubdomain}.example.com`;

            expect(domainPart.length).toBeGreaterThan(255);
            expect(validateEmailFormat(invalidLongDomain)).toBe(false);
        });
    });

    describe('Email total length limits', () => {
        test('should accept 254-character email (RFC 5321 maximum)', () => {
            // Format: [60 chars]@[189 chars].com = 254 total
            const valid254 = 'a'.repeat(60) + '@' + 'b'.repeat(189) + '.com';
            expect(valid254.length).toBe(254);
            expect(validateEmailFormat(valid254)).toBe(true);
        });

        test('should reject 255-character email', () => {
            // Format: [61 chars]@[189 chars].com = 255 total
            const invalid255 = 'a'.repeat(61) + '@' + 'b'.repeat(189) + '.com';
            expect(invalid255.length).toBe(255);
            expect(validateEmailFormat(invalid255)).toBe(false);
        });
    });

    describe('Plus sign in various positions', () => {
        test('should accept plus sign at start of local part', () => {
            expect(validateEmailFormat('+user@example.com')).toBe(true);
        });

        test('should accept plus sign at end of local part', () => {
            expect(validateEmailFormat('user+@example.com')).toBe(true);
        });

        test('should accept multiple plus signs', () => {
            expect(validateEmailFormat('user+tag+extra@example.com')).toBe(true);
        });

        test('should accept plus sign with dots', () => {
            expect(validateEmailFormat('user.name+tag@example.com')).toBe(true);
        });

        test('should accept plus sign alone', () => {
            expect(validateEmailFormat('+@example.com')).toBe(true);
        });
    });

    describe('TLD requirements', () => {
        test('should accept 2-character TLD', () => {
            expect(validateEmailFormat('user@example.co')).toBe(true);
        });

        test('should accept 3-character TLD', () => {
            expect(validateEmailFormat('user@example.com')).toBe(true);
        });

        test('should accept long TLD', () => {
            expect(validateEmailFormat('user@example.museum')).toBe(true);
        });

        test('should reject 1-character TLD', () => {
            expect(validateEmailFormat('user@example.c')).toBe(false);
        });

        test('should reject email without TLD', () => {
            expect(validateEmailFormat('user@example')).toBe(false);
        });
    });

    describe('Subdomain support', () => {
        test('should accept single subdomain', () => {
            expect(validateEmailFormat('user@mail.example.com')).toBe(true);
        });

        test('should accept multiple subdomains', () => {
            expect(validateEmailFormat('user@mail.sub.example.com')).toBe(true);
        });

        test('should accept many subdomain levels', () => {
            expect(validateEmailFormat('user@a.b.c.d.example.com')).toBe(true);
        });
    });

    describe('Edge cases', () => {
        test('should accept single character local and domain', () => {
            expect(validateEmailFormat('a@b.co')).toBe(true);
        });

        test('should accept all numbers', () => {
            expect(validateEmailFormat('123@456.com')).toBe(true);
        });

        test('should accept mixed valid characters (no percent or exclamation)', () => {
            expect(validateEmailFormat('user._-+@example.com')).toBe(true);
        });

        test('should accept dot before plus', () => {
            expect(validateEmailFormat('user.name+tag@example.com')).toBe(true);
        });

        test('should accept underscore with plus', () => {
            expect(validateEmailFormat('user_name+tag@example.com')).toBe(true);
        });
    });

    describe('Security restrictions', () => {
        describe('Percent signs rejected (obsolete, potential encoding attacks)', () => {
            test('should reject percent in local part', () => {
                expect(validateEmailFormat('user%name@example.com')).toBe(false);
            });

            test('should reject percent encoding', () => {
                expect(validateEmailFormat('user%40domain@example.com')).toBe(false);
            });

            test('should reject percent anywhere in email', () => {
                expect(validateEmailFormat('test%test@example.com')).toBe(false);
            });
        });

        describe('Exclamation marks rejected (bang paths, obsolete UUCP routing)', () => {
            test('should reject exclamation in local part', () => {
                expect(validateEmailFormat('user!name@example.com')).toBe(false);
            });

            test('should reject bang path notation', () => {
                expect(validateEmailFormat('site!user@example.com')).toBe(false);
            });

            test('should reject multiple bangs', () => {
                expect(validateEmailFormat('host!host!user@example.com')).toBe(false);
            });
        });
    });

    describe('Real-world email patterns', () => {
        describe('Gmail with plus addressing', () => {
            test('should accept Gmail plus tag', () => {
                expect(validateEmailFormat('user+receipts@gmail.com')).toBe(true);
            });

            test('should accept Gmail with dots and plus', () => {
                expect(validateEmailFormat('first.last+work@gmail.com')).toBe(true);
            });
        });

        describe('Outlook/Hotmail', () => {
            test('should accept Outlook email', () => {
                expect(validateEmailFormat('user@outlook.com')).toBe(true);
            });

            test('should accept Hotmail with plus tag', () => {
                expect(validateEmailFormat('user+tag@hotmail.com')).toBe(true);
            });
        });

        describe('Yahoo', () => {
            test('should accept Yahoo email', () => {
                expect(validateEmailFormat('user@yahoo.com')).toBe(true);
            });
        });

        describe('Corporate domains', () => {
            test('should accept UK corporate domain', () => {
                expect(validateEmailFormat('employee.name@company.co.uk')).toBe(true);
            });

            test('should accept corporate email with plus', () => {
                expect(validateEmailFormat('employee+dept@company.com')).toBe(true);
            });
        });

        describe('Educational', () => {
            test('should accept .edu domain', () => {
                expect(validateEmailFormat('student@university.edu')).toBe(true);
            });

            test('should accept .edu with plus', () => {
                expect(validateEmailFormat('student+course@university.edu')).toBe(true);
            });
        });
    });

    describe('User-reported case', () => {
        test('should accept harvey.dueck+rabbit@gmail.com', () => {
            // This is the email that was being incorrectly rejected
            expect(validateEmailFormat('harvey.dueck+rabbit@gmail.com')).toBe(true);
        });
    });
});
