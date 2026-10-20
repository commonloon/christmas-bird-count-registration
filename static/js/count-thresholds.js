/* Updated by Claude AI on 2026-10-20 */
// Participation-count tiers for the area maps (public registration map and the admin
// unassigned page), plus a Leaflet legend that doubles as the control for trying other
// cut-offs. Mirrors services/count_thresholds.py: a tier is defined by the lowest count
// in it, so the ranges can't overlap - counts below `medium` are low, `medium` up to
// `high - 1` are medium, `high` and above are high.
//
// The circle's own values (set by a circle admin) are the starting point. A viewer's
// changes are remembered in this browser only (localStorage, per circle) and are
// dropped again when they match the circle's values, so a later change to the circle's
// defaults still reaches viewers who never customised anything.
const CountThresholds = (function () {
    const MAX_THRESHOLD = 999;

    function isValid(medium, high) {
        return Number.isInteger(medium) && Number.isInteger(high) &&
            medium >= 1 && medium < high && high <= MAX_THRESHOLD;
    }

    function storageKey(slug) {
        return 'cbc-count-thresholds:' + slug;
    }

    function loadStored(slug) {
        try {
            const parsed = JSON.parse(localStorage.getItem(storageKey(slug)));
            if (parsed && isValid(parsed.medium, parsed.high)) {
                return parsed;
            }
        } catch (e) { /* storage blocked or corrupt - fall back to the defaults */ }
        return null;
    }

    function saveStored(slug, values, defaults) {
        try {
            if (values.medium === defaults.medium && values.high === defaults.high) {
                localStorage.removeItem(storageKey(slug));
            } else {
                localStorage.setItem(storageKey(slug), JSON.stringify(values));
            }
        } catch (e) { /* storage unavailable - the change just won't persist */ }
    }

    function rangeText(from, to) {
        if (to === null) return from + '+';
        return from === to ? String(from) : from + '–' + to;
    }

    // defaults: {medium, high} - the circle's values. Returns the shared state object.
    function create(slug, defaults) {
        const circleDefaults = isValid(defaults.medium, defaults.high)
            ? { medium: defaults.medium, high: defaults.high }
            : { medium: 4, high: 8 };
        let current = loadStored(slug) || { ...circleDefaults };
        const listeners = [];

        const state = {
            tier(count) {
                if (count >= current.high) return 'high';
                if (count >= current.medium) return 'med';
                return 'low';
            },
            values() {
                return { ...current };
            },
            onChange(fn) {
                listeners.push(fn);
            },
            set(medium, high) {
                if (!isValid(medium, high)) return false;
                current = { medium: medium, high: high };
                saveStored(slug, current, circleDefaults);
                listeners.forEach(fn => fn(state));
                return true;
            },
            reset() {
                state.set(circleDefaults.medium, circleDefaults.high);
            },
            isCustom() {
                return current.medium !== circleDefaults.medium || current.high !== circleDefaults.high;
            },
            // options.extraRows: [{className, text}] appended below the three tiers
            // (e.g. the registration map's "Admin-assignment only" swatch).
            legendControl(options) {
                return buildLegend(state, options || {});
            },
            // The same key as a plain element for placing in the page (e.g. beside the
            // area buttons); stays in step with any legendControl on a map.
            legendElement(options) {
                const opts = options || {};
                const box = buildLegendBox(state, opts, true);
                box.classList.add('count-legend-inline');
                return box;
            }
        };
        return state;
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function swatchRow(tier) {
        const row = el('div', 'count-legend-row');
        row.appendChild(el('span', 'color-box ' + tier + '-count'));
        return row;
    }

    function numberInput(label) {
        const input = el('input', 'form-control form-control-sm count-legend-input');
        input.type = 'number';
        input.min = '1';
        input.max = String(MAX_THRESHOLD);
        input.step = '1';
        input.inputMode = 'numeric';
        input.setAttribute('aria-label', label);
        return input;
    }

    function buildLegend(state, options) {
        const Legend = L.Control.extend({
            options: { position: 'bottomright' },

            onAdd: function (map) {
                // Phones: start collapsed so the key doesn't cover the map
                const box = buildLegendBox(state, options, map.getSize().x >= 480);
                box.classList.add('leaflet-bar');
                L.DomEvent.disableClickPropagation(box);
                L.DomEvent.disableScrollPropagation(box);
                return box;
            }
        });
        return new Legend();
    }

    function buildLegendBox(state, options, startOpen) {
        const box = el('div', 'count-legend');

        const toggle = el('button', 'count-legend-toggle', 'Colour key');
        toggle.type = 'button';
        const body = el('div', 'count-legend-body');
        body.hidden = !startOpen;
        toggle.setAttribute('aria-expanded', String(startOpen));
        toggle.addEventListener('click', function () {
            body.hidden = !body.hidden;
            toggle.setAttribute('aria-expanded', String(!body.hidden));
        });

        const lowRow = swatchRow('low');
        const lowText = el('span');
        lowRow.appendChild(lowText);

        const medRow = swatchRow('med');
        const mediumInput = numberInput('Lowest count for the middle colour');
        const medText = el('span');
        medRow.appendChild(mediumInput);
        medRow.appendChild(medText);

        const highRow = swatchRow('high');
        const highInput = numberInput('Lowest count for the darkest colour');
        const highText = el('span', null, '+ registered');
        highRow.appendChild(highInput);
        highRow.appendChild(highText);

        const reset = el('button', 'btn btn-link btn-sm p-0 count-legend-reset', 'Reset to default');
        reset.type = 'button';
        reset.addEventListener('click', function () { state.reset(); });

        const hint = el('div', 'count-legend-hint', 'Edit the numbers to change the colour ranges.');

        body.appendChild(lowRow);
        body.appendChild(medRow);
        body.appendChild(highRow);
        (options.extraRows || []).forEach(function (extra) {
            const row = el('div', 'count-legend-row');
            row.appendChild(el('span', 'color-box ' + extra.className));
            row.appendChild(el('span', null, extra.text));
            body.appendChild(row);
        });
        body.appendChild(hint);
        body.appendChild(reset);
        box.appendChild(toggle);
        box.appendChild(body);

        function refresh() {
            const v = state.values();
            lowText.textContent = rangeText(0, v.medium - 1) + ' registered';
            medText.textContent = '–' + (v.high - 1) + ' registered';
            if (document.activeElement !== mediumInput) mediumInput.value = v.medium;
            if (document.activeElement !== highInput) highInput.value = v.high;
            mediumInput.classList.remove('is-invalid');
            highInput.classList.remove('is-invalid');
            reset.hidden = !state.isCustom();
        }

        // Apply only complete, valid pairs; flag the field otherwise and leave
        // the map as it was rather than recolouring on half-typed input.
        function apply() {
            const medium = parseInt(mediumInput.value, 10);
            const high = parseInt(highInput.value, 10);
            if (isValid(medium, high)) {
                state.set(medium, high);
            } else {
                mediumInput.classList.toggle('is-invalid', !(medium >= 1 && medium < MAX_THRESHOLD));
                highInput.classList.toggle('is-invalid', !(high > medium && high <= MAX_THRESHOLD));
            }
        }
        mediumInput.addEventListener('input', apply);
        highInput.addEventListener('input', apply);
        // Put a valid value back once the field is left with invalid text
        mediumInput.addEventListener('blur', refresh);
        highInput.addEventListener('blur', refresh);

        state.onChange(refresh);
        refresh();
        return box;
    }

    return { create: create, isValid: isValid };
})();
