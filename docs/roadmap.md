# Roadmap

Each phase ends with a release. Keep phases small: a finished v0.1 beats a half-done v0.5.

| Version | Theme | Tools / work |
|---|---|---|
| **v0.0.1** ✅ | Foundation | App shell, theme, settings, logging, installer pipeline, Check File Hash |
| **v0.1** ✅ | First real tools | QR code generator (link, Wi-Fi, vCard), Images → PDF, Convert Images (JPG/PNG/WEBP), Excel ↔ CSV |
| v0.2 | Privacy-critical | Compress image (target KB), compress PDF, merge/split/reorder/rotate PDF, HEIC → JPG, remove photo location (EXIF) |
| v0.3 | Public beta | Download section on pantechautomation.com, SmartScreen/Gatekeeper guide, feedback form, VirusTotal check |
| v0.4 | Editing + office data | Resize/crop presets (SG passport 35×45 mm), watermark, sharpen, blur area, batch rename, merge Excel/CSV, remove duplicate rows, CSV ↔ JSON |
| v0.5 | Heavier features | Background removal (opt-in model download), PDF → images, sign PDF, QR reader |
| v1.0 | Polish + trust | Word/Excel → PDF (uses installed Word/LibreOffice), batch mode, shortcuts, accessibility pass, code-signing decision |

## Later (pick by demand)

OCR (Tesseract), video compress/convert/trim/GIF and MP4 → MP3 (FFmpeg), audio transcription
(faster-whisper), PDF password protect, text tools, password generator, zip/unzip.

## Not building

- Video downloaders for YouTube or social media (break platform terms, copyright).
- PDF password crackers (easily misused). "Unlock a PDF you know the password to" is fine.
