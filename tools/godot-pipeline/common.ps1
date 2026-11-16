# Shared helpers for build.ps1 / record.ps1 / pipeline.ps1 and the run tools. Dot-source it. Windows PowerShell 5.1
# compatible.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

# Machine root (GGF_ROOT env, else the config file, else %USERPROFILE%\GodotWork): see machine/lib/ggf-root.ps1.
. (Join-Path $PSScriptRoot '..\..\machine\lib\ggf-root.ps1')
$script:GGFConfig      = Get-GGFConfig
$script:WorkRoot       = $GGFConfig.root
$script:GamesRoot      = Join-Path $WorkRoot 'games'
$script:BuildsRoot     = Join-Path $WorkRoot 'builds'
$script:RecordingsRoot = Join-Path $WorkRoot 'recordings'
$script:LogRoot        = Join-Path $WorkRoot '.recording'
# Private build clones: <ggb>\src\<slug> (default <root>\_build). A Godot export compiles no path into the player, so
# the clone may sit under the user's folder; the leak scan proves it for every build.
$script:SrcRoot        = Join-Path $GGFConfig.ggb 'src'
$script:RepoRoot       = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
# The job limiter every heavy job goes through: this checkout's copy (it finds ggf-root.ps1 in ..\lib), so the pipeline
# and the limiter it calls are always the same version; the installed <root>\tools copy takes the same machine-wide slots.
$script:Heavy          = Join-Path $RepoRoot 'machine\tools\godot-heavy.ps1'
# A game window on a Windows desktop of its own (the task check's launcher): a recorded run shows nothing on the screen.
$script:Desk           = Join-Path $RepoRoot 'tools\task_check\desk.py'
# The user name as it leaks: inside paths (C:\Users\<name>\...). A bare-name search also hits unrelated strings that
# merely contain it.
$script:UserNamePatterns = @("\$($env:USERNAME)\", "/$($env:USERNAME)/")
# Names that must not be in shipped files (warned about by build.ps1; the packager blocks on them).
$script:ForbiddenNamePatterns = @('superposition', 'game-factory', 'game_factory', 'gamefactory', 'game factory', 'claude', 'anthropic', 'openai')
$script:Utf8NoBom      = New-Object System.Text.UTF8Encoding $false
$script:Inv            = [Globalization.CultureInfo]::InvariantCulture
# Every video of the factory is 60 frames a second: what the engine steps when it writes a movie.
$script:MovieFps       = 60

function Write-Step([string]$Message) {
    Write-Host ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message)
}

function Get-IsoNow { (Get-Date).ToString('o') }

function Add-JsonLine([string]$Path, $Object) {
    $dir = Split-Path $Path -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
    $line = ($Object | ConvertTo-Json -Compress -Depth 12) + "`n"
    [System.IO.File]::AppendAllText($Path, $line, $Utf8NoBom)
}

function Write-JsonFile([string]$Path, $Object) {
    [System.IO.File]::WriteAllText($Path, ($Object | ConvertTo-Json -Depth 12) + "`n", $Utf8NoBom)
}

function Read-JsonFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    return [System.IO.File]::ReadAllText($Path, $Utf8NoBom) | ConvertFrom-Json
}

# A property of a parsed JSON object (or a dictionary), $null when it has none: strict mode refuses a missing property.
function Get-Prop($Obj, [string]$Name) {
    if ($null -eq $Obj) { return $null }
    if ($Obj -is [System.Collections.IDictionary]) { if ($Obj.Contains($Name)) { return $Obj[$Name] } else { return $null } }
    if ($Obj.PSObject.Properties.Name -contains $Name) { return $Obj.$Name } else { return $null }
}

# ---- one build or recording of a game at a time ---------------------------------------------------------------------
# An exclusively opened lock file: the OS releases it if the process dies, and it works across sessions
# (Task Scheduler, other terminals). Holder details are in _pipeline-<game>.lock.json.

$script:LockStream = $null
$script:HeldLockPath = $null

