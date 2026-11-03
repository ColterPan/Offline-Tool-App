# PyInstaller build spec: onedir (fewer antivirus false positives than onefile, faster start-up).
# Build with packaging/windows/build_windows.ps1 or packaging/macos/build_dmg.sh.
# ruff: noqa: F821  (Analysis, PYZ, EXE, COLLECT, BUNDLE and SPECPATH are injected by PyInstaller)

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))

import offline_tools as meta  # noqa: E402

ASSETS = ROOT / "src" / "offline_tools" / "assets"

# Qt modules the app does not use. Excluding them keeps the download small, and leaving out
# QtNetwork means the bundled app has no Qt networking code at all.
EXCLUDES = [
    "tkinter",
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtXml",
    "PySide6.QtConcurrent",
    "PySide6.QtDBus",
]


def windows_version_info():
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    numbers = tuple(int(part) for part in meta.__version__.split(".")) + (0,)
    strings = [
        StringStruct("CompanyName", "Colter Pan"),
        StringStruct("FileDescription", meta.APP_NAME),
        StringStruct("FileVersion", meta.__version__),
        StringStruct("InternalName", meta.EXE_NAME),
        StringStruct("LegalCopyright", "GPL-3.0-or-later"),
        StringStruct("OriginalFilename", f"{meta.EXE_NAME}.exe"),
        StringStruct("ProductName", meta.APP_NAME),
        StringStruct("ProductVersion", meta.__version__),
    ]
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers[:4], prodvers=numbers[:4]),
        kids=[
            StringFileInfo([StringTable("040904B0", strings)]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )


a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=[(str(ASSETS), "offline_tools/assets")],
    excludes=EXCLUDES,
)
if sys.platform == "win32":
    # OpenCV's FFmpeg DLL (~25 MB) is only for video files/streams. The webcam uses Windows'
    # own camera API (DirectShow), so drop it. On macOS FFmpeg is linked into cv2 itself.
    # opengl32sw.dll (~20 MB) is Qt's software OpenGL fallback; this app draws no OpenGL.
    unused = ("opencv_videoio_ffmpeg", "opengl32sw.dll")
    a.binaries = [b for b in a.binaries if not any(name in b[0].lower() for name in unused)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=meta.EXE_NAME,
    console=False,
    upx=False,  # UPX-packed exes are a common antivirus false-positive trigger
    icon=str(ROOT / "packaging" / "windows" / "icon.ico") if sys.platform == "win32" else None,
    version=windows_version_info() if sys.platform == "win32" else None,
)

coll = COLLECT(exe, a.binaries, a.datas, name=meta.EXE_NAME, upx=False)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{meta.APP_NAME}.app",
        icon=str(ASSETS / "icon.png"),  # PyInstaller converts PNG to .icns using Pillow
        bundle_identifier=meta.BUNDLE_ID,
        info_plist={
            "CFBundleDisplayName": meta.APP_NAME,
            "CFBundleShortVersionString": meta.__version__,
            "CFBundleVersion": meta.__version__,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            # Required: without it macOS terminates the app when it asks for the webcam.
            "NSCameraUsageDescription": (
                f"{meta.APP_NAME} uses the camera only to read QR codes. "
                "Video never leaves this computer."
            ),
        },
    )
