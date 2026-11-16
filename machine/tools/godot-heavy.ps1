# Run one heavy Godot job (an import, an export, a generator script, a rendered play of the project or of an exported
# player) under a machine-wide limit so the parallel game sessions don't exhaust CPU/RAM. Waits for a free slot.
#   & <root>\tools\godot-heavy.ps1 -Label "island-survival import" -- "<root>\godot\4.7.2\Godot_v4.7.2-stable_win64_console.exe" --headless --path <root>\games\island-survival --import
# Exit code is the job's; 125 when the limiter itself could not run the job (called wrongly, its ggf-root.ps1 missing,
# a job that would not start), so a caller can tell "the job exited N" from "there was no job".
# Waits/acquire/release are appended to <root>\.recording\_heavy-jobs.jsonl.
# <root> is the machine root (machine/lib/ggf-root.ps1); machine/bootstrap.ps1 installs this file as
# <root>\tools\godot-heavy.ps1 with a copy of ggf-root.ps1 next to it.
#
# Slot model (docs/godot-pipeline.md, "Machine-wide slots"):
# - Slots are named mutexes, one per slot (ggf-root.ps1 Get-GGFSlotMutexes): a job killed before it releases leaves its
#   mutex abandoned and the next job takes it over, so no slot leaks. Counts are read at every call, so a config change
#   applies at once.
# - The mutex names are another factory's (Global\ue-heavy-slot-<n>, Global\ue-gpu-slot-<n>,
#   Global\ue-heavy-low-slot): on a machine that runs several factories, the jobs of all draw from one set of slots,
#   so together they never run more heavy or GPU jobs than the PC holds. This limiter also reads the other factories'
#   job logs (waiting jobs, recent GPU starts) and their recording flags (Get-GGFJobLogs, Get-GGFRecordingFlags). It
#   writes nothing of theirs.
# - General slots (Global\ue-heavy-slot-<n>): every job takes one. Count: "heavy_slots" in the machine config, else the
#   hardware formula in ggf-root.ps1 Get-GGFComputedSlots (bootstrap.ps1 writes it to the config).
# - GPU slots (Global\ue-gpu-slot-<n>): jobs that render (the Godot exe without --headless: a play of the project, a
#   screenshot run, the editor; an exported player) take one together with a general slot, never one while waiting for
#   the other. Count: "gpu_slots", else the formula.
# - VRAM guard: a GPU job starts only while the GPU's used VRAM is under "gpu_vram_limit_mb" (default half the VRAM) and
#   no other GPU job that still runs started in the last 60 s (a new renderer's VRAM shows only once it has loaded);
#   otherwise it gives the slot back and looks again every 30 s (logged as vram_wait).
# - Another factory's recording is exclusive: its recorder captures the screen and takes every GPU slot, and while one
#   waits (builds\_queue\_recording-wants-gpu fresh in that factory's root) new GPU jobs here hold back.
# - -Low (background work): one low job machine-wide; it takes a general slot only while no other job waits for one and
#   another slot stays free; its process runs below normal priority.
[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$Label = 'godot job',
  [int]$Slots = 0,   # 0: "heavy_slots" in the machine config, else the hardware formula (ggf-root.ps1 Get-GGFComputedSlots)
  [switch]$Gpu,   # force the GPU slot (auto-detected for the Godot exe without --headless and for exported players)
  [switch]$Low,   # background work: yields to every other job, one at a time, below-normal priority
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Command
)
$ErrorActionPreference = 'Continue'
trap { Write-Error $_; exit 125 }   # an error of the limiter's own (a config that is not JSON) is not a job's exit code
if ($Command.Count -and $Command[0] -eq '--') { $Command = $Command[1..($Command.Count - 1)] }
# PowerShell splits an unquoted `-Key=C:/x` passed to a script into `-Key=C:` and `/x` (it reads `-Name:` as parameter
# syntax); glue such pairs back together.
$joined = New-Object Collections.Generic.List[string]
for ($i = 0; $i -lt $Command.Count; $i++) {
  if ($Command[$i] -match '^-[^\s=]+=[A-Za-z]:$' -and $i + 1 -lt $Command.Count -and $Command[$i + 1] -match '^[\\/]') {
    $joined.Add($Command[$i] + $Command[$i + 1]); $i++
  } else { $joined.Add($Command[$i]) }
}
$Command = $joined.ToArray()
if (-not $Command) { Write-Error 'usage: godot-heavy.ps1 -Label <text> -- <exe> <args...>'; exit 125 }
# ggf-root.ps1 sits next to the installed copy, or in ..\lib in the repo.
$ggfLib = @((Join-Path $PSScriptRoot 'ggf-root.ps1'), (Join-Path $PSScriptRoot '..\lib\ggf-root.ps1')) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ggfLib) { Write-Error "godot-heavy: ggf-root.ps1 not found next to this script: install it with machine\bootstrap.ps1"; exit 125 }
. $ggfLib
$ggfRoot = Get-GGFRoot
$plan = Get-GGFSlotPlan
if ($Slots -le 0) { $Slots = $plan.heavy_slots }
$log = Join-Path $ggfRoot '.recording\_heavy-jobs.jsonl'
$jobLogs = Get-GGFJobLogs   # ours first, then the other factories' when any is set up here
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
function Log($event, $extra) {
  $row = [ordered]@{ time = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffzzz', [Globalization.CultureInfo]::InvariantCulture); event = $event; label = $Label; pid = $PID; cwd = (Get-Location).Path }
  if ($extra) { foreach ($k in $extra.Keys) { $row[$k] = $extra[$k] } }
  # Several jobs log at once: serialise appends with a named mutex and retry on a transient sharing violation.
  $line = ($row | ConvertTo-Json -Compress) + "`n"
  $m = New-Object Threading.Mutex($false, 'Global\ggf-heavy-log')
  [void](Enter-GGFMutex $m 10000)
  try {
    for ($i = 0; $i -lt 5; $i++) {
      try { [IO.File]::AppendAllText($log, $line, (New-Object Text.UTF8Encoding($false))); break }
      catch [IO.IOException] { Start-Sleep -Milliseconds (50 * ($i + 1)) }
    }
  } finally { try { $m.ReleaseMutex() } catch { } }
}
# The last lines of every job log (ours and the other factories'), oldest first within each.
function Get-JobLogTail([int]$Lines) {
  foreach ($l in $jobLogs) { try { Get-Content -LiteralPath $l -Tail $Lines -ErrorAction Stop } catch { } }
}
$heavyM = Get-GGFSlotMutexes heavy $Slots
$cmdText = $Command -join ' '
# GPU: the Godot exe renders unless --headless (a play of the project from source, a screenshot run, the editor), and
# so does an exported player: an exe under a Build or builds folder. A launcher that starts one of them (the task
# check's desk.py, which gives the game a desktop of its own) counts the same: the exe is looked for among the
# arguments too. Anything else takes a GPU slot only with -Gpu; --headless anywhere means none.
$isGodot = @($Command | Where-Object { [IO.Path]::GetFileName(($_ -replace '"', '')) -match '(?i)^Godot[^\\/]*\.exe$' }).Count -gt 0
$isPlayer = (-not $isGodot) -and @($Command | Where-Object { $_ -match '(?i)[\\/](Build|Builds)[\\/].*\.exe$' }).Count -gt 0
$isGpu = $Gpu -or $isGodot -or $isPlayer
if ($cmdText -match '(?i)(^|\s)--headless(\s|$)') { $isGpu = $false }
$gpuSlots = [math]::Min(8, [int]$plan.gpu_slots)
$vramLimit = [int]$plan.gpu_vram_limit_mb
$gpuM = if ($isGpu) { Get-GGFSlotMutexes gpu $gpuSlots } else { $null }
$heavyIdx = -1; $gpuIdx = -1; $lowHeld = $false
function Get-VramMB([string]$What) {
  try { $v = & nvidia-smi "--query-gpu=memory.$What" --format=csv,noheader,nounits 2>$null | Select-Object -First 1 } catch { $v = $null }
  if ("$v".Trim() -match '^\d+$') { return [int]"$v".Trim() } else { return $null }
}
if ($isGpu -and $vramLimit -le 0) { $tot = Get-VramMB 'total'; $vramLimit = if ($tot) { [int]($tot / 2) } else { 8192 } }
$t0 = Get-Date
# "slots":"mutex" as in the other factories' limiter rows (it marks a job of the per-slot mutexes there), so all job logs read alike
Log 'wait' @{ command = $cmdText; gpu = [bool]$isGpu; low = [bool]$Low; slots = 'mutex' }
$flags = Get-GGFRecordingFlags
function Test-RecordingWaits {
  foreach ($f in $flags) { if ((Test-Path $f) -and ((Get-Date) - (Get-Item $f).LastWriteTime).TotalMinutes -lt 20) { return $true } }
  return $false
}
# A GPU job that started in the last minute has not loaded yet: its VRAM does not show, so wait for it to settle. One
# that has ended (its "end" row, or its limiter gone: a killed one logs none) holds no VRAM: a play lasts seconds, and
# waiting out the minute after each one that had already ended would make every play of a task check wait.
function Test-VramBusy {
  $script:vramUsed = Get-VramMB 'used'
  $recent = @{}
  foreach ($l in (Get-JobLogTail 200)) {
    if ($l -notmatch '"event":"(start|end)"') { continue }
    # a row that does not parse (a time written in another culture's format) is skipped, not printed into the job's output
    try { $r = $l | ConvertFrom-Json; $age = ((Get-Date) - [datetime]$r.time).TotalSeconds } catch { continue }
    if ($r.event -eq 'end') { $recent.Remove([int]$r.pid) }
    elseif ($r.gpu -and $r.pid -ne $PID -and $age -lt 60) { $recent[[int]$r.pid] = $true }
  }
  $script:vramRecent = @($recent.Keys | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue }).Count -gt 0
  $script:vramRecent -or ($null -ne $script:vramUsed -and $script:vramUsed -gt $vramLimit)
}
if ($gpuM) {
  # GPU jobs take a GPU slot and a general slot together or not at all: holding the GPU slot while waiting for a
  # general one blocks every other GPU job and leaves the GPU idle. Another factory's recording has priority: while its
  # recorder has flagged that it waits for the GPU (a fresh _recording-wants-gpu file; one over 20 min old is ignored),
  # GPU jobs here hold back. VRAM guard: start only while the GPU's used VRAM is under the limit (per-process VRAM is
  # not available under WDDM) and no GPU job started in the last minute.
  $nextNote = Get-Date; $nextVramLog = Get-Date
  while ($true) {
    if (Test-RecordingWaits) {
      if ((Get-Date) -ge $nextNote) { Write-Host "[godot-heavy] a recording is waiting for the GPU; holding back since $($t0.ToString('HH:mm:ss'))..."; $nextNote = (Get-Date).AddMinutes(1) }
      Start-Sleep -Seconds 15; continue
    }
    $gpuIdx = Enter-GGFSlot $gpuM
    if ($gpuIdx -ge 0) {
      if (Test-VramBusy) {
        Exit-GGFSlot $gpuM $gpuIdx; $gpuIdx = -1
        if ((Get-Date) -ge $nextVramLog) {
          Write-Host "[godot-heavy] $vramUsed MB VRAM in use (limit $vramLimit MB)$(if ($vramRecent) { ', a GPU job started under a minute ago' }): waiting..."
          Log 'vram_wait' @{ gpu = $true; vram_used_mb = $vramUsed; limit_mb = $vramLimit; settling = $vramRecent; slots = 'mutex' }
          $nextVramLog = (Get-Date).AddMinutes(5)
        }
        Start-Sleep -Seconds 30; continue
      }
      $heavyIdx = Enter-GGFSlot $heavyM
      if ($heavyIdx -ge 0) { break }
      Exit-GGFSlot $gpuM $gpuIdx; $gpuIdx = -1
    }
    if ((Get-Date) -ge $nextNote) { Write-Host "[godot-heavy] waiting for a GPU slot ($gpuSlots) and a general slot ($Slots) together since $($t0.ToString('HH:mm:ss'))..."; $nextNote = (Get-Date).AddMinutes(1) }
    Start-Sleep -Seconds 3
  }
}
function Test-OthersWaiting {
  # jobs whose last logged event is 'wait' and whose process still runs (every factory's limiter logs the same events)
  $last = @{}
  foreach ($l in (Get-JobLogTail 400)) {
    try { $r = $l | ConvertFrom-Json } catch { continue }
    # (other low-priority jobs wait for this one, and GPU jobs wait for the GPU slot, not a general one: neither counts;
    # a GPU job that gets the GPU still finds the general slot a low job always leaves free)
    if ($r.pid -and $r.pid -ne $PID) { $last[[int]$r.pid] = if ($r.low -or ($r.event -eq 'wait' -and $r.gpu)) { 'other' } else { $r.event } }
  }
  foreach ($p in $last.Keys) {
    if ($last[$p] -eq 'wait' -and (Get-Process -Id $p -ErrorAction SilentlyContinue)) { return $true }
  }
  return $false
}
$lowM = $null
if ($Low) {
  # Low-priority work never makes another job wait: one low job machine-wide (a mutex shared with the other factories,
  # so a killed one does not block the next), and it takes a general slot only while nobody else is waiting and
  # another slot would still be free.
  $lowM = New-Object Threading.Mutex($false, 'Global\ue-heavy-low-slot')
  while (-not (Enter-GGFMutex $lowM 60000)) { Write-Host "[godot-heavy] low priority: another low-priority job runs; waiting..." }
  $lowHeld = $true
  while ($true) {
    if (-not (Test-OthersWaiting)) {
      $heavyIdx = Enter-GGFSlot $heavyM
      if ($heavyIdx -ge 0) {
        if ($Slots -lt 2) { break }
        $spare = Enter-GGFSlot $heavyM 0 @($heavyIdx)
        if ($spare -ge 0) { Exit-GGFSlot $heavyM $spare; break }
        Exit-GGFSlot $heavyM $heavyIdx; $heavyIdx = -1
      }
    }
    Start-Sleep -Seconds 20
  }
} elseif ($heavyIdx -lt 0) {
  $nextNote = Get-Date
  while ($true) {
    $heavyIdx = Enter-GGFSlot $heavyM
    if ($heavyIdx -ge 0) { break }
    if ((Get-Date) -ge $nextNote) {
      Write-Host "[godot-heavy] waiting for a free slot ($Slots max) since $($t0.ToString('HH:mm:ss'))..."
      $nextNote = (Get-Date).AddMinutes(1)
    }
    Start-Sleep -Seconds 3
  }
}
Log 'start' @{ waited_s = [int]((Get-Date) - $t0).TotalSeconds; gpu = [bool]$isGpu; low = [bool]$Low; slot = $heavyIdx; gpu_slot = $(if ($isGpu) { $gpuIdx } else { $null }); vram_used_mb = $(if ($isGpu) { Get-VramMB 'used' } else { $null }) }
$t1 = Get-Date
# Start the process directly and wait for it: `& exe` returns at once for GUI-subsystem programs (the Godot exe without
# its console wrapper, an exported player), which would release the slot while the job still runs. Arguments with
# spaces are quoted; -Key=value tokens keep the quotes after '=' so the program reads the whole value. Windows' own
# rules (CommandLineToArgvW, the C runtime): an empty argument is "" (unquoted, it vanished), and backslashes before a
# quote or the closing quote are doubled (a quoted path ending in \ swallowed the arguments after it).
function Quote-Arg([string]$a) {
  if ($a -and $a -notmatch '[\s"]') { return $a }
  $m = [regex]::Match($a, '^(-?[^=\s"]+=)(.*)$')
  $pre, $v = if ($m.Success) { $m.Groups[1].Value, $m.Groups[2].Value } else { '', $a }
  return $pre + '"' + (($v -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"'
}
$code = $null
try {
  $exe = $Command[0]
  $argLine = (@($Command | Select-Object -Skip 1) | ForEach-Object { Quote-Arg $_ }) -join ' '
  if ($exe -match '\.(bat|cmd)$') { $argLine = "/c `"`"$exe`" $argLine`""; $exe = "$env:ComSpec" }
  Write-Verbose "exe=[$exe] args=[$argLine]"
  $psi = New-Object Diagnostics.ProcessStartInfo $exe, $argLine
  $psi.UseShellExecute = $false
  $proc = [Diagnostics.Process]::Start($psi)
  if ($Low) { try { $proc.PriorityClass = [Diagnostics.ProcessPriorityClass]::BelowNormal } catch { } }
  $proc.WaitForExit()
  $code = $proc.ExitCode
} finally {
  if ($gpuM) { Exit-GGFSlot $gpuM $gpuIdx }
  Exit-GGFSlot $heavyM $heavyIdx
  if ($lowHeld) { try { $lowM.ReleaseMutex() } catch { } }
  Log 'end' @{ exit_code = $code; duration_s = [int]((Get-Date) - $t1).TotalSeconds; slots = 'mutex' }
}
exit $(if ($null -ne $code) { $code } else { 125 })   # no exit code: the job never started (e.g. no such exe), not a 0
