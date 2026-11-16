<#
.SYNOPSIS
  Release build, then one recorded run per scenario, validated. See docs/godot-pipeline.md.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File pipeline.ps1 harbor-run                     # scenarios from the milestone tag
  powershell -ExecutionPolicy Bypass -File pipeline.ps1 harbor-run -Scenarios 1,2 -Commit HEAD

  Scenarios default to 1..n where milestone/autoplay-<n> ("scenarios 1..n are ready") is the newest such tag reachable
  from the commit; the commit defaults to the game's current branch tip (HEAD). Without -Force, scenarios that already
  have a good run (status ok/warn) of that commit are skipped. One summary row per invocation in
  .recording\<game>\pipeline.jsonl.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [string[]]$Scenarios,   # "1,2" from powershell -File arrives as one string; split below
    [string]$Commit = 'HEAD',
    [string]$MaxSeconds = '600',   # AutoPlay time limit per run (s): "900" for every scenario, or "1=300,3=900" (others 600)
    [switch]$NoAndroid,            # a mobile game: build no APK
    [switch]$Force
)

. (Join-Path $PSScriptRoot 'common.ps1')

function Get-MilestoneScenarios([string]$Dir, [string]$Rev) {
    $tag = Invoke-Git $Dir @('describe', '--tags', '--abbrev=0', '--match', 'milestone/autoplay-*', $Rev) -AllowFail
    if ($LASTEXITCODE -ne 0 -or -not $tag) { return $null }
    $tag = "$tag".Trim()
    if ($tag -match 'milestone/autoplay-(\d+)$') { return [pscustomobject]@{ Tag = $tag; Scenarios = @(1..[int]$matches[1]) } }
    return $null
}

function Get-GoodRunCount([string]$GameSlug, [string]$Sha, [int]$Scenario) {
    $path = Join-Path (Join-Path $LogRoot $GameSlug) 'runs.jsonl'
    if (-not (Test-Path $path)) { return 0 }
    # runs.jsonl also holds event rows (mark-invalid.ps1: event "invalidated", no build_commit); invalidated runs don't count.
    $rows = @(foreach ($line in [System.IO.File]::ReadLines($path)) { try { $line | ConvertFrom-Json } catch { } })
    $invalid = @($rows | Where-Object { (Get-Prop $_ 'event') -eq 'invalidated' } | ForEach-Object { $_.run_id })
    $n = 0
    foreach ($r in $rows) {
        if ($null -eq (Get-Prop $r 'build_commit') -or $null -eq (Get-Prop $r 'status')) { continue }
        if ((Get-Prop $r 'run_id') -in $invalid) { continue }
        if ($r.build_commit -eq $Sha -and (Get-Prop $r 'scenario') -eq $Scenario -and $r.status -in @('ok', 'warn')) { $n++ }
    }
    return $n
}

$info = Get-GameInfo $Game
$maxMap = ConvertTo-MaxSecondsMap $MaxSeconds
$scenarioList = @($Scenarios | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { [int]$_ })
$t0 = Get-Date
$summary = [ordered]@{
    schema = 'godot-pipeline/v1'; game = $Game; trigger = 'manual'; requested = $Commit
    start = $t0.ToString('o'); status = 'ok'; note = ''; build = $null; scenarios = @(); runs = @()
}
try {
    $sha = (Invoke-Git $info.Dir @('rev-parse', '--verify', "$Commit^{commit}")).Trim()
    $summary.commit = $sha
    if ($scenarioList.Count -eq 0) {
        $m = Get-MilestoneScenarios $info.Dir $sha
        if (-not $m) { $summary.status = 'skipped'; $summary.note = 'no milestone/autoplay-* tag reachable' }
        else { $scenarioList = $m.Scenarios; $summary.milestone = $m.Tag }
    }
    $summary.scenarios = $scenarioList
    $summary.max_seconds = [ordered]@{}; foreach ($l in $scenarioList) { $summary.max_seconds["$l"] = Get-MaxSeconds $maxMap $l }
    $todo = @(foreach ($l in $scenarioList) { if ($Force -or (Get-GoodRunCount $Game $sha $l) -lt 1) { $l } })
    if ($summary.status -eq 'ok' -and $todo.Count -eq 0) { $summary.status = 'skipped'; $summary.note = "every scenario already has a good run of $($sha.Substring(0, 8))" }
    if ($summary.status -eq 'ok') {
        Write-Step "== $Game $($sha.Substring(0, 8)): release build"
        $build = & (Join-Path $PSScriptRoot 'build.ps1') $Game -Commit $sha -NoAndroid:$NoAndroid | Select-Object -Last 1
        $an = Get-Prop $build 'android'
        $summary.build = [ordered]@{
            status = (Get-Prop $build 'status'); short_sha = (Get-Prop $build 'short_sha'); output = (Get-Prop $build 'output_path')
            platform = (Get-Prop $build 'platform'); orientation = (Get-Prop $build 'orientation')
            android = $(if ($an) { [ordered]@{ status = (Get-Prop $an 'status'); reason = (Get-Prop $an 'reason') } } else { $null })
            autoplay_version = (Get-Prop $build 'autoplay_version')
        }
        # Leak-scan hits (user name in paths, forbidden names) in the job summary, so they show without builds.jsonl.
        # Warn-only here; the packager is the gate. (Assigned in two steps: an if-expression turns an empty list into
        # null, and [] means a clean scan.)
        $ls = Get-Prop $build 'leak_scan'
        $hits = $null
        if ($null -ne $ls) { $hits = @(Get-Prop $ls 'hits' | Where-Object { $_ } | ForEach-Object { [ordered]@{ file = (Get-Prop $_ 'file'); pattern = (Get-Prop $_ 'pattern'); count = (Get-Prop $_ 'count'); example = (Get-Prop $_ 'example') } }) }
        $summary.build.leak_scan_hits = $hits
        if ((Get-Prop $build 'status') -ne 'ok') { $summary.status = 'failed'; $summary.note = "build failed: $(Get-Prop $build 'error_excerpt')" }
        else {
            foreach ($l in $todo) {
                Write-Step "== $Game scenario ${l}: one run"
                $rows = & (Join-Path $PSScriptRoot 'record.ps1') $Game -Build $build.output_path -Scenario $l -MaxSeconds (Get-MaxSeconds $maxMap $l)
                foreach ($r in @($rows | Where-Object { $_ -and $null -ne (Get-Prop $_ 'run_id') })) {
                    $summary.runs += [ordered]@{ run_id = $r.run_id; scenario = $r.scenario; status = $r.status; result = $r.result }
                }
            }
            if (@($summary.runs | Where-Object { $_.status -eq 'failed' }).Count -gt 0) { $summary.status = 'partial' }
        }
    }
} catch {
    $summary.status = 'failed'; $summary.note = $_.Exception.Message
} finally {
    $summary.end = (Get-Date).ToString('o')
    $summary.duration_s = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
    Add-JsonLine (Join-Path $info.LogDir 'pipeline.jsonl') $summary
    Write-Step "== $Game pipeline: $($summary.status) $($summary.note)"
}
$summary
if ($summary.status -in @('failed', 'partial')) { exit 1 }
