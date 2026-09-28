// Participation Type Validation Test Suite (JavaScript)
// Created by Claude AI on 2026-09-11

/**
 * Regression tests for isParticipationTypeSelected() in
 * static/js/validation.js, used by static/js/registration.js's
 * client-side validateForm().
 *
 * Bug: for circles where templates/index.html's `is_cbc` is false, the
 * participation-type radio buttons are replaced by a single hidden input
 * carrying a fixed "regular" value (no choice to make). The old check -
 * `Array.from(radios).some(radio => radio.checked)` - tested `.checked` on
 * every `input[name="participation_type"]`, including that hidden one.
 * `.checked` on a hidden input is always undefined, so the check always
 * failed and the form refused to submit with "Please select how you would
 * like to participate", even though the section asking for that choice was
 * never shown.
 */

// Import from symlink so Jest coverage tracking works
const { isParticipationTypeSelected } = require('./validation.js');

describe('Participation Type Validation (JavaScript)', () => {

    describe('Non-CBC circles (hidden input, no choice offered)', () => {
        test('a hidden input with a fixed value counts as selected', () => {
            const inputs = [{ type: 'hidden', value: 'regular' }];
            expect(isParticipationTypeSelected(inputs)).toBe(true);
        });

        test('a hidden input with an empty value does not count as selected', () => {
            const inputs = [{ type: 'hidden', value: '' }];
            expect(isParticipationTypeSelected(inputs)).toBe(false);
        });
    });

    describe('CBC circles (radio buttons, a choice is required)', () => {
        test('no radio checked is not selected', () => {
            const inputs = [
                { type: 'radio', value: 'regular', checked: false },
                { type: 'radio', value: 'FEEDER', checked: false },
            ];
            expect(isParticipationTypeSelected(inputs)).toBe(false);
        });

        test('the "regular" radio checked counts as selected', () => {
            const inputs = [
                { type: 'radio', value: 'regular', checked: true },
                { type: 'radio', value: 'FEEDER', checked: false },
            ];
            expect(isParticipationTypeSelected(inputs)).toBe(true);
        });

        test('the "FEEDER" radio checked counts as selected', () => {
            const inputs = [
                { type: 'radio', value: 'regular', checked: false },
                { type: 'radio', value: 'FEEDER', checked: true },
            ];
            expect(isParticipationTypeSelected(inputs)).toBe(true);
        });
    });

    describe('Edge cases', () => {
        test('no matching inputs at all is not selected', () => {
            expect(isParticipationTypeSelected([])).toBe(false);
        });
    });
});
