param(
    [string]$Python = "python",
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$Project = $PSScriptRoot
$Spec = Join-Path $Project "build_gui\Competitive Loader.spec"
$Dist = Join-Path $Project "dist"
$Work = Join-Path $Project "build"
$Release = Join-Path $Project "release"
$Archive = Join-Path $Release "CompetitiveLoader-windows-x64.zip"
$Package = Join-Path $Release ("package-" + [Guid]::NewGuid().ToString("N"))

if (-not $SkipDependencyInstall) {
    & $Python -m pip install -r (Join-Path $Project "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las herramientas de compilación." }
}

& $Python -m PyInstaller --noconfirm --clean --distpath $Dist --workpath $Work $Spec
if ($LASTEXITCODE -ne 0) { throw "No se pudo construir Competitive Loader.exe." }

Remove-Item -LiteralPath $Archive -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $Package -Force | Out-Null
try {
    Copy-Item -LiteralPath (Join-Path $Dist "Competitive Loader.exe") -Destination $Package
    Copy-Item -LiteralPath (Join-Path $Project "README.txt") -Destination $Package
    Copy-Item -LiteralPath (Join-Path $Project "RISING-BATTLE.md") -Destination $Package
    Copy-Item -LiteralPath (Join-Path $Project "licenses") -Destination (Join-Path $Package "licenses") -Recurse
    Compress-Archive -Path (Join-Path $Package "*") -DestinationPath $Archive -CompressionLevel Optimal
}
finally {
    $StagePath = [IO.Path]::GetFullPath($Package)
    $ReleasePath = [IO.Path]::GetFullPath($Release) + [IO.Path]::DirectorySeparatorChar
    if ($StagePath.StartsWith($ReleasePath, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($StagePath).StartsWith("package-", [StringComparison]::Ordinal)) {
        Remove-Item -LiteralPath $StagePath -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Archive).Hash
Write-Host ""
Write-Host "Paquete listo: $Archive"
Write-Host "SHA-256: $Hash"

