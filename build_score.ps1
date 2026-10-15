param(
    [string]$Compiler = "clang++",
    [Parameter(Mandatory=$true)][string]$ImGuiInclude,
    [Parameter(Mandatory=$true)][string]$SdlInclude
)
$ErrorActionPreference = "Stop"
$IncludePath = (Resolve-Path -LiteralPath $ImGuiInclude).Path
$SdlPath = (Resolve-Path -LiteralPath $SdlInclude).Path
Push-Location $PSScriptRoot
try {
    & $Compiler --target=x86_64-w64-windows-gnu -O2 -fno-exceptions -fno-rtti "-I$IncludePath" "-I$SdlPath" -c native/competitive_score.cpp -o payload/competitive_score.o
    if ($LASTEXITCODE -ne 0) { throw "No se pudo compilar el marcador online." }
} finally {
    Pop-Location
}
