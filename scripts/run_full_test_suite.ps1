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
$targetConfig = Get-Content -Raw -LiteralPath (Join-Path $repoRoot "packaging\blender_targets.json") |
    ConvertFrom-Json

function Invoke-TestStep {
    param(
        [string]$Name,
        [string]$Executable,
        [string[]]$Arguments,
        [int]$TimeoutSeconds = 180,
        [string]$SuccessPattern = ""
    )

    $safeName = $Name -replace '[^A-Za-z0-9_.-]', '_'
    $logPath = Join-Path $reportRoot "$safeName.log"
    $started = Get-Date
    Write-Host "`n=== $Name ==="
    $stdoutPath = Join-Path $reportRoot "$safeName.stdout.tmp"
    $stderrPath = Join-Path $reportRoot "$safeName.stderr.tmp"
    $quotedArguments = @($Arguments | ForEach-Object {
        $argument = $_
        if ($argument -eq "") {
            return '""'
        }
        if ($argument -match '[\s"]') {
            return '"' + ($argument -replace '"', '\"') + '"'
        }
        return $argument
    })
    try {
        $process = Start-Process -FilePath $Executable -ArgumentList $quotedArguments -PassThru `
            -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        if ($process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.WaitForExit()
            $exitCode = $process.ExitCode
        }
        else {
            Write-Warning "$Name exceeded the ${TimeoutSeconds}s hard timeout; stopping PID $($process.Id)"
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $process.WaitForExit()
            $exitCode = 124
        }
    }
    finally {
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { @(Get-Content -LiteralPath $stdoutPath) } else { @() }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { @(Get-Content -LiteralPath $stderrPath) } else { @() }
        $output = @($stdout) + @($stderr)
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
    if ($exitCode -eq 0 -and $SuccessPattern) {
        $combinedOutput = $output -join "`n"
        if ($combinedOutput -notmatch $SuccessPattern) {
            $output += "TEST HARNESS ERROR: success marker '$SuccessPattern' was not emitted."
            $exitCode = 125
        }
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

    $previousErrorAction = $ErrorActionPreference
    try {
        # Older Blender builds can emit a harmless TBBmalloc diagnostic on stderr.
        # PowerShell wraps native stderr as an ErrorRecord when the global policy is Stop,
        # so collect the complete process output under Continue and identify the version line.
        $ErrorActionPreference = "Continue"
        $versionOutput = @(& $Blender --version 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorAction
    }
    $versionLine = $versionOutput |
        ForEach-Object { $_.ToString() } |
        Where-Object { $_ -match 'Blender\s+\d+\.\d+\.\d+' } |
        Select-Object -First 1
    if ($exitCode -ne 0 -or -not $versionLine) {
        throw "Cannot parse Blender version (exit $exitCode): $($versionOutput -join ' | ')"
    }
    if ($versionLine -notmatch 'Blender\s+(\d+)\.(\d+)\.(\d+)') {
        throw "Cannot parse Blender version from: $versionLine"
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
Invoke-TestStep "package-stage" $python @(
    (Join-Path $repoRoot "scripts\build_target_packages.py"),
    (Join-Path $repoRoot "packaging\blender_targets.json"),
    (Join-Path $repoRoot "camera_batch_renderer"),
    (Join-Path $repoRoot "build\package-staging"),
    (Join-Path $repoRoot "dist")
) | Out-Null

foreach ($row in $blenderRows) {
    $resolvedBlender = $row.path
    $label = $row.label
    $target = @($targetConfig.targets | Where-Object tested_version -eq $label)
    if ($target.Count -ne 1) {
        throw "No unique package target is configured for Blender $label"
    }
    $runtimeRoot = Join-Path $reportRoot "runtime-$label"
    $environmentPaths = [ordered]@{
        BLENDER_USER_CONFIG = Join-Path $runtimeRoot "config"
        BLENDER_USER_SCRIPTS = Join-Path $runtimeRoot "scripts"
        BLENDER_USER_DATAFILES = Join-Path $runtimeRoot "datafiles"
        BLENDER_USER_EXTENSIONS = Join-Path $runtimeRoot "extensions"
        BLENDER_USER_RESOURCES = Join-Path $runtimeRoot "resources"
        TEMP = Join-Path $runtimeRoot "temp"
        TMP = Join-Path $runtimeRoot "temp"
    }
    $previousEnvironment = @{}
    $oldPackageParent = $env:RAC_PACKAGE_PARENT
    try {
        foreach ($entry in $environmentPaths.GetEnumerator()) {
            $previousEnvironment[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, "Process")
            New-Item -ItemType Directory -Force -Path $entry.Value | Out-Null
            [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
        }
        $env:RAC_PACKAGE_PARENT = Join-Path $repoRoot "build\package-staging\$($target[0].id)"
        Invoke-TestStep "blender-$label-core" $resolvedBlender @(
            "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_blender_tests.py")
        ) -SuccessPattern 'BLENDER_TESTS_OK' | Out-Null
        Invoke-TestStep "blender-$label-edge" $resolvedBlender @(
            "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_blender_edge_cases.py")
        ) -SuccessPattern 'BLENDER_EDGE_CASES_OK' | Out-Null
        Invoke-TestStep "blender-$label-environment" $resolvedBlender @(
            "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_environment_pair_acceptance.py")
        ) -SuccessPattern 'ENVIRONMENT_PAIR_ACCEPTANCE_OK' | Out-Null
        Invoke-TestStep "blender-$label-material" $resolvedBlender @(
            "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_material_id_acceptance.py")
        ) -SuccessPattern 'MATERIAL_ID_ACCEPTANCE_OK' | Out-Null
        if (-not $SkipGui) {
            Invoke-TestStep "blender-$label-gui-host-control" $resolvedBlender @(
                "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_gui_host_control.py")
            ) -TimeoutSeconds 60 -SuccessPattern 'GUI_HOST_CONTROL_OK' | Out-Null
            Invoke-TestStep "blender-$label-gui" $resolvedBlender @(
                "--factory-startup", "--python", (Join-Path $repoRoot "scripts\run_gui_render_tests.py")
            ) -TimeoutSeconds 60 -SuccessPattern 'GUI_RENDER_TESTS_OK' | Out-Null
        }
    }
    finally {
        foreach ($name in $environmentPaths.Keys) {
            [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], "Process")
        }
        $env:RAC_PACKAGE_PARENT = $oldPackageParent
    }
}

