#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Provision isolated run folders for the agent-architecture benchmark.

.DESCRIPTION
    For each architecture x repeat combination this creates
    runs/<architecture>-run<NN>/ containing:

      data/loan_applications.csv        the source CSV only -- never the manifest
      docs/*                            validation, remediation and template docs
      tests/*                           the pytest suite the task runs
      .github/prompts/task0.prompt.md   the single fixed task prompt
      <architecture-specific files>     copied from architectures/<name>/
      output/                           empty; the only folder the agent may write to
      run_meta.json                     provenance + the provisioned-file manifest

    task/data/defect_manifest.json is the answer key and is never copied.

.PARAMETER Architectures
    Folder names under architectures/. Defaults to all of them.

.PARAMETER Repeats
    Number of repeat runs per architecture. Default 1.

.PARAMETER Force
    Overwrite an existing run folder instead of skipping it.

.EXAMPLE
    ./scripts/provision_runs.ps1 -Repeats 3

.EXAMPLE
    ./scripts/provision_runs.ps1 -Architectures 00-baseline,06-custom-agent -Repeats 5
#>
[CmdletBinding()]
param(
    [string[]] $Architectures,
    [int] $Repeats = 1,
    [switch] $Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot         = Split-Path -Parent $PSScriptRoot
$TaskDir          = Join-Path $RepoRoot 'task'
$ArchitecturesDir = Join-Path $RepoRoot 'architectures'
$RunsDir          = Join-Path $RepoRoot 'runs'
$PromptFile       = Join-Path $RepoRoot 'prompts/task0.prompt.md'
$SourceCsv        = Join-Path $TaskDir 'data/loan_applications.csv'

$ForbiddenFiles = @('defect_manifest.json')

# Build artifacts and tool caches must never be provisioned into a run folder --
# score_run.py would otherwise see them as part of the baseline file set.
$ExcludedDirectories = @('__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache', '.git', 'node_modules', '.venv')
$ExcludedExtensions  = @('.pyc', '.pyo')

if ($Repeats -lt 1) { throw "-Repeats must be at least 1 (got $Repeats)." }

foreach ($required in @($SourceCsv, $PromptFile)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required fixture missing: $required. Run task/data/generate_dataset.py first."
    }
}

if (-not $Architectures) {
    $Architectures = @(
        Get-ChildItem -LiteralPath $ArchitecturesDir -Directory |
            Sort-Object Name |
            Select-Object -ExpandProperty Name
    )
}

# `pwsh -File script.ps1 -Architectures a,b` hands the whole list over as one
# string; splitting here makes the comma form work from bash as well as from
# inside PowerShell.
$Architectures = @(
    $Architectures |
        ForEach-Object { $_ -split ',' } |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }
)

function Copy-Tree {
    param(
        [Parameter(Mandatory)] [string] $Source,
        [Parameter(Mandatory)] [string] $Destination
    )
    if (-not (Test-Path -LiteralPath $Source)) { return @() }

    $copied = [System.Collections.Generic.List[string]]::new()
    $sourceRoot = (Resolve-Path -LiteralPath $Source).Path
    foreach ($file in Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -Force) {
        if ($file.Name -eq '.gitkeep') { continue }
        if ($ForbiddenFiles -contains $file.Name) { continue }
        if ($ExcludedExtensions -contains $file.Extension.ToLower()) { continue }

        $relative = [System.IO.Path]::GetRelativePath($sourceRoot, $file.FullName)
        $segments = $relative -split '[\\/]'
        if ($segments | Where-Object { $ExcludedDirectories -contains $_ }) { continue }
        $target   = Join-Path $Destination $relative
        $parent   = Split-Path -Parent $target
        if (-not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
        $copied.Add(($relative -replace '\\', '/'))
    }
    return $copied.ToArray()
}

function Get-FileSha256 {
    param([Parameter(Mandatory)] [string] $Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLower()
}

New-Item -ItemType Directory -Path $RunsDir -Force | Out-Null

$provisioned = 0
$skipped     = 0

foreach ($architecture in $Architectures) {
    $archDir = Join-Path $ArchitecturesDir $architecture
    if (-not (Test-Path -LiteralPath $archDir)) {
        throw "Unknown architecture '$architecture' -- no folder at $archDir."
    }

    for ($repeat = 1; $repeat -le $Repeats; $repeat++) {
        $runName = '{0}-run{1:d2}' -f $architecture, $repeat
        $runDir  = Join-Path $RunsDir $runName

        if (Test-Path -LiteralPath $runDir) {
            if (-not $Force) {
                Write-Host "skip      $runName (already exists; pass -Force to overwrite)"
                $skipped++
                continue
            }
            Remove-Item -LiteralPath $runDir -Recurse -Force
        }

        New-Item -ItemType Directory -Path $runDir -Force | Out-Null
        foreach ($sub in @('data', 'docs', 'tests', 'output', '.github/prompts')) {
            New-Item -ItemType Directory -Path (Join-Path $runDir $sub) -Force | Out-Null
        }

        # Source CSV only. The defect manifest is the answer key and stays put.
        Copy-Item -LiteralPath $SourceCsv -Destination (Join-Path $runDir 'data/loan_applications.csv') -Force

        $null = Copy-Tree -Source (Join-Path $TaskDir 'docs')  -Destination (Join-Path $runDir 'docs')
        $null = Copy-Tree -Source (Join-Path $TaskDir 'tests') -Destination (Join-Path $runDir 'tests')

        # The same prompt lands in the same place for every variant, baseline included.
        Copy-Item -LiteralPath $PromptFile -Destination (Join-Path $runDir '.github/prompts/task0.prompt.md') -Force

        $archFiles = @(Copy-Tree -Source $archDir -Destination $runDir)

        # Guard: the answer key must never reach a run folder.
        $leaked = @(Get-ChildItem -LiteralPath $runDir -Recurse -File -Force |
            Where-Object { $ForbiddenFiles -contains $_.Name })
        if ($leaked.Count -gt 0) {
            throw "Answer key leaked into ${runName}: $($leaked.FullName -join ', ')"
        }

        # Record every provisioned file so score_run.py can detect scope creep.
        $manifest = [ordered]@{}
        foreach ($file in Get-ChildItem -LiteralPath $runDir -Recurse -File -Force | Sort-Object FullName) {
            $relative = ([System.IO.Path]::GetRelativePath($runDir, $file.FullName)) -replace '\\', '/'
            if ($relative -like 'output/*' -or $relative -eq 'run_meta.json') { continue }
            $manifest[$relative] = Get-FileSha256 -Path $file.FullName
        }

        $meta = [ordered]@{
            run_id            = $runName
            architecture      = $architecture
            repeat            = $repeat
            provisioned_at    = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
            prompt            = '/task0'
            model             = ''
            permission_level  = ''
            notes             = ''
            architecture_files = @($archFiles | Sort-Object)
            provisioned_files = $manifest
        }
        $meta | ConvertTo-Json -Depth 6 |
            Set-Content -LiteralPath (Join-Path $runDir 'run_meta.json') -Encoding utf8

        Write-Host ("provision {0} ({1} architecture file(s), {2} provisioned file(s))" -f `
            $runName, $archFiles.Count, $manifest.Count)
        $provisioned++
    }
}

Write-Host ''
Write-Host "Provisioned $provisioned run folder(s) under $RunsDir ($skipped skipped)."
Write-Host "Fill in 'model' and 'permission_level' in each run_meta.json before you start."
Write-Host "Next: ./scripts/open_run_windows.ps1 -BatchSize 4"
