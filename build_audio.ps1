param([string]$Compiler = "clang++")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Compiler --target=x86_64-w64-windows-gnu -O2 -fno-exceptions -fno-rtti -c native/competitive_audio.cpp -o payload/competitive_audio.o
    if ($LASTEXITCODE -ne 0) { throw "No se pudo compilar la corrección de audio." }
} finally {
    Pop-Location
}
