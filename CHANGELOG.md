# Changelog

All notable changes are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - unreleased

### Added

- **QR Code Generator**: link or text, Wi-Fi login (guests scan to join) and contact card
  (vCard). Live preview, four sizes, error-correction levels, save as PNG or SVG, copy image.
- **Images → PDF**: combine photos or scans into one PDF in a chosen order; pages sized to
  each image or A4/Letter with margins; phone photos are auto-rotated.
- **Convert Images**: batch JPG ↔ PNG ↔ WEBP with a quality slider. Camera and location
  metadata is not copied. One bad file doesn't stop the batch.
- **Excel ↔ CSV**: one sheet or all sheets to CSV (Excel-friendly UTF-8 with BOM, or plain
  UTF-8); CSV to .xlsx with number detection that keeps leading zeros and long IDs as text.
  Cells starting with `=` are stored as text so a CSV can't inject formulas.
- `run.bat`: double-click to run from source; sets up and updates the environment itself.

### Changed

- Background jobs are now called with `on_progress=` as a keyword (see docs/adding-a-tool.md).
- Results are written to a temporary `.part` file first, so a failure never leaves a
  half-written file behind.
- CI tests on Windows for every push and on macOS for pull requests and manual runs.

### Fixed

- Release workflow failed to start because it used the `runner` context in job-level `env`.

## [0.0.1] - 2026-11-03

### Added

- App shell: sidebar navigation, home screen with tool search, Settings, About & privacy page.
- Light and dark themes that follow the operating system, or can be set manually.
- Settings for where results are saved (next to the original, or a chosen folder).
- Rotating log file and an "Open log folder" button for troubleshooting.
- First tool: **Check File Hash** (SHA-256, SHA-1, MD5) with an expected-hash comparison.
- Windows installer (Inno Setup) and macOS disk image, built by GitHub Actions on version tags.
