<#
.SYNOPSIS
  Check one AutoPlay outputDir against docs/autoplay-contract.md (no video needed). For game sessions testing by hand.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File validate-run.ps1 <root>\games\harbor-run\Logs\autoplay\20261110-161353_s1
  (Scripts/godot.ps1 autoplay writes there; otherwise the folder given to the game with -outputDir, and without one
  the drop-in's user://AutoPlay/<timestamp>)
#>
param([Parameter(Mandatory = $true, Position = 0)][string]$Dir)

. (Join-Path $PSScriptRoot 'common.ps1')
$problems = New-Object System.Collections.ArrayList
$notes = New-Object System.Collections.ArrayList

function Read-Rows([string]$Name, [string]$KindField) {
    $r = Read-RunRows (Join-Path $Dir $Name) $KindField
    if (-not $r) { [void]$problems.Add("missing $Name"); return [ordered]@{ lines = 0; counts = @{} } }
    if ($r.bad_lines) { [void]$problems.Add("$Name has $($r.bad_lines) unparseable lines") }
    if ($r.unstamped) { [void]$problems.Add("$Name has $($r.unstamped) rows without t_ns, qpc and frame") }
    if ($r.non_monotonic) { [void]$problems.Add("$Name t_ns goes backwards $($r.non_monotonic) times") }
    return $r
}

$inputs = Read-Rows 'inputs.jsonl' 'type'
$telemetry = Read-Rows 'telemetry.jsonl' 'event'
if (-not $inputs.counts.ContainsKey('inject')) { [void]$problems.Add('inputs.jsonl has no inject rows') }
foreach ($e in 'run_start', 'scenario_start', 'scenario_end', 'run_end') { if (-not $telemetry.counts.ContainsKey($e)) { [void]$problems.Add("telemetry.jsonl has no $e") } }
foreach ($e in 'score', 'state') { if (-not $telemetry.counts.ContainsKey($e)) { [void]$notes.Add("telemetry has no '$e' events (required for all games)") } }
if ($telemetry.counts.ContainsKey('error')) { [void]$notes.Add("telemetry has $($telemetry.counts['error']) error rows: read them") }

$outcome = $null
try { $outcome = Read-JsonFile (Join-Path $Dir 'outcome.json') } catch { [void]$problems.Add("outcome.json is not JSON: $($_.Exception.Message)") }
if ($outcome) { [void]$notes.Add("AutoPlay drop-in version $(Get-Prop $outcome 'autoplay_version'), engine $(Get-Prop $outcome 'engine') $(Get-Prop $outcome 'engine_version'), renderer $(Get-Prop $outcome 'renderer'), frames $(@(Get-Prop $outcome 'viewport') -join 'x'), schema $(Get-Prop $outcome 'schema')") }
if (-not $outcome) { if (-not (Test-Path (Join-Path $Dir 'outcome.json'))) { [void]$problems.Add('missing outcome.json') } }
else {
    if ((Get-Prop $outcome 'result') -notin @('win', 'lose', 'timeout', 'abort')) { [void]$problems.Add("outcome.result is '$(Get-Prop $outcome 'result')'") }
    if (Get-Prop $outcome 'go_timed_out') { [void]$notes.Add('go_timed_out is true (expected when testing by hand with -goTimeout 0)') }
    $dur = Get-Prop $outcome 'duration_s'
    if ($dur -and [double]$dur -gt 0) { [void]$notes.Add(("scenario {5} ({6}) ran {0:N1} s at {1:N1} fps, {2} injected inputs, result {3}, score {4}" -f [double]$dur, ([double](Get-Prop $outcome 'frames') / [double]$dur), (Get-Prop $outcome 'inputs_injected'), (Get-Prop $outcome 'result'), (Get-Prop $outcome 'score'), (Get-Prop $outcome 'scenario'), (Get-Prop $outcome 'scenario_name'))) }
}
$clock = $null
try { $clock = Read-JsonFile (Join-Path $Dir 'clock.json') } catch { [void]$problems.Add("clock.json is not JSON: $($_.Exception.Message)") }
if (-not $clock) { if (-not (Test-Path (Join-Path $Dir 'clock.json'))) { [void]$problems.Add('missing clock.json') } }
else {
    $labels = @(@(Get-Prop $clock 'samples') | Where-Object { $_ } | ForEach-Object { $_.label })
    foreach ($l in 'start', 'go', 'end') { if ($l -notin $labels) { [void]$problems.Add("clock.json has no '$l' sample") } }
}
if (Test-Path (Join-Path $Dir 'watchdog.json')) { [void]$problems.Add('watchdog.json: the exit watchdog ended a game that hung') }
[void]$notes.Add('the sound is checked on a recording (the engine''s movie carries it), not here')

[void]$notes.Add("inputs: $($inputs.lines) rows $(($inputs.counts.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')")
[void]$notes.Add("telemetry: $($telemetry.lines) rows $(($telemetry.counts.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')")
$status = if ($problems.Count) { 'FAIL' } else { 'PASS' }
Write-Host "$status $Dir"
foreach ($p in $problems) { Write-Host "  problem: $p" }
foreach ($n in $notes) { Write-Host "  note: $n" }
if ($problems.Count) { exit 1 }
