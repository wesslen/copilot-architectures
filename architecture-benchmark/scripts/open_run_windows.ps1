#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Open provisioned run folders as VS Code windows, one per run.

.DESCRIPTION
    Uses the standard VS Code CLI (`code <path>`) -- this is unrelated to the
    Copilot CLI. Each window becomes one benchmark run. After each launch the
    script prints the manual protocol for that window.

.PARAMETER RunFolders
    Explicit run folder paths or names under runs/. Takes precedence over -BatchSize.

.PARAMETER BatchSize
    Open the next N runs that have no output/chat_session.json yet. Default 4.

.PARAMETER DelaySeconds
    Seconds to wait between launches so VS Code can settle. Default 3.

.PARAMETER WhatIf
    Print what would be opened without launching anything.

.EXAMPLE
    ./scripts/open_run_windows.ps1 -BatchSize 4

.EXAMPLE
    ./scripts/open_run_windows.ps1 -RunFolders 00-baseline-run01,06-custom-agent-run01
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string[]] $RunFolders,
    [int] $BatchSize = 4,
    [int] $DelaySeconds = 3
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$RunsDir  = Join-Path $RepoRoot 'runs'

if (-not (Test-Path -LiteralPath $RunsDir)) {
    throw "No runs/ directory at $RunsDir. Run ./scripts/provision_runs.ps1 first."
}

function Resolve-RunFolder {
    param([Parameter(Mandatory)] [string] $Name)
    if (Test-Path -LiteralPath $Name) { return (Resolve-Path -LiteralPath $Name).Path }
    $candidate = Join-Path $RunsDir $Name
    if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    throw "Run folder not found: $Name"
}

if ($RunFolders) {
    # Same `pwsh -File` comma-splitting workaround as provision_runs.ps1.
    $names = @(
        $RunFolders |
            ForEach-Object { $_ -split ',' } |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
    $targets = @($names | ForEach-Object { Resolve-RunFolder -Name $_ })
} else {
    if ($BatchSize -lt 1) { throw "-BatchSize must be at least 1 (got $BatchSize)." }
    $targets = @(
        Get-ChildItem -LiteralPath $RunsDir -Directory |
            Sort-Object Name |
            Where-Object { -not (Test-Path -LiteralPath (Join-Path $_.FullName 'output/chat_session.json')) } |
            Select-Object -First $BatchSize |
            Select-Object -ExpandProperty FullName
    )
}

if ($targets.Count -eq 0) {
    Write-Host 'Nothing to open -- every run folder already has output/chat_session.json.'
    return
}

$codeCommand = Get-Command code -ErrorAction SilentlyContinue
if (-not $codeCommand) {
    throw "The VS Code CLI 'code' is not on PATH. In VS Code run: Command Palette -> 'Shell Command: Install code command in PATH'."
}

Write-Host "Opening $($targets.Count) run window(s)."
Write-Host ''

$index = 0
foreach ($target in $targets) {
    $index++
    $name = Split-Path -Leaf $target

    if ($PSCmdlet.ShouldProcess($target, 'code --new-window')) {
        & $codeCommand.Source --new-window $target | Out-Null
    }

    Write-Host ("[{0}/{1}] {2}" -f $index, $targets.Count, $name)
    Write-Host "        1. In Copilot Chat, type: /task0   (send it unmodified)"
    Write-Host "        2. Wait for the agent to finish. Do not intervene or add follow-up prompts."
    Write-Host "        3. Command Palette -> 'Chat: Export Session...' -> save as:"
    Write-Host ("           {0}" -f (Join-Path $target 'output/chat_session.json'))
    Write-Host "        4. Close the window."
    Write-Host ''

    if ($index -lt $targets.Count -and $DelaySeconds -gt 0) {
        Start-Sleep -Seconds $DelaySeconds
    }
}

Write-Host 'All windows launched. Score each run when it is finished:'
Write-Host '  python scripts/score_run.py runs/<run-folder> gold'
Write-Host '  python scripts/summarize_results.py'