# Per-game lock: a build and a recording of the same game share its clone and its build folder, so they exclude each
# other; different games only share the machine, which godot-heavy's slots already ration.
function Enter-PipelineLock([string]$Job, [string]$Game, [int]$TimeoutMinutes = 720) {
    if (-not (Test-Path $BuildsRoot)) { New-Item -ItemType Directory -Force $BuildsRoot | Out-Null }
    $lockPath = Join-Path $BuildsRoot "_pipeline-$Game.lock"
    $script:HeldLockPath = $lockPath
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $announced = $false
    while ($true) {
        try {
            $script:LockStream = [System.IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
            Write-JsonFile "$lockPath.json" ([ordered]@{ pid = $PID; job = $Job; since = (Get-IsoNow); host = $env:COMPUTERNAME })
            return
        } catch [System.IO.IOException] {
            if (-not $announced) {
                $holder = $null; try { $holder = Read-JsonFile "$lockPath.json" } catch { }
                Write-Step "waiting for the $Game pipeline lock (held by: $(if ($holder) { "$($holder.job), pid $($holder.pid), since $($holder.since)" } else { 'unknown' }))"
                $announced = $true
            }
            if ((Get-Date) -gt $deadline) { throw "timed out waiting for the pipeline lock $lockPath" }
            Start-Sleep -Seconds 5
        }
    }
}

function Exit-PipelineLock {
    if ($script:LockStream) {
        $script:LockStream.Dispose()
        $script:LockStream = $null
        Remove-Item "$($script:HeldLockPath).json" -ErrorAction SilentlyContinue
    }
}

# ---- games ----------------------------------------------------------------------------------------------------------

function Get-GameInfo([string]$Game) {
    $dir = Join-Path $GamesRoot $Game
    if (-not (Test-Path $dir)) { throw "no game directory $dir" }
    if (-not (Test-Path (Join-Path $dir 'project.godot'))) { throw "$dir is not a Godot project (no project.godot)" }
    return [pscustomobject]@{ Slug = $Game; Dir = $dir; ProjectName = (Get-ProjectName $dir $Game); LogDir = (Join-Path $LogRoot $Game) }
}

# The project's name, <Project> of <Project>.exe: the file name of the "Windows Desktop" export preset's export_path
# (the template writes Build/Windows/<Project>.exe there), else the slug in PascalCase, as new-game.ps1 names a project.
function Get-ProjectName([string]$ProjectDir, [string]$Slug) {
    $presets = Join-Path $ProjectDir 'export_presets.cfg'
    if (Test-Path -LiteralPath $presets) {
        $inWindows = $false
        foreach ($l in [IO.File]::ReadAllLines($presets)) {
            if ($l -match '^\s*\[preset\.\d+\]\s*$') { $inWindows = $false }
            elseif ($l -match '^\s*name\s*=\s*"Windows Desktop"\s*$') { $inWindows = $true }
            elseif ($inWindows -and $l -match '^\s*export_path\s*=\s*"(?:[^"]*[\\/])?([A-Za-z_][\w-]*)\.exe"\s*$') { return $Matches[1] }
        }
    }
    return (-join ($Slug -split '[-_\s]+' | Where-Object { $_ } | ForEach-Object { $_.Substring(0, 1).ToUpperInvariant() + $_.Substring(1) }))
}

# Whether a project's export_presets.cfg has a preset of this name.
function Test-ExportPreset([string]$ProjectDir, [string]$Name) {
    $presets = Join-Path $ProjectDir 'export_presets.cfg'
    if (-not (Test-Path -LiteralPath $presets)) { return $false }
    return [bool](Select-String -LiteralPath $presets -Pattern ('^\s*name\s*=\s*"' + [regex]::Escape($Name) + '"\s*$') -Quiet)
}

# Which AutoPlay drop-in a project ships: the VERSION constant of its addons\autoplay\autoplay.gd; $null when it has none.
function Get-AutoPlayVersion([string]$ProjectDir) {
    $f = Join-Path $ProjectDir 'addons\autoplay\autoplay.gd'
    if (-not (Test-Path -LiteralPath $f)) { return $null }
    if ([IO.File]::ReadAllText($f) -match '(?m)^const\s+VERSION\s*(?::\s*int\s*)?:?=\s*(\d+)') { return [int]$Matches[1] }
    return $null
}

function Invoke-Git([string]$Dir, [string[]]$GitArgs, [switch]$AllowFail) {
    # PowerShell 5.1 turns native stderr into terminating errors under 'Stop'; run git under 'Continue'.
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & git -C $Dir @GitArgs 2>&1 | ForEach-Object { "$_" }
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $eap }
    if ($code -ne 0 -and -not $AllowFail) { throw "git $($GitArgs -join ' ') failed in ${Dir}: $($out -join ' ')" }
    return $out
}

