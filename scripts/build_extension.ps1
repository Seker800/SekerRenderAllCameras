param(
    [string]$BlenderPaths = "",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $repoRoot "camera_batch_renderer"
$outputPath = Join-Path $repoRoot "dist"
$stagingPath = Join-Path $repoRoot "build\package-staging"
$configPath = Join-Path $repoRoot "packaging\blender_targets.json"

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python executable not found: $Python"
}
$resolvedBlenderPaths = @()
if ([string]::IsNullOrWhiteSpace($BlenderPaths)) {
    $resolvedBlenderPaths = @((Get-Command blender -ErrorAction Stop).Source)
}
else {
    $resolvedBlenderPaths = @($BlenderPaths -split '\|' | Where-Object { $_ })
}

function Get-BlenderVersion {
    param([string]$Executable)
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $lines = @(& $Executable --version 2>&1)
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
    $line = $lines | ForEach-Object { $_.ToString() } |
        Where-Object { $_ -match 'Blender\s+\d+\.\d+\.\d+' } | Select-Object -First 1
    if ($code -ne 0 -or $line -notmatch 'Blender\s+(\d+\.\d+\.\d+)') {
        throw "Cannot read Blender version from $Executable"
    }
    return $Matches[1]
}

$executablesByVersion = @{}
foreach ($path in $resolvedBlenderPaths) {
    $resolved = (Resolve-Path -LiteralPath $path).Path
    $executablesByVersion[(Get-BlenderVersion $resolved)] = $resolved
}

New-Item -ItemType Directory -Force -Path $outputPath, $stagingPath | Out-Null
$builder = Join-Path $PSScriptRoot "build_target_packages.py"
$buildJson = & $Python $builder $configPath $sourcePath $stagingPath $outputPath | Out-String
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$builtTargets = $buildJson | ConvertFrom-Json

foreach ($target in $builtTargets) {
    if (-not $executablesByVersion.ContainsKey($target.tested_version)) {
        throw "Missing Blender $($target.tested_version) required for target $($target.id)"
    }
    if ($target.package_type -eq "extension") {
        $blender = $executablesByVersion[$target.tested_version]
        $validationRoot = Join-Path $stagingPath "validation-$($target.id)"
        $environmentPaths = [ordered]@{
            BLENDER_USER_CONFIG = Join-Path $validationRoot "config"
            BLENDER_USER_SCRIPTS = Join-Path $validationRoot "scripts"
            BLENDER_USER_DATAFILES = Join-Path $validationRoot "datafiles"
            BLENDER_USER_EXTENSIONS = Join-Path $validationRoot "extensions"
            BLENDER_USER_RESOURCES = Join-Path $validationRoot "resources"
            TEMP = Join-Path $validationRoot "temp"
            TMP = Join-Path $validationRoot "temp"
        }
        $previousEnvironment = @{}
        try {
            foreach ($entry in $environmentPaths.GetEnumerator()) {
                $previousEnvironment[$entry.Key] = [Environment]::GetEnvironmentVariable(
                    $entry.Key, "Process"
                )
                New-Item -ItemType Directory -Force -Path $entry.Value | Out-Null
                [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
            }
            & $blender --command extension validate $target.source
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        finally {
            foreach ($name in $environmentPaths.Keys) {
                [Environment]::SetEnvironmentVariable(
                    $name, $previousEnvironment[$name], "Process"
                )
            }
        }
    }
}

$releaseGate = Join-Path $PSScriptRoot "release_gate.py"
& $Python $releaseGate --root $repoRoot --packages-only
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($target in $builtTargets) {
    Write-Output "$($target.id): $($target.artifact)"
}
