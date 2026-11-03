# Building and releasing

## Build locally on Windows

One-time setup: install Inno Setup 6 (`winget install --id JRSoftware.InnoSetup -e`).

```powershell
& $env:LOCALAPPDATA\offline-tools\.venv\Scripts\Activate.ps1
.\packaging\windows\build_windows.ps1
```

Output goes to `C:\offline-tools-build\` (deliberately outside OneDrive):

- `dist\OfflineTools\OfflineTools.exe` is the app folder, which you can run directly
- `OfflineTools-Setup.exe` is the installer to share

Install it, open it from the Start menu or desktop shortcut, and try each tool.
To quickly check that a build starts at all: `OfflineTools.exe --smoke-test` (exit code 0).

## Build on macOS

Builds must happen on a Mac (PyInstaller can't cross-compile). Without a Mac, use CI:
**Actions → Release → Run workflow** builds both installers without publishing, and you can
download them from the run's *Artifacts* section.

```bash
bash packaging/macos/build_dmg.sh   # on a Mac, from an activated venv
```

## Release checklist

1. Bump `__version__` in `src/offline_tools/__init__.py` and update `CHANGELOG.md`.
2. Commit: `chore: release v0.1.0`.
3. Tag and push: `git tag v0.1.0 && git push origin main --tags`.
4. GitHub Actions builds, smoke-tests and publishes the release with `SHA256SUMS.txt`.
5. Upload both files to [VirusTotal](https://www.virustotal.com) before announcing.
   If an antivirus flags it, submit it as a false positive to that vendor.
6. Test the installer on a different PC from the one you built on.

## Website download links

Because asset names never change, these always point to the newest release:

```text
https://github.com/ColterPan/Offline-Tool-App/releases/latest/download/OfflineTools-Setup.exe
https://github.com/ColterPan/Offline-Tool-App/releases/latest/download/OfflineTools.dmg
```

`/releases/latest` skips pre-releases, so the release workflow publishes every tag as a normal
release marked *latest* (the app still calls itself beta while on v0.x).

## Code signing (later)

| Platform | Option | Cost | Note |
|---|---|---|---|
| Windows | OV code-signing certificate | ~US$200–400/yr | SmartScreen warnings fade as reputation builds |
| Windows | Microsoft Store (MSIX) | one-time small fee | Store apps skip SmartScreen entirely |
| Windows | Azure Artifact Signing | ~US$10/mo | Individuals: USA/Canada only at time of writing |
| macOS | Apple Developer Program + notarisation | US$99/yr | Removes the "Open Anyway" step |
