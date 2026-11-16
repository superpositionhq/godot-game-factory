<#
.SYNOPSIS
  Write <run>\gameplay.mp4 (the dataset's Gameplay/ file) again, or for a run whose first try failed.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File gameplay-mp4.ps1 harbor-run -Commit ff5f1ee
  powershell -ExecutionPolicy Bypass -File gameplay-mp4.ps1 <game> -RunId <run id> -Force

  Takes the runs that still have the engine's movie (raw\movie.avi: record.ps1 removes it after a good video unless
  -KeepMovie) and no INVALID file. -Commit takes one or more build-commit prefixes (metadata.json build.commit). The
  frames from go to the end of the result hold are encoded as record.ps1 does (Export-GameplayMp4 in common.ps1). Adds
  `gameplay_mp4` to metadata.json and the file to manifest.json. CPU only, below-normal priority. It does not change a
  run's validation: a run that failed for its video is recorded again.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [string[]]$Commit,
    [string[]]$RunId,
    [switch]$Force
)
. (Join-Path $PSScriptRoot 'common.ps1')
Set-BelowNormalPriority
# "a,b" from powershell -File arrives as one string
$Commit = @($Commit | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$RunId = @($RunId | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
$root = Join-Path $RecordingsRoot $Game
$done = 0; $failed = 0; $skipped = 0
foreach ($d in @(Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '_*' -and (-not $RunId -or $_.Name -in $RunId) } | Sort-Object Name)) {
    $m = Read-JsonFile (Join-Path $d.FullName 'metadata.json')
    if (-not $m -or (Test-Path (Join-Path $d.FullName 'INVALID'))) { continue }
    if ($Commit -and -not @($Commit | Where-Object { "$(Get-Prop (Get-Prop $m 'build') 'commit')".StartsWith($_) }).Count) { continue }
    if (-not $Force -and (Test-Path (Join-Path $d.FullName 'gameplay.mp4'))) { $skipped++; continue }
    if (-not (Test-Path (Join-Path $d.FullName 'raw\movie.avi'))) { Write-Step "$($d.Name): no raw\movie.avi left to encode from (record the scenario again)"; $failed++; continue }
    $samples = @{}; foreach ($s in @(Get-Prop (Get-Prop $m 'clock') 'samples')) { if ($s) { $samples[[string]$s.label] = $s } }
    $v = Get-Prop $m 'video'
    if (-not ($samples.ContainsKey('go') -and $samples.ContainsKey('end'))) { Write-Step "$($d.Name): no go and end clock samples to cut the movie by"; $failed++; continue }
    $movie = Get-MediaInfo (Join-Path $d.FullName 'raw\movie.avi')
    $last = if ($movie) { [math]::Min([int]$samples['end'].frame, $movie.frames - 1) } else { [int]$samples['end'].frame }
    $r = Export-GameplayMp4 $d.FullName ([int]$samples['go'].frame) $last ([int]$v.width) ([int]$v.height)
    if ($r.error) { Write-Step "$($d.Name): WARNING gameplay.mp4 not written: $($r.error)"; $failed++; continue }
    $m | Add-Member -Force NoteProperty gameplay_mp4 $r
    Write-JsonFile (Join-Path $d.FullName 'metadata.json') $m
    Update-BundleManifest $d.FullName @('metadata.json', 'gameplay.mp4')
    Write-Step ("{0}: gameplay.mp4 {1:N1} s, {2:N1} MB" -f $d.Name, $r.duration_s, ($r.bytes / 1MB))
    $done++
}
Write-Step "$Game : $done written, $failed failed, $skipped already had one"
if ($failed) { exit 1 }
