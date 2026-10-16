# Vendored front-end libraries

Self-hosted so pages do not depend on third-party CDNs (and so the
Content-Security-Policy in `app.py` can stay `'self'` only). Source maps were
stripped. Licences are alongside each library.

| Library | Version | Files |
|---|---|---|
| Bootstrap | 5.3.3 | `bootstrap/css/bootstrap.min.css`, `bootstrap/js/bootstrap.bundle.min.js` |
| Bootstrap Icons | 1.11.3 | `bootstrap-icons/bootstrap-icons.min.css`, `bootstrap-icons/fonts/` |
| Leaflet | 1.9.4 | `leaflet/leaflet.css`, `leaflet/leaflet.js`, `leaflet/images/` |

Each `.css` and `.js` file has a pre-compressed `.gz` copy next to it. `app.py`
(`PrecompressedStaticFlask`) sends that to browsers that accept gzip, so nothing
is compressed per request. Fonts and images are already compressed and have no
`.gz`.

To upgrade, download the same files from the npm package (jsDelivr or unpkg)
at the new version, replace them here, run `python utils/gzip_vendor.py` to
regenerate the `.gz` files, and update this table and the version in
`UX_REVIEW.md`. A unit test fails if a `.gz` no longer matches its source.
