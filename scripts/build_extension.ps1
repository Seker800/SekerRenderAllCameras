param(
    [string]$Blender = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $repoRoot "camera_batch_renderer"
$outputPath = Join-Path $repoRoot "dist"
$manifestPath = Join-Path $sourcePath "blender_manifest.toml"
$manifestText = Get-Content -Raw -LiteralPath $manifestPath
if ($manifestText -notmatch '(?m)^version = "([^"]+)"$') {
    throw "Cannot read the package version from blender_manifest.toml"
}
$version = $Matches[1]

if ([string]::IsNullOrWhiteSpace($Blender)) {
    $Blender = (Get-Command blender -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $Blender -PathType Leaf)) {
    throw "Blender executable not found: $Blender"
}

New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

# Blender 4.2+ standards-compliant Extension package.
& $Blender --command extension validate $sourcePath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Blender --command extension build --source-dir $sourcePath --output-dir $outputPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Blender 4.0.2-4.1 legacy add-on package, generated from the same source tree.
$stagingRoot = Join-Path ([IO.Path]::GetTempPath()) ("rac-legacy-" + [guid]::NewGuid())
$legacyPackage = Join-Path $stagingRoot "camera_batch_renderer"
$legacyOutput = Join-Path $outputPath "camera_batch_renderer-$version-legacy.zip"
try {
    New-Item -ItemType Directory -Force -Path $legacyPackage | Out-Null
    Copy-Item -Path (Join-Path $sourcePath "*") -Destination $legacyPackage -Recurse -Force
    Remove-Item -LiteralPath (Join-Path $legacyPackage "blender_manifest.toml")
    Get-ChildItem -LiteralPath $legacyPackage -Directory -Filter "__pycache__" -Recurse |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $legacyPackage -File -Recurse |
        Where-Object Extension -In ".pyc", ".pyo" |
        Remove-Item -Force
    if (Test-Path -LiteralPath $legacyOutput) {
        Remove-Item -LiteralPath $legacyOutput
    }
    & tar.exe -a -cf $legacyOutput -C $stagingRoot "camera_batch_renderer"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}

Write-Output "Extension: $(Join-Path $outputPath "camera_batch_renderer-$version.zip")"
Write-Output "Legacy add-on: $legacyOutput"
