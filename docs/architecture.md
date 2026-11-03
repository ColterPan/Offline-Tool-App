# Architecture

## Layers

```
src/offline_tools/
├── core/          Pure Python file processing. NO Qt imports. Fully unit-tested.
│   ├── errors.py  ToolError(user_message, detail): message for the UI, detail for the log
│   ├── paths.py   require_file(), unique_output_path(): originals are never overwritten
│   └── hashing.py First tool's logic
├── ui/            PySide6 interface
│   ├── worker.py  TaskRunner: runs core functions on a thread pool, reports back on UI thread
│   ├── theme/     tokens.py (colours, sizes) → stylesheet.py (QSS) → apply_theme()
│   ├── widgets/   DropZone, ResultBanner, Card, ToolPage (standard page layout)
│   ├── pages/     Home, Settings, About
│   ├── tools/     One page per tool + ALL_TOOLS registry list
│   └── main_window.py  Sidebar + stacked pages, tool pages created lazily
├── registry.py    Tool dataclass + ToolRegistry (search, grouping by category)
├── settings.py    Typed, validated wrapper around QSettings (.ini file)
├── logging_setup.py  Rotating log file in the platform log folder
└── app.py         Start-up wiring
```

## Rules

1. **`core` never imports Qt.** Core functions take paths/values and return results or write a
   new file. That keeps them fast to test and reusable (e.g. a future command-line version).
2. **Never touch the input.** Results go to `unique_output_path(...)`, which never returns an
   existing file.
3. **Errors are explicit.** Core raises `ToolError` subclasses with a friendly `user_message`.
   The worker turns any *other* exception into a generic message and logs the traceback.
4. **No blocking the UI thread.** Anything that reads a file goes through `TaskRunner.submit`.
5. **No network.** Nothing in the app opens a connection. If a future feature needs a
   download (AI models), it must ask the user first and be easy to audit.
6. **Validate stored settings.** `AppSettings` treats the .ini file as untrusted input.

## Where things live on the user's machine

| What | Windows | macOS |
|---|---|---|
| App | `%LOCALAPPDATA%\Programs\Offline Tools` (per-user install) | `/Applications/Offline Tools.app` |
| Settings | `%APPDATA%\offline-tools\offline-tools.ini` | `~/.config/offline-tools/offline-tools.ini` |
| Logs | `%LOCALAPPDATA%\offline-tools\Logs` | `~/Library/Logs/offline-tools` |

## Renaming the app

The name is a placeholder. Change `APP_NAME`, `APP_ID`, `EXE_NAME`, `BUNDLE_ID` and `SOURCE_URL`
in `src/offline_tools/__init__.py`. The window title, installer, dmg and log folder all read
from there. Renaming the Python package (`offline_tools`) is optional and purely internal.
