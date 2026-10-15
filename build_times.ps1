param([string]$Compiler = "clang++")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Compiler --target=x86_64-w64-windows-gnu -O2 -fno-exceptions -fno-rtti -c native/competitive_times.cpp -o payload/competitive_times.o
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron compilar los tiempos competitivos." }
} finally {
    Pop-Location
}
