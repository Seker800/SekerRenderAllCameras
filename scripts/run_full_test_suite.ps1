param(
    [string[]]$BlenderPaths = @(),
    [switch]$SkipGui,
    [switch]$Release
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$reportId = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $PID
$reportRoot = Join-Path $repoRoot "build\test-reports\$reportId"
New-Item -ItemType Directory -Force -Path $reportRoot | Out-Null

if ($BlenderPaths.Count -eq 0) {
    $BlenderPaths = @((Get-Command blender -ErrorAction Stop).Source)
}
$python = (Get-Command python -ErrorAction Stop).Source
$results = [System.Collections.Generic.List[object]]::new()
$manifestText = Get-Content -Raw -LiteralPath (Join-Path $repoRoot "camera_batch_renderer\blender_manifest.toml")
if ($manifestText -notmatch '(?m)^version = "([^"]+)"$') {
    throw "Cannot read package version from blender_manifest.toml"
}
$packageVersion = $Matches[1]

function Invoke-TestStep {
    param(
        [string]$Name,
        [string]$Executable,
        [string[]]$Arguments
    )

    $safeName = $Name -replace '[^A-Za-z0-9_.-]', '_'
    $logPath = Join-Path $reportRoot "$safeName.log"
    $started = Get-Date
    Write-Host "`n=== $Name ==="
    $previousErrorAction = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $Executable @Arguments 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    $output | Tee-Object -FilePath $logPath | ForEach-Object { Write-Host $_ }
    $results.Add([pscustomobject]@{
        name = $Name
        status = if ($exitCode -eq 0) { "passed" } else { "failed" }
        exit_code = $exitCode
        duration_seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 3)
        log = $logPath
    })
    return $exitCode -eq 0
}

function Get-BlenderVersion {
    param([string]$Blender)

    $firstLine = (& $Blender --version 2>&1 | Select-Object -First 1).ToString()
    if ($firstLine -notmatch 'Blender\s+(\d+)\.(\d+)\.(\d+)') {
        throw "Cannot parse Blender version from: $firstLine"
    }
    return [version]::new(
        [int]$Matches[1],
        [int]$Matches[2],
        [int]$Matches[3]
    )
}

$blenderRows = @()
foreach ($blender in $BlenderPaths) {
    $resolvedBlender = (Resolve-Path -LiteralPath $blender).Path
    $version = Get-BlenderVersion $resolvedBlender
    $label = "$($version.Major).$($version.Minor).$($version.Build)"
    $blenderRows += [pscustomobject]@{ path = $resolvedBlender; version = $version; label = $label }
}

if ($Release) {
    if ($SkipGui) {
        throw "Release qualification cannot use -SkipGui"
    }
    $requiredLines = @("4.0", "4.1", "4.2", "4.5", "5.2")
    $actualLines = @($blenderRows | ForEach-Object { "$($_.version.Major).$($_.version.Minor)" })
    $missingLines = @($requiredLines | Where-Object { $_ -notin $actualLines })
    if ($missingLines.Count -gt 0) {
        throw "Release qualification is missing Blender lines: $($missingLines -join ', ')"
    }
}

Invoke-TestStep "python-unit" $python @("-m", "unittest", "discover", "-s", "tests/unit", "-v") | Out-Null
Invoke-TestStep "architecture" $python @("-m", "unittest", "discover", "-s", "tests/architecture", "-v") | Out-Null
Invoke-TestStep "ruff" "uvx" @("ruff", "check", "camera_batch_renderer", "tests", "scripts") | Out-Null

foreach ($row in $blenderRows) {
    $resolvedBlender = $row.path
    $label = $row.label
    Invoke-TestStep "blender-$label-core" $resolvedBlender @(
        "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_blender_tests.py")
    ) | Out-Null
    Invoke-TestStep "blender-$label-edge" $resolvedBlender @(
        "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_blender_edge_cases.py")
    ) | Out-Null
    Invoke-TestStep "blender-$label-environment" $resolvedBlender @(
        "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_environment_pair_acceptance.py")
    ) | Out-Null
    Invoke-TestStep "blender-$label-material" $resolvedBlender @(
        "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_material_id_acceptance.py")
    ) | Out-Null
    if (-not $SkipGui) {
        Invoke-TestStep "blender-$label-gui" $resolvedBlender @(
            "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_gui_render_tests.py")
        ) | Out-Null
    }
}

