# Changelog

All notable changes are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## [0.2.0] - unreleased

### Added

- **Redact Documents** (new *Privacy & safety* section): draw boxes over anything in a PDF or
  photo, page by page, in black or white. The saved copy is flattened to images, so hidden text
  can't be copied out of it.
- **Watermark Photos**: text or logo, nine positions or click anywhere on the live preview, or
  tile across the photo; opacity, size, angle, colour and outline. Batch mode, plus an
  "ID-copy template" ("COPY FOR ____ ONLY" + date). Metadata is not copied.
- **Check a QR Code**: from a photo, a pasted screenshot (Ctrl+V), the webcam, or a pasted link.
  Offline checks for fake bank and government sites, look-alike characters, hidden short
  links, IP-address links and downloads of apps or programs (.apk, .exe). PayNow/SGQR payment
  codes show who you'd pay and whether the code's checksum was tampered with.
- **Scan Document**: finds the page in a phone photo, lets you adjust the corners (mouse or
  keyboard), straightens it and removes shadows: black & white, greyscale or colour, saved as
  PDF, JPG or PNG.
- `--self-test`: exercises every bundled native library (PDFium, OpenCV, zxing, Qt's SVG
  plugin). CI runs it on the installed Windows app and the macOS app.

### Changed

- Installer grows to about 57 MB (OpenCV for the scanner). Unused FFmpeg and software-OpenGL
  DLLs are left out on Windows.
- Checked radio buttons show a proper dot; new amber "warning" colour that meets WCAG contrast.

## [0.1.0] - 2026-11-03

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
