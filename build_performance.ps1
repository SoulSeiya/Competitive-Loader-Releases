param([string]$Compiler="clang",[Parameter(Mandatory=$true)][string]$SdlInclude)
$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    & $Compiler --target=x86_64-w64-windows-gnu -O2 -I $SdlInclude -c native/competitive_menu_art.c -o payload/competitive_menu_art.o
    if($LASTEXITCODE -ne 0){throw 'No se pudo compilar el filtro de texturas.'}
} finally {Pop-Location}
