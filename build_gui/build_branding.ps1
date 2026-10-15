$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$assets = Split-Path -Parent $PSScriptRoot
$assets = Join-Path $assets 'assets'
$iconSource = Join-Path $assets 'universo_tenkaichi_source.png'
$logoSource = Join-Path $assets 'competitive_edition_logo_source.png'
$iconPng = Join-Path $assets 'universo_tenkaichi_ui.png'
$logoPng = Join-Path $assets 'competitive_edition_logo.png'
$iconFile = Join-Path $assets 'universo_tenkaichi.ico'

function New-ResizedPng([string]$Source, [string]$Destination, [int]$Width, [int]$Height) {
    $sourceImage = [System.Drawing.Image]::FromFile($Source)
    try {
        $bitmap = New-Object System.Drawing.Bitmap($Width, $Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
                $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
                $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $graphics.Clear([System.Drawing.Color]::Transparent)
                $graphics.DrawImage($sourceImage, 0, 0, $Width, $Height)
            } finally {
                $graphics.Dispose()
            }
            $bitmap.Save($Destination, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $bitmap.Dispose()
        }
    } finally {
        $sourceImage.Dispose()
    }
}

New-ResizedPng $iconSource $iconPng 256 256
New-ResizedPng $logoSource $logoPng 336 141

$sourceImage = [System.Drawing.Image]::FromFile($iconSource)
try {
    $sizes = @(16, 24, 32, 48, 64, 128, 256)
    $frames = @()
    foreach ($size in $sizes) {
        $bitmap = New-Object System.Drawing.Bitmap($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        try {
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
                $graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
                $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
                $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
                $graphics.Clear([System.Drawing.Color]::Transparent)
                $graphics.DrawImage($sourceImage, 0, 0, $size, $size)
            } finally {
                $graphics.Dispose()
            }
            $stream = New-Object System.IO.MemoryStream
            $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
            $frames += ,$stream.ToArray()
            $stream.Dispose()
        } finally {
            $bitmap.Dispose()
        }
    }

    $fileStream = [System.IO.File]::Open($iconFile, [System.IO.FileMode]::Create)
    try {
        $writer = New-Object System.IO.BinaryWriter($fileStream)
        try {
            $writer.Write([uint16]0)
            $writer.Write([uint16]1)
            $writer.Write([uint16]$sizes.Count)
            $offset = 6 + (16 * $sizes.Count)
            for ($index = 0; $index -lt $sizes.Count; $index++) {
                $sizeByte = if ($sizes[$index] -eq 256) { 0 } else { $sizes[$index] }
                $writer.Write([byte]$sizeByte)
                $writer.Write([byte]$sizeByte)
                $writer.Write([byte]0)
                $writer.Write([byte]0)
                $writer.Write([uint16]1)
                $writer.Write([uint16]32)
                $writer.Write([uint32]$frames[$index].Length)
                $writer.Write([uint32]$offset)
                $offset += $frames[$index].Length
            }
            foreach ($frame in $frames) {
                $writer.Write($frame)
            }
        } finally {
            $writer.Dispose()
        }
    } finally {
        $fileStream.Dispose()
    }
} finally {
    $sourceImage.Dispose()
}

Write-Host "Branding listo: $iconPng, $logoPng, $iconFile"
