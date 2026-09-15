$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $repoRoot "camera_batch_renderer"
$outputPath = Join-Path $repoRoot "dist"
$blender = (Get-Command blender -ErrorAction Stop).Source

New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
& $blender --command extension validate $sourcePath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $blender --command extension build --source-dir $sourcePath --output-dir $outputPath
exit $LASTEXITCODE
