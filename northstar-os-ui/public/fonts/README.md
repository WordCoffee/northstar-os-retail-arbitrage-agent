# Self-hosted fonts

DM Sans and Libre Baskerville (the design system's two families), vendored as woff2
from the Google Fonts CSS on 2026-10-11 and served locally at /ui/fonts/.
No third-party request is made at runtime; tools/check-no-third-party.cjs fails the
build if any non-local host appears in the served UI.
