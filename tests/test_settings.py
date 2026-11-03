from pathlib import Path

from PySide6.QtCore import QSettings

from offline_tools.settings import AppSettings, OutputMode, ThemeMode


def test_defaults(settings: AppSettings) -> None:
    assert settings.theme is ThemeMode.SYSTEM
    assert settings.output_mode is OutputMode.NEXT_TO_INPUT
    assert settings.output_folder is None


def test_values_persist_across_instances(tmp_path: Path) -> None:
    ini = str(tmp_path / "s.ini")
    first = AppSettings(QSettings(ini, QSettings.Format.IniFormat))
    first.set_theme(ThemeMode.DARK)
    first.set_output_mode(OutputMode.FOLDER)
    first.set_output_folder(tmp_path)

    second = AppSettings(QSettings(ini, QSettings.Format.IniFormat))

    assert second.theme is ThemeMode.DARK
    assert second.output_mode is OutputMode.FOLDER
    assert second.output_folder == tmp_path


def test_corrupt_values_fall_back_to_defaults(tmp_path: Path) -> None:
    store = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    store.setValue("appearance/theme", "neon")
    store.setValue("output/mode", 42)

    settings = AppSettings(store)

    assert settings.theme is ThemeMode.SYSTEM
    assert settings.output_mode is OutputMode.NEXT_TO_INPUT


def test_output_dir_defaults_to_source_folder(settings: AppSettings, tmp_path: Path) -> None:
    source = tmp_path / "in" / "a.png"

    assert settings.output_dir_for(source) == source.parent


def test_output_dir_uses_chosen_folder(settings: AppSettings, tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    settings.set_output_mode(OutputMode.FOLDER)
    settings.set_output_folder(out)

    assert settings.output_dir_for(tmp_path / "a.png") == out


def test_output_dir_falls_back_when_chosen_folder_was_deleted(
    settings: AppSettings, tmp_path: Path
) -> None:
    settings.set_output_mode(OutputMode.FOLDER)
    settings.set_output_folder(tmp_path / "deleted")
    source = tmp_path / "a.png"

    assert settings.output_dir_for(source) == tmp_path
