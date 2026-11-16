# __TITLE__: the game's engine runs, through the machine-wide limiter (<root>\tools\godot-heavy.ps1).
#   powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 import                      (import; fails on a script error: "the project compiles")
#   powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 step -Script steps/<name>.gd -Reason "..."
#   powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 row -Op <area.verb> -Target <what> -Reason "..." [-Params '<json>'] [-Direction <id>] [-Status failed]
#   powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 build [-Android] [-Reason "..."]
#   powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 play [-Scenario <n>] [-Seconds 60] [-Shots <n>] [-Extra "..."] [-Tag <name>]
#   powershell -ExecutionPolicy Bypass -File Scripts/godot.ps1 autoplay [-Scenario <n>] [-MaxSeconds 120] [-Seed 0] [-Skill 1] [-Audible] [-Extra "..."]
# `step` runs one generator script (steps/<name>.gd, a SceneTree script that ends with quit()) headless and appends its
# workflow.jsonl row: op editor.step, the script's path and the sha256 of its text as it ran, the status from the exit
# code. Keep this call shape: the creation replay recognises "godot.ps1 step -Script <path>" in the recorded command.
# `row` appends one workflow.jsonl row for work done by hand (a scene written, a script edited, a setting changed), with
# the id and seq that follow the file's last row. -Params is a JSON object, or the path of a file that holds one. An op
# user.direction is written as the user's row (params {"direction": "...", "via": "..."}).
# `build` exports the Windows player to Build/Windows/__PROJECT__.exe (one file) and logs a build.player row. -Android
# (a mobile game) also exports Build/Android/__PROJECT__.apk when this machine has the Android toolchain
# (machine\get-android.ps1); without it the APK is skipped by name and the Windows build is the result.
# `play` runs the project from source, rendered, at the game's exact frame size (1920x1080; a portrait mobile game
# 1080x1920, whatever the window shows), and stops it after -Seconds. -Shots n saves n evenly spaced PNG frames of
# those seconds to Logs/godot-ps1/<tag>/ and the game then quits by itself.
# `autoplay` runs the built player as a recording does (the AutoPlay drop-in, addons/autoplay): the bot plays scenario
# n for at most -MaxSeconds, starting at once (no recorder's go file), on a Windows desktop of its own (nothing on the
# screen, the keyboard and cursor left alone, the sound muted unless -Audible); the run's files go to
# Logs/autoplay/<time>_s<n>/, and a summary of them is printed.
# Engine: $env:GODOT_EDITOR, else the factory's pinned editor (<root>\tools\ggf-root.ps1 Get-GGFGodot). Limiter and
# ggf-root.ps1: $env:GGF_ROOT\tools, else two folders up (<root>). Logs: Logs/godot-ps1/.
param(
  [Parameter(Position = 0)][ValidateSet('import', 'step', 'row', 'build', 'play', 'autoplay')][string]$Mode,
  [string]$Script = '',
  [string]$Reason = '',
  [string]$Op = '',
  [string]$Target = '',
  [string]$Params = '',
  [string]$Direction = '',
  [ValidateSet('observed', 'failed', 'unrecorded', 'reverted')][string]$Status = 'observed',
  [switch]$Android,
  [int]$Scenario = 0,
  [int]$Seconds = 60,
  [int]$Shots = 0,
  [string]$Extra = '',
  [string]$Tag = 'test',
  [int]$MaxSeconds = 120,
  [int]$Seed = 0,
  [double]$Skill = 1,
  [switch]$Audible
)
$ErrorActionPreference = 'Continue'
$Proj = Split-Path $PSScriptRoot -Parent
$utf8 = New-Object Text.UTF8Encoding($false)
$t0 = Get-Date
function Done([int]$Code) { Write-Host "exit code $Code ($([int]((Get-Date) - $t0).TotalSeconds) s)"; exit $Code }

# ---- workflow.jsonl (schema godot-workflow/v0): one row appended at the moment an operation happens --------------------
$Workflow = Join-Path $Proj 'workflow.jsonl'

