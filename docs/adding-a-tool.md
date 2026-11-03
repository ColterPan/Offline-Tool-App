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
- Accept an optional `on_progress(done, total)` callback for slow work.
- No Qt imports.

## 2. Page (`src/offline_tools/ui/tools/qr_page.py`)

Subclass `ToolPage`, add widgets with `self.add_content(...)`, and run the core function through
the runner so the UI never freezes:

```python
self._runner.submit(
    partial(make_qr, text),
    on_success=self._on_done,
    on_error=lambda message, _detail: self.banner.show_error(message),
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
