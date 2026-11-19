<#
.SYNOPSIS
    Build dist\AegisVault.exe (one windowed file) with PyInstaller and print its SHA-256.

.DESCRIPTION
    Uses the project's virtual environment. Set it up once with:

        py -m venv .venv
        .venv\Scripts\python -m pip install -e ".[gui,dev]"

    The build bundles whatever crypto backend that environment has: the Rust
    core when `ferrocrypto` is installed there, the Python adapters otherwise
    (Argon2id and AES-256-GCM from `cryptography`). The hash goes to
    dist\AegisVault.exe.sha256 so a copy can be checked before it is trusted.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\build-exe.ps1
#>
[CmdletBinding()]
param(
    # Python of the build environment; defaults to .venv\Scripts\python.exe.
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $Python) { $Python = Join-Path $root ".venv\Scripts\python.exe" }
if (-not (Test-Path $Python)) {
    throw "Python not found at $Python. Create the environment first (see Get-Help $PSCommandPath)."
}

Push-Location $root
try {
    & $Python -m PyInstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller `
        packaging\windows\AegisVault.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }

    $exe = Join-Path $root "dist\AegisVault.exe"
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash.ToLowerInvariant()
    "$hash  AegisVault.exe" | Set-Content -Encoding ascii -LiteralPath "$exe.sha256"
    $size = [math]::Round((Get-Item -LiteralPath $exe).Length / 1MB, 1)
    Write-Host ""
    Write-Host "dist\AegisVault.exe  ($size MB)"
    Write-Host "SHA-256  $hash"
}
finally {
    Pop-Location
}
