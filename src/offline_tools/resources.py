"""Locate bundled files (icons, fonts) both from source and inside a PyInstaller build."""

from importlib.resources import files
from pathlib import Path


def asset_path(name: str) -> Path:
    return Path(str(files("offline_tools") / "assets" / name))
