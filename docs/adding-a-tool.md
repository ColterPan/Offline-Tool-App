# Adding a tool

Example: a "Text → QR code" tool. One commit per tool.

## 1. Core logic + tests first (`src/offline_tools/core/qr.py`)

Write `tests/core/test_qr.py` first and watch it fail, then implement:

```python
def make_qr(data: str, *, box_size: int = 10) -> PIL.Image.Image:
    if not data.strip():
        raise InvalidInputError("Type some text or a link first.")
    ...
```

- Take plain values/paths, return a result or write via `unique_output_path(...)`.
- Raise `InvalidInputError` / `OutputError` with a message a non-technical user understands.
- Accept a keyword argument `on_progress: ProgressCallback | None = None` and call
  `report(on_progress, done, total)` (from `core/progress.py`). The background worker always
  calls jobs as `job(on_progress=...)`, so `partial(your_function, args...)` just works.
- No Qt imports.

## 2. Page (`src/offline_tools/ui/tools/qr_page.py`)

Subclass `ToolPage`, add widgets with `self.add_content(...)`, and run the core function through
`run_task`, which runs it in the background, shows a progress bar and puts any error in the
result banner:

```python
self.run_task(
    self._context.runner,
    partial(convert_images, sources, target, out_dir_for=settings.output_dir_for),
    self._on_done,                      # receives the function's return value
    disable=[self.drop_zone, self.convert_button],  # greyed out while it runs
)
```

Use `self.banner.show_success("Saved photo (qr).png", folder=output.parent)` when a file is written.

## 3. Register it (`src/offline_tools/ui/tools/__init__.py`)

Add an entry to `ALL_TOOLS`:

```python
ALL_TOOLS: tuple[Tool, ...] = (
    ...,
    Tool(
        id="qr-code",
        name="QR Code",
        summary="Turn a link, Wi-Fi login or contact into a QR code.",
        category=Category.EVERYDAY,
        page_factory=QrPage,
        keywords=("qr", "wifi", "vcard", "link"),
    ),
)
```

The sidebar, home card and search pick it up automatically.

## 4. Dependencies

Add the library to `pyproject.toml` with a version range, then add a row to
`THIRD_PARTY_LICENSES.md`. **Check the license first**: AGPL libraries (PyMuPDF, Ghostscript)
need a deliberate decision.

## 5. Test the packaged app

Some libraries need extra PyInstaller settings (hidden imports, data files). After adding a
dependency, run the local build (see `docs/release.md`) and try the tool in the installed app.

## 6. Commit

```text
feat: add QR code generator
```

## Reusable widgets

| Widget | Use it for |
|---|---|
| `DropZone` | Drag-and-drop + Browse button, filtered by extension |
| `FileList` | Ordered list of chosen files with Move up/down, Remove, Clear |
| `Card` | Grouping related options |
| `forms.combo` / `forms.form` | (label, value) dropdowns and labelled option rows |
| `ResultBanner` (`self.banner`) | Success with "Open folder", or an error message |
