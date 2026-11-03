# Third-party components

Offline Tools is GPL-3.0-or-later. It bundles the following components in its installers.
Update this table whenever a dependency is added.

| Component | Used for | License | Source |
|---|---|---|---|
| Qt 6 / PySide6 (Essentials) | User interface | LGPL-3.0 | https://code.qt.io/cgit/pyside/pyside-setup.git |
| Pillow | Image handling, icon generation | MIT-CMU (HPND) | https://github.com/python-pillow/Pillow |
| platformdirs | Locating the log/settings folders | MIT | https://github.com/tox-dev/platformdirs |
| CPython | Runtime | PSF License | https://github.com/python/cpython |
| PyInstaller bootloader | Launching the bundled app | GPL-2.0 with bootloader exception | https://github.com/pyinstaller/pyinstaller |

## LGPL notice for Qt / PySide6

Qt and PySide6 are used under the GNU Lesser General Public License v3. The installed app ships
them as separate shared libraries (in the `_internal` folder), so you can replace them with
your own builds. Their source code is available at the links above.

## Planned components (check the license before adding)

| Component | License | Note |
|---|---|---|
| pypdf | BSD-3-Clause | PDF merge/split/compress |
| pikepdf | MPL-2.0 | PDF repair/advanced operations |
| pypdfium2 | Apache-2.0 / BSD-3-Clause | PDF page thumbnails, PDF → images |
| qrcode | BSD | QR generation |
| openpyxl | MIT | Excel files |
| pillow-heif | BSD-3-Clause + LGPL/GPL codecs | HEIC → JPG; wheels may include GPL x265 (fine under GPL-3.0) |
| rembg + onnxruntime | MIT | Background removal; models downloaded on demand, not bundled |
| PyMuPDF | **AGPL-3.0** | Avoid unless pypdf compression is not good enough |
