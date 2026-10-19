# Self-hosted fonts

Served first-party under `/fonts/` so CSP (`default-src 'self'`) never needs a
font CDN. All three families are SIL Open Font License 1.1.

| File | Family | Weight | Style |
|---|---|---|---|
| `space-grotesk-*.woff2` | Space Grotesk | 600, 700 | normal |
| `source-sans-3-*.woff2` | Source Sans 3 | 400, 600, 700 | normal |
| `source-serif-4-*-italic.woff2` | Source Serif 4 | 400, 600 | italic |

Latin subsets only. Re-download from the fontsource mirror on jsDelivr if you
bump versions, then confirm `fonts/**` remains in both deploy path filters.
