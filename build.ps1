$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pythonExe = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $pythonExe = "python"
    }
}

if (-not $pythonExe) {
    $fallback = "C:\Users\win11\AppData\Local\Programs\Python\Python311\python.exe"
    if (Test-Path $fallback) {
        $pythonExe = $fallback
    } else {
        throw "Could not find a Python interpreter with PyInstaller installed."
    }
}

Write-Host "Building MixGemini with $pythonExe ..."
& $pythonExe -m PyInstaller --clean --noconfirm MixGemini.spec
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$exePath = Join-Path $PSScriptRoot "dist\MixGemini.exe"
if (Test-Path $exePath) {
    $sizeMb = [Math]::Round((Get-Item $exePath).Length / 1MB, 2)
    Write-Host "Build succeeded: $exePath ($sizeMb MB)"
} else {
    throw "Expected output binary not found at $exePath"
}