# Where a repository keeps its Git LFS objects: its lfs.storage, else <git common dir>\lfs\objects.
function Get-LfsStore([string]$Repo) {
    $storage = "$(Invoke-Git $Repo @('config', '--get', 'lfs.storage') -AllowFail)".Trim()   # empty when unset
    $common = "$(Invoke-Git $Repo @('rev-parse', '--git-common-dir'))".Trim()
    if (-not [IO.Path]::IsPathRooted($common)) { $common = Join-Path $Repo $common }
    if ($storage) {
        $base = if ([IO.Path]::IsPathRooted($storage)) { $storage } else { Join-Path $common $storage }
        if (Test-Path -LiteralPath (Join-Path $base 'objects')) { return (Join-Path $base 'objects') }
        return $base
    }
    return (Join-Path $common 'lfs\objects')
}

# ---- processes ------------------------------------------------------------------------------------------------------

# A command line as Windows programs read it (the limiter quotes the same way): an argument with a space or a quote in
# quotes, backslashes before a quote doubled.
function Format-CommandLine([string[]]$Command) {
    ($Command | ForEach-Object {
        $a = [string]$_
        if ($a -and $a -notmatch '[\s"]') { $a } else { '"' + (($a -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"' }
    }) -join ' '
}

# One job through the machine-wide limiter (godot-heavy.ps1: a general slot, and a GPU slot as well for a job that
# renders), the way every game's Scripts/godot.ps1 runs the engine. The limiter runs in a PowerShell of its own, so
# the job can be watched and ended from here; what it and the job print goes to -Log. Returns the started process; its
# exit code is the job's (125: the limiter could not run it).
function Start-Heavy([string]$Label, [string[]]$Command, [string]$Log, [switch]$Gpu) {
    $q = { param($s) "'" + ([string]$s -replace "'", "''") + "'" }
    $call = "`$ProgressPreference = 'SilentlyContinue'; & $(& $q $Heavy) -Label $(& $q $Label) $(if ($Gpu) { '-Gpu ' })-- " + (($Command | ForEach-Object { & $q $_ }) -join ' ') + " *>&1 | ForEach-Object { `"`$_`" }; exit `$LASTEXITCODE"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($call))
    $psi = New-Object Diagnostics.ProcessStartInfo 'cmd.exe'
    $psi.Arguments = "/d /s /c `"powershell.exe -NoProfile -ExecutionPolicy Bypass -OutputFormat Text -EncodedCommand $encoded > `"$Log`" 2>&1`""
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    return [Diagnostics.Process]::Start($psi)
}

# Wait for a job started with Start-Heavy: its exit code, or $null when it was still running after -TimeoutSeconds
# (0: no limit) and was ended with everything it started.
function Wait-Heavy($Process, [int]$TimeoutSeconds = 0) {
    if ($TimeoutSeconds -gt 0) {
        if (-not $Process.WaitForExit($TimeoutSeconds * 1000)) { Stop-Heavy $Process; return $null }
    } else { $Process.WaitForExit() }
    return $Process.ExitCode
}

# End a job and every process it started (the limiter, the launcher, the engine).
function Stop-Heavy($Process) {
    if ($Process.HasExited) { return }
    $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & taskkill.exe /T /F /PID $Process.Id 2>&1 | Out-Null } catch { } finally { $ErrorActionPreference = $eap }
    [void]$Process.WaitForExit(10000)
}

# One job through the limiter, waited for: its exit code (125: the limiter could not run it; $null: ended at the timeout).
function Invoke-Heavy([string]$Label, [string[]]$Command, [string]$Log, [switch]$Gpu, [int]$TimeoutSeconds = 0) {
    return (Wait-Heavy (Start-Heavy $Label $Command $Log -Gpu:$Gpu) $TimeoutSeconds)
}

# The first lines of a failed engine log that say why (script errors, a failed export), else its last 15 lines.
function Get-ErrorExcerpt([string]$LogPath, [int]$MaxLines = 25) {
    if (-not (Test-Path $LogPath)) { return '' }
    $pattern = '(SCRIPT ERROR|Parse Error|Failed to load script|^\s*ERROR:|export template|Cannot export|Project export for preset .* failed|BUILD FAILED|FAILURE: Build failed|Unhandled exception)'
    $lines = @(Select-String -Path $LogPath -Pattern $pattern -CaseSensitive:$false | Select-Object -First $MaxLines | ForEach-Object { $_.Line.Trim() })
    if ($lines.Count -eq 0) { $lines = @(Get-Content $LogPath -Tail 15) }
    $text = ($lines -join "`n")
    if ($text.Length -gt 4000) { $text = $text.Substring(0, 4000) }
    return $text
}

# The lines of an engine log that mean the project's scripts do not load.
function Get-ScriptErrors([string]$LogPath) {
    if (-not (Test-Path $LogPath)) { return @() }
    return @(Select-String -Path $LogPath -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script' | Select-Object -First 10 | ForEach-Object { $_.Line.Trim() })
}

function Set-BelowNormalPriority {
    try { (Get-Process -Id $PID).PriorityClass = 'BelowNormal' } catch { }
}

function Find-FFmpeg {
    # Order (ggf-root.ps1 Get-GGFFfmpeg): $env:GGF_FFMPEG, "ffmpeg" in the config, the pinned copy in <root>\tools
    # (machine/get-ffmpeg.ps1), PATH; then the winget package.
    $ff = Get-GGFFfmpeg $GGFConfig
    if ($ff) { return $ff }
    $pkg = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    $hit = Get-ChildItem $pkg -Directory -Filter 'Gyan.FFmpeg*' -ErrorAction SilentlyContinue |
        ForEach-Object { Get-ChildItem $_.FullName -Recurse -Filter ffmpeg.exe -File } | Select-Object -First 1
    if ($hit) { return $hit.FullName }
    throw "ffmpeg not found: run machine\get-ffmpeg.ps1 (the pinned copy into $WorkRoot\tools)"
}

function Find-FFprobe {
    $ff = Find-FFmpeg
    $probe = Join-Path (Split-Path $ff) 'ffprobe.exe'
    if (Test-Path $probe) { return $probe }
    throw "ffprobe not found next to $ff"
}

function Get-FileSha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Invoke-Native([string]$Exe, [string[]]$NativeArgs) {
    # Runs a native tool capturing stdout only; stderr is discarded without tripping ErrorActionPreference=Stop.
    $eap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { return (& $Exe @NativeArgs 2>$null) } finally { $ErrorActionPreference = $eap }
}

# ffmpeg run to its end with its stderr captured (CPU only, below-normal priority): @{ code; error }.
function Invoke-FFmpeg([string[]]$FFArgs) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = (Find-FFmpeg); $psi.Arguments = (Format-CommandLine $FFArgs)
    $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true; $psi.RedirectStandardError = $true
    $p = [System.Diagnostics.Process]::Start($psi)
    try { $p.PriorityClass = 'BelowNormal' } catch { }
    $err = $p.StandardError.ReadToEnd(); $p.WaitForExit()
    return [pscustomobject]@{ code = $p.ExitCode; error = $err.Trim() }
}

# What ffprobe says of a file: its streams (codec, size, frame rate, counted packets) and duration; $null when it reads
# nothing.
function Get-MediaInfo([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $text = (Invoke-Native (Find-FFprobe) @('-v', 'error', '-count_packets', '-show_entries',
            'stream=codec_type,codec_name,profile,pix_fmt,width,height,avg_frame_rate,nb_read_packets,sample_rate,channels:format=duration', '-of', 'json', $Path)) -join "`n"
    if (-not $text.Trim()) { return $null }
    $j = $text | ConvertFrom-Json
    if (-not $j -or $j.PSObject.Properties.Name -notcontains 'streams' -or @($j.streams).Count -eq 0) { return $null }
    $v = @($j.streams | Where-Object { $_.codec_type -eq 'video' }) | Select-Object -First 1
    $a = @($j.streams | Where-Object { $_.codec_type -eq 'audio' }) | Select-Object -First 1
    $dur = 0.0
    [void][double]::TryParse("$(Get-Prop (Get-Prop $j 'format') 'duration')", [Globalization.NumberStyles]::Float, $Inv, [ref]$dur)
    return [pscustomobject]@{ video = $v; audio = $a; duration_s = $dur; frames = $(if ($v) { [int]$v.nb_read_packets } else { 0 }) }
}

# The loudness of a file's sound (ffmpeg volumedetect): @{ mean_volume_db; max_volume_db }, $null for silence.
function Get-AudioVolume([string]$Path) {
    $r = Invoke-FFmpeg @('-hide_banner', '-nostats', '-i', $Path, '-vn', '-af', 'volumedetect', '-f', 'null', '-')
    $vol = [ordered]@{ mean_volume_db = $null; max_volume_db = $null }
    foreach ($k in 'mean', 'max') {
        if ($r.error -match "${k}_volume: (-?[\d\.]+) dB") { $vol["${k}_volume_db"] = [double]::Parse($Matches[1], $Inv) }
    }
    return $vol
}

# The manifest of a bundle: sha256 + bytes of every file in it but manifest.json itself (raw\ and stills\ included).
function Write-BundleManifest([string]$RunDir, [string]$RunId) {
    $files = [ordered]@{}
    foreach ($f in Get-ChildItem -LiteralPath $RunDir -Recurse -File | Where-Object { $_.Name -ne 'manifest.json' } | Sort-Object FullName) {
        $rel = $f.FullName.Substring($RunDir.TrimEnd('\').Length + 1).Replace('\', '/')
        $files[$rel] = [ordered]@{ sha256 = (Get-FileSha256 $f.FullName); bytes = $f.Length }
    }
    Write-JsonFile (Join-Path $RunDir 'manifest.json') ([ordered]@{ schema = 'manifest/v1'; run_id = $RunId; files = $files })
}

# Refresh the manifest entries of these bundle files (relative paths), others untouched; entries under -DropPrefix go
# first (files that were replaced as a set, such as stills/).
function Update-BundleManifest([string]$RunDir, [string[]]$RelPaths, [string]$DropPrefix = '') {
    $manPath = Join-Path $RunDir 'manifest.json'
    $man = Read-JsonFile $manPath
    if (-not $man) { return }
    $files = [ordered]@{}
    foreach ($p in $man.files.PSObject.Properties) { if (-not $DropPrefix -or -not $p.Name.StartsWith($DropPrefix)) { $files[$p.Name] = $p.Value } }
    foreach ($rel in $RelPaths) {
        $f = Get-Item -LiteralPath (Join-Path $RunDir $rel.Replace('/', '\'))
        $files[$rel] = [ordered]@{ sha256 = (Get-FileSha256 $f.FullName); bytes = $f.Length }
    }
    $man.files = $files
    Write-JsonFile $manPath $man
}

# ---- the run's rows -------------------------------------------------------------------------------------------------

# Parses every line of a run's inputs.jsonl or telemetry.jsonl: counts per type or event, lines that are not JSON or
# lack the stamp (t_ns, qpc, frame), t_ns going backwards. $null without the file.
function Read-RunRows([string]$Path, [string]$KindField) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    Add-Type -AssemblyName System.Web.Extensions
    $ser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
    $ser.MaxJsonLength = 64MB
    $r = [ordered]@{ lines = 0; bad_lines = 0; unstamped = 0; non_monotonic = 0; counts = @{} }
    $prev = [long]0
    foreach ($line in [System.IO.File]::ReadLines($Path)) {
        if ($line.Trim() -eq '') { continue }
        $r.lines++
        try { $o = $ser.DeserializeObject($line) } catch { $r.bad_lines++; continue }
        if ($o -isnot [System.Collections.IDictionary]) { $r.bad_lines++; continue }
        if (-not ($o.ContainsKey('t_ns') -and $o.ContainsKey('qpc') -and $o.ContainsKey('frame'))) { $r.unstamped++ }
        else {
            $t = [long]$o['t_ns']
            if ($t -lt $prev) { $r.non_monotonic++ }
            $prev = $t
        }
        $k = "$(if ($o.ContainsKey($KindField)) { $o[$KindField] })"
        if ($r.counts.ContainsKey($k)) { $r.counts[$k]++ } else { $r.counts[$k] = 1 }
    }
    return $r
}

# Per-scenario AutoPlay time limits. Spec: "" (default 600 s for all), "900" (all), "1=300,3=900" (listed scenarios; the
# rest 600, or "*=700" for the rest). Returns a hashtable keyed "1","*".
function ConvertTo-MaxSecondsMap($Spec) {
    $map = @{ '*' = 600 }
    foreach ($part in @("$Spec" -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
        if ($part -match '^\d+$') { $k = '*'; $v = $part }
        elseif ($part -match '^(\d+|\*)\s*=\s*(\d+)$') { $k = $Matches[1]; $v = $Matches[2] }
        else { throw "bad -MaxSeconds part '$part' (use 900 or 1=300,3=900)" }
        $s = [int]$v
        if ($s -lt 30 -or $s -gt 7200) { throw "MaxSeconds $s for scenario $k is outside 30..7200" }
        $map[[string]$k] = $s
    }
    return $map
}
function Get-MaxSeconds($Map, $Scenario) { if ($Map.ContainsKey("$Scenario")) { return [int]$Map["$Scenario"] } else { return [int]$Map['*'] } }

# ---- the video ------------------------------------------------------------------------------------------------------

# The dataset's Gameplay/ file, <run>\gameplay.mp4, from the engine's own movie (<run>\raw\movie.avi: one JPEG frame
# and one block of PCM sound per engine frame): the frames -FirstFrame..-LastFrame (go to the end of the result hold)
# as H.264 yuv420p at 60 fps and the frame's own size, the sound of the same frames as AAC, +faststart. Picture and
# sound are cut at the same frame, so they stay in step to the sample. CPU only, below-normal priority. Never throws:
# errors come back in .error.
function Export-GameplayMp4([string]$RunDir, [int]$FirstFrame, [int]$LastFrame, [int]$Width, [int]$Height) {
    $result = [ordered]@{ file = 'gameplay.mp4'; video = "h264 yuv420p ${Width}x${Height} $MovieFps fps (libx264 crf 18) from raw/movie.avi"; audio = $null
                          audio_offset_s = 0.0; first_frame = $FirstFrame; last_frame = $LastFrame; frames = $null; duration_s = $null; bytes = $null; error = $null }
    $tmp = Join-Path $RunDir 'gameplay.tmp.mp4'
    try {
        $movie = Join-Path $RunDir 'raw\movie.avi'
        $src = Get-MediaInfo $movie
        if (-not $src -or -not $src.video) { throw 'no raw\movie.avi with a video stream' }
        if ($LastFrame -lt $FirstFrame) { throw "no frames to take ($FirstFrame..$LastFrame)" }
        if ($LastFrame -ge $src.frames) { throw "the movie has $($src.frames) frames, the run ends at frame $LastFrame" }
        $want = $LastFrame - $FirstFrame + 1
        $t0 = ($FirstFrame / $MovieFps).ToString('0.000000', $Inv); $t1 = (($LastFrame + 1) / $MovieFps).ToString('0.000000', $Inv)
        # a JPEG is full-range BT.601; the video is limited-range BT.709, tagged so
        $vf = "trim=start_frame=${FirstFrame}:end_frame=$($LastFrame + 1),setpts=PTS-STARTPTS," +
              'scale=in_color_matrix=bt601:in_range=pc:out_color_matrix=bt709:out_range=tv,format=yuv420p'
        $ffArgs = @('-hide_banner', '-loglevel', 'error', '-y', '-i', $movie, '-map', '0:v:0', '-vf', $vf,
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-g', '120', '-r', "$MovieFps", '-fps_mode', 'cfr',
                    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv')
        if ($src.audio) {
            $ffArgs += @('-map', '0:a:0', '-af', "atrim=start=${t0}:end=${t1},asetpts=PTS-STARTPTS", '-c:a', 'aac', '-b:a', '192k', '-ac', '2')
            $result.audio = 'aac 192k stereo from the movie''s own sound, cut at the same frames'
        } else { $ffArgs += @('-an'); $result.audio = 'none (the movie has no sound)' }
        $ffArgs += @('-movflags', '+faststart', $tmp)
        $r = Invoke-FFmpeg $ffArgs
        if ($r.code -ne 0 -or -not (Test-Path $tmp)) { throw "ffmpeg exit $($r.code): $($r.error)" }
        $out = Get-MediaInfo $tmp
        if (-not $out -or -not $out.video) { throw 'ffmpeg wrote no video' }
        $codecs = @($out.video.codec_name) + $(if ($out.audio) { @($out.audio.codec_name) } else { @() })
        $wantCodecs = @('h264') + $(if ($src.audio) { @('aac') } else { @() })
        if (($codecs -join ',') -ne ($wantCodecs -join ',')) { throw "unexpected streams: $($codecs -join ', ')" }
        if ([int]$out.video.width -ne $Width -or [int]$out.video.height -ne $Height) { throw "the video is $($out.video.width)x$($out.video.height), not ${Width}x${Height}" }
        if ($out.frames -ne $want) { throw "the video has $($out.frames) frames, not the run's $want" }
        Move-Item -Force $tmp (Join-Path $RunDir 'gameplay.mp4')
        $result.frames = $out.frames; $result.duration_s = [math]::Round($out.duration_s, 3); $result.bytes = (Get-Item (Join-Path $RunDir 'gameplay.mp4')).Length
    } catch {
        $result.error = $_.Exception.Message
        if (Test-Path $tmp) { Remove-Item -Force $tmp -ErrorAction SilentlyContinue }
    }
    return $result
}

# README screenshots: $Count evenly spaced stills from a run's gameplay.mp4 (CPU decode), at the video's own size, into
# <run>\stills\NN.jpg and recordings\<game>\_stills\<run_id>_NN.jpg. Never throws: errors come back in .error.
function Export-RunStills([string]$RunDir, [string]$RunId, [string]$GameStillsDir, [int]$Count = 8) {
    $result = [ordered]@{ count = 0; files = @(); copied_to = $GameStillsDir; error = $null }
    try {
        $video = Join-Path $RunDir 'gameplay.mp4'
        $info = Get-MediaInfo $video
        if (-not $info -or $info.duration_s -le 0) { throw 'no gameplay.mp4 with a duration' }
        $ff = Find-FFmpeg
        $dir = Join-Path $RunDir 'stills'
        New-Item -ItemType Directory -Force $dir | Out-Null
        New-Item -ItemType Directory -Force $GameStillsDir | Out-Null
        $files = New-Object System.Collections.ArrayList
        for ($i = 1; $i -le $Count; $i++) {
            $t = [math]::Round($info.duration_s * $i / ($Count + 1), 3)
            $out = Join-Path $dir ('{0:D2}.jpg' -f $i)
            $null = Invoke-Native $ff @('-hide_banner', '-loglevel', 'error', '-y', '-ss', $t.ToString($Inv), '-i', $video, '-frames:v', '1', '-q:v', '2', $out)
            if (-not (Test-Path $out) -or (Get-Item $out).Length -eq 0) { throw "ffmpeg wrote no still at $t s" }
            Copy-Item $out (Join-Path $GameStillsDir ('{0}_{1:D2}.jpg' -f $RunId, $i)) -Force
            [void]$files.Add([ordered]@{ file = ('stills/{0:D2}.jpg' -f $i); t_s = $t })
        }
        $result.files = @($files); $result.count = $files.Count
    } catch { $result.error = $_.Exception.Message }
    return $result
}

# ---- the leak scan --------------------------------------------------------------------------------------------------
# Strings that must not ship (the Windows user name inside paths, the names of $ForbiddenNamePatterns): a
# case-insensitive byte search for each pattern in ASCII and UTF-16LE across every file under $Dir. Returns one row per
# file and pattern.
if (-not ('GodotPipeline.ByteScan' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;
namespace GodotPipeline {
    public static class ByteScan {
        // Counts matches of every ASCII pattern (case-insensitive) as 1-byte or 2-byte little-endian chars, in one read
        // of the file. Returns { ascii, utf16 } per pattern; examples[k] is the first match's context.
        public static long[][] CountAll(string path, string[] patterns, out string[] examples) {
            int m = patterns.Length, maxLen = 1;
            byte[][] p = new byte[m][];
            var starts = new System.Collections.Generic.List<int>[256];   // patterns by their first byte
            for (int k = 0; k < m; k++) {
                p[k] = System.Text.Encoding.ASCII.GetBytes(patterns[k].ToLowerInvariant());
                if (p[k].Length == 0) continue;
                maxLen = Math.Max(maxLen, p[k].Length);
                if (starts[p[k][0]] == null) starts[p[k][0]] = new System.Collections.Generic.List<int>();
                starts[p[k][0]].Add(k);
            }
            long[][] counts = new long[m][]; for (int k = 0; k < m; k++) counts[k] = new long[2];
            examples = new string[m];
            int overlap = 2 * maxLen;
            byte[] buf = new byte[(1 << 22) + overlap]; int keep = 0;
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, 1 << 16)) {
                while (true) {
                    int read = fs.Read(buf, keep, buf.Length - keep);
                    int len = keep + read;
                    bool last = read == 0;
                    int limit = last ? len : len - overlap;   // only start matches that fit wholly in this window
                    if (limit < 0) limit = 0;                 // a short read (or a file shorter than the overlap): carry it all over
                    for (int i = 0; i < limit; i++) {
                        var cand = starts[Lower(buf[i])];
                        if (cand == null) continue;
                        foreach (int k in cand) {
                            byte[] q = p[k]; int n = q.Length;
                            if (i + n <= len) {
                                int j = 1; while (j < n && Lower(buf[i + j]) == q[j]) j++;
                                if (j == n) { counts[k][0]++; if (examples[k] == null) examples[k] = Context(buf, i, len); }
                            }
                            if (i + 2 * n <= len) {
                                int j = 0; while (j < n && Lower(buf[i + 2 * j]) == q[j] && buf[i + 2 * j + 1] == 0) j++;
                                if (j == n) { counts[k][1]++; if (examples[k] == null) examples[k] = Context(buf, i, len); }
                            }
                        }
                    }
                    if (last) break;
                    keep = len - limit; Buffer.BlockCopy(buf, limit, buf, 0, keep);
                }
            }
            return counts;
        }
        static byte Lower(byte b) { return (b >= 65 && b <= 90) ? (byte)(b + 32) : b; }
        static string Context(byte[] buf, int i, int len) {
            int s = Math.Max(0, i - 40), e = Math.Min(len, i + 60);
            var sb = new System.Text.StringBuilder();
            for (int j = s; j < e; j++) { byte b = buf[j]; if (b >= 32 && b < 127) sb.Append((char)b); else if (b != 0) sb.Append('.'); }
            return sb.ToString();
        }
    }
}
'@
}
function Find-LeakedStrings([string]$Dir, [string[]]$Patterns) {
    $Patterns = @($Patterns | Where-Object { $_ })
    if (-not $Patterns) { return }
    foreach ($f in @(Get-ChildItem -LiteralPath $Dir -Recurse -File -ErrorAction SilentlyContinue)) {
        $ex = $null
        $c = [GodotPipeline.ByteScan]::CountAll($f.FullName, [string[]]$Patterns, [ref]$ex)
        for ($k = 0; $k -lt $Patterns.Count; $k++) {
            if ($c[$k][0] + $c[$k][1] -gt 0) {
                [pscustomobject]@{ file = $f.FullName.Substring($Dir.TrimEnd('\').Length + 1); pattern = $Patterns[$k]; count = $c[$k][0] + $c[$k][1]; ascii = $c[$k][0]; utf16 = $c[$k][1]; example = $ex[$k] }
            }
        }
    }
}