$buildArguments = @(
    "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $repoRoot "scripts\build_extension.ps1"),
    "-BlenderPaths", (($blenderRows | ForEach-Object { $_.path }) -join '|'),
    "-Python", $python
)
$buildPassed = Invoke-TestStep "package-build" "powershell" $buildArguments
Invoke-TestStep "release-gate" $python @(
    (Join-Path $repoRoot "scripts\release_gate.py"), "--packages-only"
) | Out-Null

if ($buildPassed) {
    foreach ($row in $blenderRows) {
        $testRoot = Join-Path $reportRoot "install-$($row.label)"
        New-Item -ItemType Directory -Force -Path $testRoot | Out-Null
        $oldConfig = $env:BLENDER_USER_CONFIG
        $oldScripts = $env:BLENDER_USER_SCRIPTS
        $oldDatafiles = $env:BLENDER_USER_DATAFILES
        $oldExtensions = $env:BLENDER_USER_EXTENSIONS
        $oldResources = $env:BLENDER_USER_RESOURCES
        $oldTemp = $env:TEMP
        $oldTmp = $env:TMP
        $oldLegacy = $env:RAC_LEGACY_PACKAGE
        $oldExpectedTarget = $env:RAC_EXPECTED_TARGET
        $oldExpectedMinimum = $env:RAC_EXPECTED_VERSION_MIN
        try {
            $env:BLENDER_USER_CONFIG = Join-Path $testRoot "config"
            $env:BLENDER_USER_SCRIPTS = Join-Path $testRoot "scripts"
            $env:BLENDER_USER_DATAFILES = Join-Path $testRoot "datafiles"
            $env:BLENDER_USER_EXTENSIONS = Join-Path $testRoot "extensions"
            $env:BLENDER_USER_RESOURCES = Join-Path $testRoot "resources"
            $env:TEMP = Join-Path $testRoot "temp"
            $env:TMP = $env:TEMP
            New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
            $target = @($targetConfig.targets | Where-Object tested_version -eq $row.label)[0]
            $env:RAC_EXPECTED_TARGET = $target.id
            $env:RAC_EXPECTED_VERSION_MIN = $target.version_min
            if ($row.version -ge [version]"4.2.0") {
                $package = Join-Path $repoRoot "dist\camera_batch_renderer-$packageVersion-$($target.id).zip"
                $installed = Invoke-TestStep "blender-$($row.label)-extension-install" $row.path @(
                    "--factory-startup", "--command", "extension", "install-file",
                    "-r", "user_default", "-e", $package
                )
                if ($installed) {
                    $demo = Join-Path $testRoot "RenderAllCameras_Demo.blend"
                    $created = Invoke-TestStep "blender-$($row.label)-create-demo" $row.path @(
                        "--background", "--factory-startup",
                        "--python", (Join-Path $repoRoot "scripts\create_demo_scene.py"),
                        "--", $demo
                    ) -SuccessPattern 'DEMO_SCENE_OK'
                    if (-not $created) {
                        continue
                    }
                    Invoke-TestStep "blender-$($row.label)-installed-demo" $row.path @(
                        "--background", $demo, "--python", (Join-Path $repoRoot "scripts\run_installed_demo.py")
                    ) -SuccessPattern 'INSTALLED_DEMO_OK' | Out-Null
                    Invoke-TestStep "blender-$($row.label)-extension-remove" $row.path @(
                        "--factory-startup", "--command", "extension", "remove", "camera_batch_renderer"
                    ) | Out-Null
                }
            }
            else {
                $env:RAC_LEGACY_PACKAGE = Join-Path $repoRoot "dist\camera_batch_renderer-$packageVersion-$($target.id).zip"
                Invoke-TestStep "blender-$($row.label)-legacy-install" $row.path @(
                    "--background", "--factory-startup", "--python", (Join-Path $repoRoot "scripts\test_legacy_install.py")
                ) -SuccessPattern 'LEGACY_INSTALL_TEST_OK' | Out-Null
            }
        }
        finally {
            $env:BLENDER_USER_CONFIG = $oldConfig
            $env:BLENDER_USER_SCRIPTS = $oldScripts
            $env:BLENDER_USER_DATAFILES = $oldDatafiles
            $env:BLENDER_USER_EXTENSIONS = $oldExtensions
            $env:BLENDER_USER_RESOURCES = $oldResources
            $env:TEMP = $oldTemp
            $env:TMP = $oldTmp
            $env:RAC_LEGACY_PACKAGE = $oldLegacy
            $env:RAC_EXPECTED_TARGET = $oldExpectedTarget
            $env:RAC_EXPECTED_VERSION_MIN = $oldExpectedMinimum
        }
    }
}

$failed = @($results | Where-Object status -eq "failed")
$packageHashes = @()
foreach ($target in $targetConfig.targets) {
    $path = Join-Path $repoRoot "dist\camera_batch_renderer-$packageVersion-$($target.id).zip"
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
