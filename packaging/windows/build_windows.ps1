<#
.SYNOPSIS
    Build the Windows app folder (PyInstaller) and installer (Inno Setup).
.DESCRIPTION
    Run from an activated venv:  .\packaging\windows\build_windows.ps1
    Build output goes to C:\offline-tools-build by default, OUTSIDE OneDrive, so syncing
    can't lock files mid-build. Works in Windows PowerShell 5.1 and PowerShell 7.
#>
param(
    [string]$BuildRoot = "C:\offline-tools-build",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")

function Invoke-Native([string]$What, [scriptblock]$Command) {
    # PowerShell 5.1 treats any stderr output from a program as a fatal error, and PyInstaller
    # logs progress to stderr. Judge success by the exit code instead.
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Command 2>&1 | ForEach-Object { "$_" }
    } finally {
        $ErrorActionPreference = $saved
    }
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

function Find-Iscc {
    $onPath = Get-Command iscc -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    throw "Inno Setup 6 not found. Install it with: winget install --id JRSoftware.InnoSetup -e"
}

$meta = & $Python -c "import offline_tools as m; print(m.APP_NAME); print(m.EXE_NAME); print(m.__version__); print(m.SOURCE_URL)"
if ($LASTEXITCODE -ne 0) { throw "Could not import offline_tools. Is the venv activated and the package installed?" }
$appName, $exeName, $version, $sourceUrl = $meta
Write-Host "Building $appName $version into $BuildRoot"

Invoke-Native "PyInstaller" {
    & $Python -m PyInstaller --noconfirm --clean --log-level WARN `
        --workpath (Join-Path $BuildRoot "work") `
        --distpath (Join-Path $BuildRoot "dist") `
        (Join-Path $repo "packaging\offline_tools.spec")
}

$iscc = Find-Iscc
Invoke-Native "Inno Setup" {
    & $iscc /Q `
        "/DAppName=$appName" `
        "/DAppVersion=$version" `
        "/DExeName=$exeName" `
        "/DSourceUrl=$sourceUrl" `
        "/DSourceDir=$(Join-Path $BuildRoot "dist\$exeName")" `
        "/DOutputDir=$BuildRoot" `
        (Join-Path $repo "packaging\windows\installer.iss")
}

$installer = Join-Path $BuildRoot "$exeName-Setup.exe"
$hash = (Get-FileHash $installer -Algorithm SHA256).Hash.ToLower()
$sizeMb = [math]::Round((Get-Item $installer).Length / 1MB, 1)
Write-Host "Installer: $installer ($sizeMb MB)"
Write-Host "SHA-256:   $hash"
