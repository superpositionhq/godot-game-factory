<#
.SYNOPSIS
  Bring a game's copy of the AutoPlay drop-in up to date (or install it): tools\godot-pipeline\autoplay\addons\autoplay\
  (its scripts and their .uid files) copied unchanged into <game>\addons\autoplay\. One workflow.jsonl row (op
  autoplay.install) and one commit of exactly those files.
.DESCRIPTION
  Safe on a game in progress: it refuses while addons\autoplay or workflow.jsonl have uncommitted changes (commit them
  first), touches no other file, and its commit holds only what it changed, so other work in progress stays as it was,
  staged or not. Files in addons\autoplay that are not the drop-in's are left where they are and named. On a game that
  is up to date it changes nothing and commits nothing. It wires nothing: the autoload line in project.godot
  (AutoPlay="*res://addons/autoplay/autoplay.gd", which a game made from the template has), the game's start_scenario
  handler, its scenario_started and finish_run calls and its bot are the game's own (docs\autoplay-contract.md,
  section 6).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File <root>\godot-game-factory\tools\godot-pipeline\autoplay\install.ps1 -Game <root>\games\<slug>
#>
param(
    [Parameter(Mandatory = $true)][string]$Game,
    # the workflow row's reason; default: what it does
    [string]$Reason = '',
    # say what would change, change nothing
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$repo = [IO.Path]::GetFullPath((Join-Path $here '..\..\..'))
$src = Join-Path $here 'addons\autoplay'
$utf8 = New-Object Text.UTF8Encoding($false)
# Files of an earlier drop-in that this one no longer has, by their path in addons\autoplay\: removed from a game's copy.
$Retired = @()

function Invoke-Git([string]$Dir, [string[]]$GitArgs) {
    # stdout as it is, without PowerShell's line splitting or its stderr records
    $psi = New-Object Diagnostics.ProcessStartInfo 'git'
    $psi.Arguments = (@('-C', $Dir) + $GitArgs | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = $utf8
    $p = [Diagnostics.Process]::Start($psi)
    $err = $p.StandardError.ReadToEndAsync()
    $out = $p.StandardOutput.ReadToEnd()
    $p.WaitForExit()
    return [pscustomobject]@{ Code = $p.ExitCode; Out = $out; Err = $err.Result }
}

# Text as git commits it here: LF line ends (a clone with core.autocrlf has CRLF on disk), UTF-8 without a BOM.
function Read-Text([string]$Path) { return ([IO.File]::ReadAllText($Path, $utf8)).Replace("`r`n", "`n") }
function Get-Sha256([string]$Text) {
    $h = [Security.Cryptography.SHA256]::Create()
    return -join ($h.ComputeHash($utf8.GetBytes($Text)) | ForEach-Object { $_.ToString('x2') })
}

# ---- the game
if (-not (Test-Path -LiteralPath $Game)) { throw "no such folder: $Game" }
$Game = (Resolve-Path -LiteralPath $Game).Path.TrimEnd('\')
foreach ($need in 'project.godot', 'workflow.jsonl') {
    if (-not (Test-Path -LiteralPath (Join-Path $Game $need))) { throw "$Game is not a game made from the template: it has no $need" }
}
$top = Invoke-Git $Game @('rev-parse', '--show-toplevel')
if ($top.Code -ne 0 -or [IO.Path]::GetFullPath($top.Out.Trim()).TrimEnd('\') -ne $Game) { throw "$Game is not the top of a git repo" }
$ours = @('addons/autoplay', 'workflow.jsonl')
$dirty = Invoke-Git $Game (@('status', '--porcelain', '--untracked-files=all', '--') + $ours)
if ($dirty.Out.Trim()) {
    throw "uncommitted changes in what this updates (commit them first, then run it again):`n$($dirty.Out.TrimEnd())"
}
$version = if ((Read-Text (Join-Path $src 'autoplay.gd')) -match '(?m)^const VERSION := (\d+)') { [int]$Matches[1] } else { throw "no VERSION in $src\autoplay.gd" }

# ---- the drop-in: every file of it, LF, unchanged
$had = Test-Path -LiteralPath (Join-Path $Game 'addons\autoplay\autoplay.gd')
if (-not $Reason) {
    $Reason = if ($had) { 'Bring the AutoPlay drop-in (addons/autoplay) up to the current one' }
    else { 'Install the AutoPlay drop-in (addons/autoplay, an unchanged copy) so the game can be played by its bot and recorded' }
}
$changed = New-Object Collections.ArrayList
$hashes = [ordered]@{}
$items = @(Get-ChildItem -LiteralPath $src -File -Recurse | Sort-Object FullName | ForEach-Object {
        [pscustomobject]@{ From = $_.FullName; To = 'addons/autoplay/' + $_.FullName.Substring($src.Length + 1).Replace('\', '/') } })
$mine = @{}
foreach ($it in $items) {
    $text = Read-Text $it.From
    $mine[$it.To] = $true
    $hashes[$it.To] = Get-Sha256 $text
    $dst = Join-Path $Game $it.To
    if ((Test-Path -LiteralPath $dst) -and (Read-Text $dst) -ceq $text) { continue }
    [void]$changed.Add($it.To)
    if ($DryRun) { continue }
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    [IO.File]::WriteAllText($dst, $text, $utf8)
}
$removed = New-Object Collections.ArrayList
$foreign = New-Object Collections.ArrayList
$folder = Join-Path $Game 'addons\autoplay'
if (Test-Path -LiteralPath $folder) {
    foreach ($f in Get-ChildItem -LiteralPath $folder -File -Recurse) {
        $rel = 'addons/autoplay/' + $f.FullName.Substring($folder.Length + 1).Replace('\', '/')
        if ($mine.ContainsKey($rel)) { continue }
        $name = $rel.Substring('addons/autoplay/'.Length)
        if ($Retired -contains $name -or $Retired -contains ($name -replace '\.uid$', '')) {
            [void]$removed.Add($rel)
            if (-not $DryRun) { Remove-Item -LiteralPath $f.FullName -Force }
        } else { [void]$foreign.Add($rel) }
    }
}

Write-Host "AutoPlay drop-in v$version for $Game"
foreach ($c in $changed) { Write-Host "  $(if ($DryRun) { 'would write' } else { 'wrote' }) $c" }
foreach ($r in $removed) { Write-Host "  $(if ($DryRun) { 'would remove' } else { 'removed' }) $r (no longer part of the drop-in)" }
foreach ($f in $foreign) { Write-Host "  left alone: $f is not the drop-in's (keep the game's own code out of addons/autoplay)" }
if (-not (Select-String -LiteralPath (Join-Path $Game 'project.godot') -Pattern '^\s*AutoPlay\s*=\s*"\*res://addons/autoplay/autoplay\.gd"' -Quiet)) {
    Write-Host '  project.godot has no autoload line AutoPlay="*res://addons/autoplay/autoplay.gd" under [autoload]: add it (before the game''s own autoloads)'
}
if ($changed.Count -eq 0 -and $removed.Count -eq 0) { Write-Host '  up to date: nothing to commit'; exit 0 }
if ($DryRun) { exit 0 }

# ---- the workflow.jsonl row, then one commit of exactly these files
$wf = Join-Path $Game 'workflow.jsonl'
$prefix = $null; $number = 0; $lastSeq = 0
foreach ($line in [IO.File]::ReadAllLines($wf)) {
    # the last line with an id; a line cut short is passed over
    if ($line -notmatch '"id"\s*:\s*"([A-Za-z0-9]+)-(\d+)"') { continue }
    $prefix = $Matches[1]
    $number = [int]$Matches[2]
    $lastSeq = if ($line -match '"seq"\s*:\s*(\d+)') { [int]$Matches[1] } else { $number }
}
if (-not $prefix) { throw "$wf has no rows: the game was not made by new-game.ps1" }
$rowId = '{0}-{1:D5}' -f $prefix, ($number + 1)
$toolCommit = $null
$head = Invoke-Git $repo @('rev-parse', '--short=12', 'HEAD')
if ($head.Code -eq 0) { $toolCommit = $head.Out.Trim() }
$row = [ordered]@{
    schema = 'godot-workflow/v0'; id = $rowId; seq = $lastSeq + 1
    time = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffzzz', [Globalization.CultureInfo]::InvariantCulture)
    actor = 'agent'; op = 'autoplay.install'; target = 'addons/autoplay'
    params = [ordered]@{
        autoplay_version = $version; written = @($changed); removed = @($removed)
        files = $hashes; tool_commit = $toolCommit
    }
    reason = $Reason; reason_source = 'agent_note'; status = 'observed'
    source = [ordered]@{ script = 'tools/godot-pipeline/autoplay/install.ps1'; sha256 = (Get-Sha256 (Read-Text $PSCommandPath)); commit = $null }
}
$bytes = [IO.File]::ReadAllBytes($wf)
$sep = if ($bytes.Length -gt 0 -and $bytes[$bytes.Length - 1] -ne 10) { "`n" } else { '' }
[IO.File]::AppendAllText($wf, $sep + ($row | ConvertTo-Json -Compress -Depth 6) + "`n", $utf8)

$paths = @($changed) + @($removed) + @('workflow.jsonl')
$add = Invoke-Git $Game (@('add', '-A', '--') + $paths)
if ($add.Code -ne 0) { throw "git add failed: $($add.Err.Trim())" }
$subject = if ($had) { "Update the AutoPlay drop-in (v$version)" } else { "Install the AutoPlay drop-in v$version" }
$msg = "$subject`n`naddons/autoplay: the AutoPlay drop-in v$version, an unchanged copy.`n`nworkflow: $rowId`n"
$msgFile = Join-Path $Game ".git\autoplay-install-$PID.txt"
[IO.File]::WriteAllText($msgFile, $msg, $utf8)
$commit = Invoke-Git $Game (@('commit', '-q', '-F', $msgFile, '--') + $paths)
Remove-Item -LiteralPath $msgFile -ErrorAction SilentlyContinue
if ($commit.Code -ne 0) {
    throw "the commit failed ($($commit.Err.Trim())): the files and the row $rowId are written; commit them yourself (git user.name / user.email set?)"
}
$sha = (Invoke-Git $Game @('rev-parse', '--short', 'HEAD')).Out.Trim()
Write-Host "  committed $sha (workflow: $rowId)"
Write-Host '  next: wire it (docs/autoplay-contract.md, section 6), build, then test by hand (section 7)'
