param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Python -m PyInstaller --noconfirm --clean --onefile --console --name "Competitive Online Lab" --add-data "payload;payload" --hidden-import ps2_save --distpath dist --workpath build/lab local_online_test.py
    if ($LASTEXITCODE -ne 0) { throw "No se pudo construir Competitive Online Lab.exe" }
} finally {
    Pop-Location
}
