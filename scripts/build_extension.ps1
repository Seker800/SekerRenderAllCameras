param(
    [string]$Blender = "",
    [string]$Python = ""
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
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable not found: $Python"
}

New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

# Blender 4.2+ standards-compliant Extension package.
& $Blender --command extension validate $sourcePath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Blender --command extension build --source-dir $sourcePath --output-dir $outputPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Blender 4.0.2-4.1 deterministic legacy package, generated from the same source tree.
$legacyOutput = Join-Path $outputPath "camera_batch_renderer-$version-legacy.zip"
$legacyBuilder = Join-Path $PSScriptRoot "build_legacy_package.py"
& $Python $legacyBuilder $sourcePath $legacyOutput
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output "Extension: $(Join-Path $outputPath "camera_batch_renderer-$version.zip")"
Write-Output "Legacy add-on: $legacyOutput"