# The id prefix, the last row number and the last seq, read from the last line that has an id (a line cut short, by a
# crash or by hand, is passed over rather than stopping every later row).
function Get-LastRow {
  $id = $null; $seq = $null
  if (Test-Path -LiteralPath $Workflow) {
    # read beside another writer: a plain read refuses a file that one has open
    $r = New-Object IO.StreamReader((New-Object IO.FileStream($Workflow, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)), $utf8)
    try {
      while ($null -ne ($line = $r.ReadLine())) {
        $m = [regex]::Match($line, '"id"\s*:\s*"([A-Za-z0-9]+)-(\d+)"')
        if (-not $m.Success) { continue }
        $id = $m; $seq = [regex]::Match($line, '"seq"\s*:\s*(\d+)')
      }
    } finally { $r.Close() }
  }
  if (-not $id) { throw 'workflow.jsonl has no rows: the project was not created by new-game.ps1' }
  $n = [int]$id.Groups[2].Value
  return @{ prefix = $id.Groups[1].Value; number = $n; seq = $(if ($seq.Success) { [int]$seq.Groups[1].Value } else { $n }) }
}

# The sha256 of a text file as git commits it (LF): a script written with CRLF would otherwise get a hash that no
# checkout of it ever matches.
function Get-CommittedSha256([string]$File) {
  $latin1 = [Text.Encoding]::GetEncoding(28591)   # one character per byte, so the bytes come back unchanged
  $bytes = $latin1.GetBytes($latin1.GetString([IO.File]::ReadAllBytes($File)).Replace("`r`n", "`n"))
  return -join ([Security.Cryptography.SHA256]::Create().ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') })
}

# Append a row and return its id. $P holds what the operation did; $Source is the script that did it (project-relative)
# and its sha256, nulls for work done without a script.
function Add-Row([string]$RowOp, [string]$RowTarget, $P, [string]$RowReason, [string]$RowStatus = 'observed', [string]$SourceScript = '', [string]$SourceSha = '', [string]$RowDirection = '') {
  $last = Get-LastRow
  $id = '{0}-{1:D5}' -f $last.prefix, ($last.number + 1)
  $user = ($RowOp -eq 'user.direction')
  if ($null -eq $P) { $P = @{} }
  $row = [ordered]@{
    schema = 'godot-workflow/v0'; id = $id; seq = $last.seq + 1
    time = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffzzz', [Globalization.CultureInfo]::InvariantCulture)
    actor = $(if ($user) { 'user' } else { 'agent' }); op = $RowOp; target = $RowTarget; params = $P
    reason = $RowReason; reason_source = $(if ($user) { 'user_direction' } else { 'agent_note' }); status = $RowStatus
    source = [ordered]@{ script = $(if ($SourceScript) { $SourceScript } else { $null }); sha256 = $(if ($SourceSha) { $SourceSha } else { $null }); commit = $null }
  }
  if ($RowDirection) { $row['direction'] = $RowDirection }
  $json = $row | ConvertTo-Json -Compress -Depth 20
  # Windows PowerShell writes ' < > & as \u0027 \u003c \u003e \u0026: put the characters back (JSON needs no escape for them)
  $json = [regex]::Replace($json, '(?<!\\)((?:\\\\)*)\\u00(27|3c|3e|26)', { param($m) $m.Groups[1].Value + [string][char][Convert]::ToInt32($m.Groups[2].Value, 16) })
  # a file whose last line has no line break (a row appended by hand without one) gets one first: glued to it, this
  # row would make both unreadable
  $lead = ''
  if ((Test-Path -LiteralPath $Workflow) -and (Get-Item -LiteralPath $Workflow).Length -gt 0) {
    $f = New-Object IO.FileStream($Workflow, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
    try { [void]$f.Seek(-1, [IO.SeekOrigin]::End); if ($f.ReadByte() -ne 10) { $lead = "`n" } } finally { $f.Close() }
  }
  # one write of one whole line; another writer may hold the file for a moment
  for ($i = 0; ; $i++) {
    try { [IO.File]::AppendAllText($Workflow, $lead + $json + "`n", $utf8); break }
    catch [IO.IOException] { if ($i -ge 4) { throw }; Start-Sleep -Milliseconds (50 * ($i + 1)) }
  }
  $error1 = ''
  $why = if ($P -is [Collections.IDictionary]) { $P['error'] } else { $P.error }
  if ($RowStatus -ne 'observed' -and $why) { $error1 = ': ' + (([string]$why) -replace '\s+', ' ').Trim() }
  Write-Host "[workflow] $id $RowOp $RowTarget$(if ($RowStatus -ne 'observed') { " ($RowStatus$error1)" })"
  return $id
}

if ($Mode -eq 'row') {
  if ($Op -cnotmatch '^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$') { Write-Error 'pass -Op <area.verb> in lower case, e.g. scene.build, code.edit, asset.import, settings.change, user.direction'; exit 2 }
  if (-not $Target) { Write-Error 'pass -Target <what the operation acted on: a file, a scene, a node, an area>'; exit 2 }
  if ($Direction -and $Direction -cnotmatch '^[a-z]+-[0-9]+$') { Write-Error "-Direction is the id of a user.direction row, e.g. ab-00012 (got '$Direction')"; exit 2 }
  $p = @{}
  if ($Params) {
    $text = $Params
    if ($Params -notmatch '^\s*\{' -and (Test-Path -LiteralPath $Params -PathType Leaf)) { $text = [IO.File]::ReadAllText($Params) }
    try { $p = $text | ConvertFrom-Json -ErrorAction Stop } catch { $p = $null }
    if ($p -isnot [Management.Automation.PSCustomObject]) {
      Write-Error "-Params is not a JSON object: $text (a shell may have taken the quotes: write the object to a file and pass the file's path)"; exit 2
    }
  }
  try { [void](Add-Row $Op $Target $p $Reason $Status '' '' $Direction) } catch { Write-Error $_.Exception.Message; exit 1 }
  exit 0
}

# ---- the machine: the limiter, the engine ------------------------------------------------------------------------------
$Root = if ($env:GGF_ROOT) { $env:GGF_ROOT } else { Split-Path (Split-Path $Proj -Parent) -Parent }
$Heavy = Join-Path $Root 'tools\godot-heavy.ps1'
if (-not (Test-Path $Heavy)) { Write-Error "job limiter not found: $Heavy (run machine/bootstrap.ps1)"; exit 2 }
$Lib = @((Join-Path $Root 'tools\ggf-root.ps1'), (Join-Path $Root 'godot-game-factory\machine\lib\ggf-root.ps1')) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Lib) { Write-Error "ggf-root.ps1 not found in $Root\tools (run machine/bootstrap.ps1)"; exit 2 }
. $Lib
# the editor exe renders (play); its console wrapper waits for the engine and passes its exit code on (headless runs)
$Godot = Get-GGFGodot
if (-not $Godot) { Write-Error 'the Godot editor was not found: run machine/get-godot.ps1 (or set GODOT_EDITOR)'; exit 2 }
$GodotConsole = Get-GGFGodot -Console
$Logs = Join-Path $Proj 'Logs\godot-ps1'
New-Item -ItemType Directory -Force $Logs | Out-Null

function Join-Arguments([string[]]$List) {
  return ($List | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
}
# One job through the limiter; returns its exit code. The limiter runs in a process of its own whose output is read
# and dropped: the engine writes its progress to the console it inherits, and the job's log is the file. Exit code 125
# is the limiter's own (it could not run the job): then what it said is printed.
function Invoke-Heavy([string]$Label, [string[]]$Command, [switch]$Gpu) {
  # the call as PowerShell text, every word a quoted literal, passed encoded so no shell reads its quotes or its "--"
  $call = "& '$($Heavy -replace "'", "''")' -Label '$(("__SLUG__ $Label") -replace "'", "''")'$(if ($Gpu) { ' -Gpu' }) -- " +
    (($Command | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ' ') + '; exit $LASTEXITCODE'
  $psi = New-Object Diagnostics.ProcessStartInfo 'powershell', ('-NoProfile -ExecutionPolicy Bypass -EncodedCommand ' + [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($call)))
  $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
  $p = [Diagnostics.Process]::Start($psi)
  $out = $p.StandardOutput.ReadToEndAsync(); $err = $p.StandardError.ReadToEndAsync()
  $p.WaitForExit()
  if ($p.ExitCode -eq 125) {
    Write-Host 'the job limiter could not run the job (exit code 125):'
    (($out.Result + "`n" + $err.Result) -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 12 | ForEach-Object { Write-Host "  $($_.TrimEnd())" }
  }
  return $p.ExitCode
}
function Invoke-Godot([string]$Label, [string]$Log, [string[]]$More) {
  Remove-Item -LiteralPath $Log -ErrorAction SilentlyContinue   # an engine that never starts must not show an old log
  return (Invoke-Heavy $Label (@($GodotConsole, '--headless', '--path', $Proj, '--log-file', $Log) + $More))
}
# Prints the log's lines that matter and returns how many of them are script errors (the engine ends with exit code 0
# after a script that does not parse).
function Show-Errors([string]$Log, [switch]$Quiet) {
  if (-not (Test-Path $Log)) { Write-Host "no log: $Log"; return 0 }
  $hits = @(Select-String -Path $Log -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script|^\s*ERROR: |^\s+at: .*res://|\[workflow\]')
  if (-not $Quiet) { $hits | Select-Object -Last 40 | ForEach-Object { Write-Host $_.Line.Trim() } }
  return @($hits | Where-Object { $_.Line -match 'SCRIPT ERROR|Parse Error|Failed to load script' }).Count
}
function Get-FirstError([string]$Log) {
  if (-not (Test-Path $Log)) { return 'the engine wrote no log' }
  $m = Select-String -Path $Log -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script|^\s*ERROR: ' | Select-Object -First 1
  if ($m) { return (($m.Line -replace '\x1b\[[0-9;]*m', '').Trim()) }
  return ''
}
function Get-FolderBytes([string]$Dir) {
  if (-not (Test-Path $Dir)) { return 0 }
  return [long](Get-ChildItem -LiteralPath $Dir -Recurse -File | Measure-Object Length -Sum).Sum
}
# Clears a build folder; only a folder under the project's Build/ is ever cleared.
function Reset-BuildFolder([string]$Dir) {
  $full = [IO.Path]::GetFullPath($Dir)
  if ((Test-Path -LiteralPath $full) -and $full.StartsWith([IO.Path]::GetFullPath((Join-Path $Proj 'Build')) + '\', [StringComparison]::OrdinalIgnoreCase)) {
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
  }
  New-Item -ItemType Directory -Force $full | Out-Null
}
# The game's platform and frame size (the one reader of Platform.json: ggf-root.ps1 Get-GGFPlatform).
function Get-Platform {
  try { return (Get-GGFPlatform -Folder $Proj) } catch { Write-Error $_.Exception.Message; exit 2 }
}
# The width and height a PNG file says it has.
function Get-PngSize([string]$File) {
  $f = [IO.File]::OpenRead($File); $h = New-Object byte[] 24
  try { [void]$f.Read($h, 0, 24) } finally { $f.Close() }
  return ('{0}x{1}' -f (([int]$h[16] -shl 24) + ([int]$h[17] -shl 16) + ([int]$h[18] -shl 8) + $h[19]), (([int]$h[20] -shl 24) + ([int]$h[21] -shl 16) + ([int]$h[22] -shl 8) + $h[23]))
}

# `autoplay`: the player on a desktop of its own (WinSta0\AutoPlay), in a job object that ends it, and whatever it
# started, when the wrapper ends; stopped after $limit s (exit code 124). Written into the run's wrapper script.
$DeskRun = @'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class AutoPlayDesk
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct StartupInfo
    {
        public int cb; public string reserved; public string desktop; public string title;
        public int x, y, width, height, xChars, yChars, fill, flags;
        public short show, reserved2; public IntPtr reserved3, stdIn, stdOut, stdErr;
    }
    [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { public IntPtr process, thread; public int pid, tid; }
    [StructLayout(LayoutKind.Sequential)] struct Basic
    {
        public long perProcessTime, perJobTime; public int flags; public UIntPtr minWs, maxWs; public int processes;
        public UIntPtr affinity; public int priority, scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct Extended
    {
        public Basic basic; public ulong r1, r2, w1, w2, o1, o2; public UIntPtr processMemory, jobMemory, peakProcess, peakJob;
    }
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateDesktopW(string name, IntPtr device, IntPtr mode, int flags, uint access, IntPtr attributes);
    [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] static extern IntPtr CreateJobObjectW(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref Extended info, int size);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateProcessW(string app, StringBuilder commandLine, IntPtr pa, IntPtr ta, bool inherit, int flags, IntPtr env, string cwd, ref StartupInfo si, out ProcessInfo pi);
    [DllImport("kernel32.dll", SetLastError = true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")] static extern int ResumeThread(IntPtr thread);
    [DllImport("kernel32.dll")] static extern uint WaitForSingleObject(IntPtr handle, uint ms);
    [DllImport("kernel32.dll")] static extern bool GetExitCodeProcess(IntPtr process, out uint code);
    [DllImport("kernel32.dll")] static extern bool TerminateProcess(IntPtr process, uint code);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);

    public static int Run(string exe, string args, string cwd, string name, int seconds)
    {
        IntPtr desktop = CreateDesktopW(name, IntPtr.Zero, IntPtr.Zero, 0, 0x10000000, IntPtr.Zero);
        if (desktop == IntPtr.Zero) throw new Exception("CreateDesktop failed, error " + Marshal.GetLastWin32Error());
        IntPtr job = CreateJobObjectW(IntPtr.Zero, null);
        try
        {
            Extended limits = new Extended();
            limits.basic.flags = 0x2000;
            if (!SetInformationJobObject(job, 9, ref limits, Marshal.SizeOf(typeof(Extended))))
                throw new Exception("SetInformationJobObject failed, error " + Marshal.GetLastWin32Error());
            StartupInfo si = new StartupInfo();
            si.cb = Marshal.SizeOf(typeof(StartupInfo));
            si.desktop = "WinSta0\\" + name;
            ProcessInfo pi;
            StringBuilder line = new StringBuilder("\"" + exe + "\" " + args);
            if (!CreateProcessW(null, line, IntPtr.Zero, IntPtr.Zero, false, 4, IntPtr.Zero, cwd, ref si, out pi))
                throw new Exception("CreateProcess failed, error " + Marshal.GetLastWin32Error());
            try
            {
                if (!AssignProcessToJobObject(job, pi.process)) { TerminateProcess(pi.process, 1); throw new Exception("AssignProcessToJobObject failed"); }
                ResumeThread(pi.thread);
                if (WaitForSingleObject(pi.process, (uint)seconds * 1000) != 0)
                {
                    TerminateProcess(pi.process, 124);
                    WaitForSingleObject(pi.process, 10000);
                    return 124;
                }
                uint code;
                GetExitCodeProcess(pi.process, out code);
                return unchecked((int)code);
            }
            finally { CloseHandle(pi.thread); CloseHandle(pi.process); }
        }
        finally { CloseHandle(job); CloseDesktop(desktop); }
    }
}
"@
exit ([AutoPlayDesk]::Run($exe, $argLine, (Split-Path $exe), 'AutoPlay', $limit))
'@

# `autoplay`: what the run wrote (docs: the AutoPlay drop-in's files), in a few lines.
function Show-Run([string]$Dir, [int]$Code) {
  Write-Host "run files: $Dir"
  $missing = @('ready.json', 'inputs.jsonl', 'telemetry.jsonl', 'outcome.json', 'clock.json') | Where-Object { -not (Test-Path (Join-Path $Dir $_)) }
  if ($missing) { Write-Host "missing: $($missing -join ', ')" }
  $o = $null
  try { $o = Get-Content -Raw (Join-Path $Dir 'outcome.json') -ErrorAction Stop | ConvertFrom-Json } catch { }
  if ($o) {
    $fps = if ($o.duration_s -gt 0) { $o.frames / $o.duration_s } else { 0 }
    Write-Host ("outcome: {0}, score {1}; {2:N1} s of scenario at {3:N1} fps; {4} inputs injected{5}" -f
      $o.result, $o.score, $o.duration_s, $fps, $o.inputs_injected, $(if ($o.go_timed_out) { '; started without a go file' } else { '' }))
    if ($o.extra -and @($o.extra.PSObject.Properties).Count) { Write-Host "extra: $($o.extra | ConvertTo-Json -Compress -Depth 4)" }
  }
  foreach ($file in 'inputs.jsonl', 'telemetry.jsonl') {
    $p = Join-Path $Dir $file
    if (-not (Test-Path $p)) { continue }
    $kinds = @{}; $errors = @()
    foreach ($l in [IO.File]::ReadLines($p)) {
      if ($l -match '"(?:type|event)":\s*"([^"]+)"') { $kinds[$Matches[1]] = 1 + [int]$kinds[$Matches[1]] }
      if ($l -match '"event":\s*"error".*"message":\s*"((?:[^"\\]|\\.)*)"') { $errors += $Matches[1] }
    }
    Write-Host "${file}: $(($kinds.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')"
    $errors | Select-Object -First 8 | ForEach-Object { Write-Host "  error: $_" }
  }
  $w = Join-Path $Dir 'watchdog.json'
  if (Test-Path $w) { Write-Host "watchdog: $((Get-Content -Raw $w).Trim())" }
  $log = Join-Path $Dir 'game.log'
  if (Test-Path $log) { Select-String -Path $log -Pattern 'AutoPlay: |SCRIPT ERROR|^\s*ERROR: ' | Select-Object -Last 25 | ForEach-Object { $_.Line.Trim() } }
  if ($Code -eq 0) { Write-Host 'the run ended and the player quit' }
  elseif ($Code -eq 124 -and (Test-Path $w)) { Write-Host 'the player hung: its watchdog ended it (watchdog.json)' }
  elseif ($Code -eq 124) { Write-Host "the player was stopped after its time limit (-MaxSeconds + 180 s)" }
  else { Write-Host "the player ended with exit code ${Code}: a crash, or it was killed (read game.log)" }
}

switch ($Mode) {
  'import' {
    $log = Join-Path $Logs 'import.log'
    $code = Invoke-Godot 'import' $log @('--import')
    $bad = Show-Errors $log
    if ($code -eq 0 -and $bad -gt 0) { Write-Host "the import ended, but $bad line(s) of its log are script errors: the project does not compile"; $code = 1 }
    Done $code
  }
  'step' {
    $rel = ($Script -replace '\\', '/') -replace '^(\./|res://)', ''
    if ($rel -notmatch '^steps/[A-Za-z0-9_][A-Za-z0-9_./-]*\.gd$' -or $rel -match '\.\.') { Write-Error 'pass -Script steps/<name>.gd (a generator script under steps/)'; exit 2 }
    $file = Join-Path $Proj ($rel -replace '/', '\')
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Write-Error "no such step: $rel"; exit 2 }
    $sha = Get-CommittedSha256 $file   # the script as it runs: taken before the run
    $name = [IO.Path]::GetFileNameWithoutExtension($rel)
    $log = Join-Path $Logs "step_$name.log"
    $start = Get-Date
    $code = Invoke-Godot "step $name" $log @('--script', "res://$rel")
    # what the step printed (the engine's first line is its version)
    if (Test-Path $log) { Get-Content -LiteralPath $log | Where-Object { $_.Trim() -and $_ -notmatch '^Godot Engine v' } | Select-Object -Last 40 | ForEach-Object { Write-Host $_.TrimEnd() } }
    $bad = Show-Errors $log -Quiet
    if ($code -eq 0 -and $bad -gt 0) { $code = 1 }   # a script error does not change the engine's exit code
    $p = [ordered]@{ exit_code = $code; seconds = [int]((Get-Date) - $start).TotalSeconds }
    if ($code -ne 0) { $p['error'] = Get-FirstError $log }
    [void](Add-Row 'editor.step' $rel $p $Reason $(if ($code -eq 0) { 'observed' } else { 'failed' }) $rel $sha)
    Done $code
  }
  'build' {
    if ($Android -and (Get-Platform).platform -ne 'mobile') { Write-Error '-Android goes with a mobile game (one made with new-game.ps1 -Platform mobile: Platform.json)'; exit 2 }
    $log = Join-Path $Logs 'build.log'
    $out = Join-Path $Proj 'Build\Windows'
    $exe = Join-Path $out '__PROJECT__.exe'
    Reset-BuildFolder $out
    $start = Get-Date
    $code = Invoke-Godot 'build' $log @('--export-release', 'Windows Desktop', $exe)
    [void](Show-Errors $log)
    $ok = ($code -eq 0 -and (Test-Path -LiteralPath $exe))
    if (-not $ok -and $code -eq 0) { $code = 1 }
    $p = [ordered]@{
      result = $(if ($ok) { 'Succeeded' } else { 'Failed' }); configuration = 'release'; preset = 'Windows Desktop'
      seconds = [int]((Get-Date) - $start).TotalSeconds; bytes = (Get-FolderBytes $out)
    }
    if (-not $ok) { $p['error'] = Get-FirstError $log }
    if ($Android -and $ok) {
      $apkRel = 'Build/Android/__PROJECT__.apk'
      $toolchain = Set-GGFAndroidEnv   # JAVA_HOME, ANDROID_HOME, GRADLE_USER_HOME and the keystores, for this run only
      if (-not $toolchain) {
        $why = 'this machine has no Android toolchain (missing: ' + ((@(Get-GGFAndroidParts | Where-Object { -not $_.present } | ForEach-Object { $_.name })) -join ', ') + '; machine\get-android.ps1 installs it)'
        Write-Host "APK skipped: $why. The Windows build is the result."
        $p['android'] = [ordered]@{ status = 'skipped'; reason = $why }
      } else {
        $logA = Join-Path $Logs 'build_android.log'
        $outA = Join-Path $Proj 'Build\Android'
        $apk = Join-Path $outA '__PROJECT__.apk'
        Reset-BuildFolder $outA
        $more = @('--export-release', 'Android', $apk)
        # The Gradle build template (android/build/, git-ignored) comes from the export templates' android_source.zip
        # and carries the engine version it was made from (android/.build_version): install it when it is missing or
        # another version's.
        $engine = if ("$(& $GodotConsole --version 2>$null)" -match '^(\d+(\.\d+)+\.[a-z]+\d*)') { $Matches[1] } else { '' }
        $versionFile = Join-Path $Proj 'android\.build_version'
        $installed = if (Test-Path -LiteralPath $versionFile) { ([IO.File]::ReadAllText($versionFile)).Trim() } else { '' }
        if (-not (Test-Path -LiteralPath (Join-Path $Proj 'android\build\build.gradle')) -or $installed -ne $engine) {
          Remove-Item -LiteralPath (Join-Path $Proj 'android\build') -Recurse -Force -ErrorAction SilentlyContinue
          $more = @('--install-android-build-template') + $more
        }
        $startA = Get-Date
        $codeA = Invoke-Godot 'build android' $logA $more
        [void](Show-Errors $logA)
        $okA = ($codeA -eq 0 -and (Test-Path -LiteralPath $apk))
        if ($okA) {
          $p['android'] = [ordered]@{ status = 'ok'; apk = $apkRel; bytes = (Get-Item -LiteralPath $apk).Length; seconds = [int]((Get-Date) - $startA).TotalSeconds }
          Write-Host "APK: $apkRel"
        } else {
          $why = Get-FirstError $logA
          $p['android'] = [ordered]@{ status = 'failed'; reason = $why; seconds = [int]((Get-Date) - $startA).TotalSeconds }
          $p['result'] = 'Failed'; $p['error'] = "the APK was not built: $why (Logs/godot-ps1/build_android.log)"
          Write-Host $p['error']
          $ok = $false; $code = $(if ($codeA -ne 0) { $codeA } else { 1 })
        }
      }
    }
    [void](Add-Row 'build.player' 'Build/Windows/__PROJECT__.exe' $p $Reason $(if ($ok) { 'observed' } else { 'failed' }))
    Done $code
  }
  'play' {
    if ($Seconds -lt 1) { Write-Error 'pass -Seconds 1 or more'; exit 2 }
    $size = Get-Platform
    $log = Join-Path $Logs "play_$Tag.log"
    Remove-Item -LiteralPath $log -ErrorAction SilentlyContinue   # a game that never starts must not show an old log
    $a = @('--path', $Proj, '--log-file', $log, '--', '-size', "$($size.width)x$($size.height)")
    if ($Scenario -gt 0) { $a += @('-scenario', "$Scenario") }
    $limit = $Seconds
    $shotDir = Join-Path $Logs $Tag
    if ($Shots -gt 0) {
      New-Item -ItemType Directory -Force $shotDir | Out-Null
      Get-ChildItem -LiteralPath $shotDir -Filter *.png | Remove-Item -Force   # an earlier run's frames would pass for this run's
      $a += @('-shots', "$Shots", '-shotDir', $shotDir, '-seconds', "$Seconds")
      $limit = $Seconds + 90   # the game quits by itself after the last frame; the limit is a backstop, counted from its start
    }
    $a += ($Extra -split ' ' | Where-Object { $_ })
    # a game runs until it quits: a small wrapper stops it after the limit, so the slot is always released. The limit
    # counts from the game's start. Process.Start, not Start-Process: Start-Process splits an argument holding a space
    # (a project under a user folder named "First Last") and loses the exit code of a game that ends before the wait starts.
    $wrap = Join-Path $Logs "play_$Tag.ps1"
    # with a BOM: Windows PowerShell reads a script without one as ANSI, and the paths may hold any letter
    [IO.File]::WriteAllText($wrap, @"
`$psi = New-Object Diagnostics.ProcessStartInfo '$($Godot -replace "'", "''")', '$((Join-Arguments $a) -replace "'", "''")'
`$psi.UseShellExecute = `$false
`$psi.WorkingDirectory = '$($Proj -replace "'", "''")'
`$p = [Diagnostics.Process]::Start(`$psi)
if (-not `$p.WaitForExit($limit * 1000)) { & taskkill /PID `$p.Id /T /F *> `$null; exit 124 }
exit `$p.ExitCode
"@, (New-Object Text.UTF8Encoding($true)))
    # the limiter sees powershell, not the engine: -Gpu claims the GPU slot for a rendered run
    $code = Invoke-Heavy "play $Tag" @('powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $wrap) -Gpu
    [void](Show-Errors $log)
    if ($Shots -gt 0) {
      $frames = @(Get-ChildItem -LiteralPath $shotDir -Filter *.png | Sort-Object Name)
      $sizes = @($frames | ForEach-Object { Get-PngSize $_.FullName } | Select-Object -Unique)
      Write-Host "shots: $($frames.Count) of $Shots in $shotDir$(if ($frames.Count) { " ($($sizes -join ', '))" })"
      if ($code -eq 0 -and $frames.Count -lt $Shots) { $code = 1 }
    }
    if ($code -eq 124 -and $Shots -gt 0) { Write-Host "stopped after $limit s: the game did not quit after its last frame" }
    elseif ($code -eq 124) { Write-Host "stopped after $Seconds s (the game did not quit by itself: the timeout, not a crash)" }
    Done $code
  }
  'autoplay' {
    $exe = Join-Path $Proj 'Build\Windows\__PROJECT__.exe'
    if (-not (Test-Path $exe)) { Write-Error "no player build at $exe (run: godot.ps1 build)"; exit 2 }
    if ($MaxSeconds -lt 1) { Write-Error 'pass -MaxSeconds 1 or more'; exit 2 }
    $size = Get-Platform
    $n = if ($Scenario -gt 0) { $Scenario } else { 1 }
    $out = Join-Path $Proj ('Logs\autoplay\{0}_s{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $n)
    New-Item -ItemType Directory -Force $out | Out-Null
    $a = @('--log-file', (Join-Path $out 'game.log'), '--', '-autoplay', '-scenario', "$n", '-seed', "$Seed",
      '-skill', $Skill.ToString([Globalization.CultureInfo]::InvariantCulture), '-maxSeconds', "$MaxSeconds", '-goTimeout', '0',
      '-outputDir', $out, '-size', "$($size.width)x$($size.height)")
    if (-not $Audible) { $a += '-autoplayMute' }
    $a += ($Extra -split ' ' | Where-Object { $_ })
    # the player stops itself (the run's end, or its watchdog after -MaxSeconds); the wrapper's limit is a backstop
    $wrap = Join-Path $Logs "autoplay_$Tag.ps1"
    # with a BOM: Windows PowerShell reads a script without one as ANSI, and the paths may hold any letter
    [IO.File]::WriteAllText($wrap, "`$exe = '$($exe -replace "'", "''")'`n`$argLine = '$((Join-Arguments $a) -replace "'", "''")'`n`$limit = $($MaxSeconds + 180)`n" + $DeskRun, (New-Object Text.UTF8Encoding($true)))
    $code = Invoke-Heavy "autoplay $Tag" @('powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $wrap) -Gpu
    Show-Run $out $code
    Done $code
  }
  default { Write-Error 'pass a mode: import, step, row, build, play or autoplay (the top of this file lists them)'; exit 2 }
}
