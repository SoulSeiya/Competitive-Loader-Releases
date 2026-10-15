param([string]$Compiler = "clang++")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Compiler --target=x86_64-w64-windows-gnu -O2 -fno-exceptions -fno-rtti -c native/competitive_effect_model.cpp -o payload/competitive_effect_model.o
    if ($LASTEXITCODE -ne 0) { throw "No se pudo compilar la corrección de modelos de efectos." }
} finally { Pop-Location }