$buildBlender = $blenderRows[-1]
$buildPassed = Invoke-TestStep "package-build" "powershell" @(
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $repoRoot "scripts\build_extension.ps1"),
    "-Blender", $buildBlender.path,
    "-Python", $python
)
Invoke-TestStep "release-gate" $python @((Join-Path $repoRoot "scripts\release_gate.py")) | Out-Null

if ($buildPassed) {
    foreach ($row in $blenderRows) {
        $testRoot = Join-Path $reportRoot "install-$($row.label)"
        New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
        $oldConfig = $env:BLENDER_USER_CONFIG
        $oldScripts = $env:BLENDER_USER_SCRIPTS
        $oldDatafiles = $env:BLENDER_USER_DATAFILES
        $oldLegacy = $env:RAC_LEGACY_PACKAGE
        try {
            $env:BLENDER_USER_CONFIG = Join-Path $testRoot "config"
            $env:BLENDER_USER_SCRIPTS = Join-Path $testRoot "scripts"
            $env:BLENDER_USER_DATAFILES = Join-Path $testRoot "datafiles"
            if ($row.version -ge [version]"4.2.0") {
                $package = Join-Path $repoRoot "dist\camera_batch_renderer-$packageVersion.zip"
                $installed = Invoke-TestStep "blender-$($row.label)-extension-install" $row.path @(
                    "--command", "extension", "install-file", "-r", "user_default", "-e", $package
                )
                if ($installed) {
                    $demo = Join-Path $testRoot "RenderAllCameras_Demo.blend"
                    Copy-Item -LiteralPath (Join-Path $repoRoot "examples\RenderAllCameras_Demo.blend") -Destination $demo
                    Invoke-TestStep "blender-$($row.label)-installed-demo" $row.path @(
                        "--background", $demo, "--python", (Join-Path $repoRoot "scripts\run_installed_demo.py")
                    ) | Out-Null
                    Invoke-TestStep "blender-$($row.label)-extension-remove" $row.path @(
                        "--command", "extension", "remove", "camera_batch_renderer"
                    ) | Out-Null
                }
            }
            else {
                $env:RAC_LEGACY_PACKAGE = Join-Path $repoRoot "dist\camera_batch_renderer-$packageVersion-legacy.zip"
                Invoke-TestStep "blender-$($row.label)-legacy-install" $row.path @(
                    "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\test_legacy_install.py")
                ) | Out-Null
            }
        }
        finally {
            $env:BLENDER_USER_CONFIG = $oldConfig
            $env:BLENDER_USER_SCRIPTS = $oldScripts
            $env:BLENDER_USER_DATAFILES = $oldDatafiles
            $env:RAC_LEGACY_PACKAGE = $oldLegacy
        }
    }
}

$failed = @($results | Where-Object status -eq "failed")
$extensionPath = Join-Path $repoRoot "dist\camera_batch_renderer-$packageVersion.zip"
$legacyPath = Join-Path $repoRoot "dist\camera_batch_renderer-$packageVersion-legacy.zip"
$packageHashes = @()
foreach ($path in @($extensionPath, $legacyPath)) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $path
        $packageHashes += [pscustomobject]@{ path = $path; sha256 = $hash.Hash }
    }
}
$summary = [ordered]@{
    schema_version = 1
    created_at = (Get-Date).ToString("o")
    mode = if ($Release) { "release" } else { "development" }
    repository = $repoRoot
    report_directory = $reportRoot
    blender_versions = @($blenderRows | ForEach-Object label)
    passed = @($results | Where-Object status -eq "passed").Count
    failed = $failed.Count
    packages = $packageHashes
    results = $results
}
$summaryPath = Join-Path $reportRoot "summary.json"
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryPath -Encoding utf8
Write-Host "`nTest report: $summaryPath"
if ($failed.Count -gt 0) {
    exit 1
}
exit 0
