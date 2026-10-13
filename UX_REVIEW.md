# UI/UX Review

Date: 2026-10-13

Scope: static read of `templates/` and `static/css/main.css`. Pages were not opened in a browser, so visual points should be confirmed against the live pages.

The inconsistent CSV export button is a symptom of a wider problem: there is no shared button, colour or layout convention, so each page makes its own choices.

Status key: **Done** = fixed, **Open** = not yet addressed.

## A. Real bugs

| # | Issue | Status |
|---|-------|--------|
| 1 | **Missing icons on the Leaders page.** `admin/leaders.html` used Font Awesome classes (`fas fa-users`, `fa-chart-bar`, `fa-download`) but only Bootstrap Icons is loaded, so they rendered as blank space. | Done |
| 2 | **Warning and info flash messages showed as green success.** `base.html` mapped only `error` to `alert-danger`; everything else became `alert-success`. | Done |
| 3 | **`.map-legend` / `.legend-item` defined twice, differently** (`main.css` and an inline `<style>` in `leaders.html`), so the Leaders legend differed from the registration legend and the inline rules could leak. | Done |
| 4 | **Hard-coded warning colours (`#fff3cd`, `#856404`, `#ffc107`) in the leader dashboard's Withdrawn section.** Emails keep their own inline colours by design (email clients ignore stylesheets). | Done |

## B. Inconsistency

5. **Export CSV is styled four different ways.**

   | Page | Style |
   |---|---|
   | Admin dashboard | `btn-primary`, no icon |
   | Participants | `btn-success`, no icon |
   | Leaders | `btn-success btn-sm`, icon (was broken, see A1) |
   | Leader dashboard | `btn-primary`, `bi-download`, label "Export Team CSV" |

   Recommendation: one pattern everywhere, `btn btn-outline-secondary` with `bi-download` and the label "Export CSV". It is a utility action and should not compete with primary actions.
6. **Quick Actions rows use colour inconsistently.** Dashboard: all six buttons are `btn-primary`, so nothing stands out. Participants: Unassigned is yellow, Leaders cyan, Export green, with no meaning, and "Manage Leaders" is a different colour on each page. Leaders: a `btn-group` of outline buttons, a third pattern for the same navigation. Recommendation: reserve primary for the one main action per page, outline-secondary for navigation, warning for attention items.
7. **Page headers are built differently on each page.** Title, year badge, email and Logout are arranged differently, with Logout styled `btn-sm btn-outline-secondary ms-2` on most pages and `btn-outline-secondary btn-sm` on Recent Registrations. Recommendation: put the user email and Logout in the navbar once, and use a shared `page_header` macro for title, year and actions.
8. **Year switching comes in three forms:** an auto-submitting `<select>` (dashboard, area detail, Recent Registrations), a tab strip (Participants, Leaders), and nothing on Super-Admin pages. Pick one control. The `<select>` also lacks a visible label on some pages.
9. **Breadcrumbs exist on some pages and not others.** Participants, Leaders and Unassigned have them; Super-Admin pages use ad hoc "Back to Circles" buttons; Login uses a grey `btn-secondary` "Back to Registration". Use breadcrumbs or one consistent back link.
10. **Badge colours mean different things on different pages.** `bg-info` is used for year, FEEDER and general status; `bg-warning` is used with and without `text-dark` (poor contrast without); skill level uses green/blue/cyan/grey, colliding with status meanings. Recommendation: a small semantic set (status = success/warning/danger, attributes = neutral secondary), and always pair `bg-warning` with `text-dark`.
11. **Table styles vary.** About 10 combinations of `table-striped`, `table-sm`, `table-hover`, `align-middle`, plus a custom `.participant-table`, and one table with `table-info`. Standardise on one or two.
12. **Button variants are scattered.** `btn-secondary` and `btn-outline-secondary` are mixed for Cancel/Back; `btn-info` and `btn-warning` are used as solid fills for non-status actions; Save/Edit differ between pages (`btn-success btn-save` vs `btn-primary`).
13. **Heading scale is not shared.** `index.html` overrides the `<h1>` size inline (1.75rem), Registration Success uses an `<h2>`, and the stat cards use `<h2 class="text-primary/success/warning/info">`; cyan `text-info` on white has poor contrast.

## C. Visual and theming

14. **`main.css` re-declares Bootstrap defaults and adds no brand.** `.btn-primary` sets `#0d6efd`, identical to Bootstrap's value. The result is the stock Bootstrap blue navbar. Recommendation: define CSS variables (`--brand-primary` etc.) and override `--bs-primary`; circles could theme from `circle_slug`.
15. **Colours are hard-coded** (`#28a745`, `#ffc107`, `#dc3545` are Bootstrap 4 values; the app uses Bootstrap 5.1.3). Use `var(--bs-success)` and the other variables.
16. **Map colours are not shared.** The registration map uses orange/maroon/navy for low/medium/high counts; the Leaders map uses red/green for needs-leader/has-leader. Each is fine alone, but there is no shared legend component.
17. **Inline styles and `<style>` blocks are widespread** (16 inline `style=` attributes in `participants.html` alone, 58 across non-email templates). Move to utility classes or `main.css`.
18. **Library versions are old.** Bootstrap 5.1.3 (current is 5.3.x, with colour modes and better variables) and Bootstrap Icons 1.10.0, loaded from third-party CDNs without SRI hashes. Consider self-hosting.

## D. Usability and accessibility

19. **Admin pages are crowded on mobile.** The Participants table has 8+ columns with inline-edit rows and relies on horizontal scrolling. Consider a card layout under 768px.
20. **Native `confirm()` / `alert()` is used in 23 places.** Replace with a Bootstrap modal so dialogs look consistent and the destructive action is labelled ("Delete participant", not "OK").
21. **Quick Actions buttons use `me-2` spacing**, which wraps badly on narrow screens. Use `d-flex flex-wrap gap-2`.
22. **Small touch targets.** `btn-sm` is used for primary row actions, and the mobile `.btn-lg` rule is the only touch optimisation.
23. **Accessibility gaps.** `.sr-only` is a Bootstrap 4 class (BS5 uses `visually-hidden`); many `<select>`/`<input>` controls lack a `<label>` or `aria-label`; `btn-close` has no `aria-label`; the custom focus outline duplicates Bootstrap's box-shadow, so focus is doubled on form fields.
24. **The navbar is nearly empty.** Only a brand, plus "Manage Circles" for super-admins. No active-state links and no way to move between Participants, Leaders and Areas except via the dashboard. A real admin nav would remove most per-page button rows.
25. **Error pages are bare.** 404/403/500 have a heading and a button, with no circle context or contact (`count_contact` is available).
26. **Empty and loading states are inconsistent.** Some tables show a message when empty, others an empty table. `.loading` is defined but not used consistently.

## Suggested order

1. Real bugs (A1-A4).
2. Define button, badge and table conventions (B5, B6, B10-B12) and apply in one pass.
3. Shared page header and navbar (B7-B9, D24).
4. Theming, library versions, accessibility (C14, C15, C18, D23).
