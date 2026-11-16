<#
.SYNOPSIS
  Record AutoPlay runs of a game's release player: start it in the engine's Movie Maker mode with the contract's flags,
  turn the movie into gameplay.mp4, validate, and write one gameplay bundle per run. See docs/godot-pipeline.md and
  docs/autoplay-contract.md.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File record.ps1 harbor-run -Build %GGF_ROOT%\builds\harbor-run\a1b2c3d4 -Scenario 1
  powershell -ExecutionPolicy Bypass -File record.ps1 harbor-run -Build latest -Scenario 2 -Skill 0.5 -Seed 42

  Bundle: recordings\<game>\<run-id>\ gameplay.mp4, inputs.jsonl, telemetry.jsonl, outcome.json, metadata.json,
  validation.json, manifest.json, stills\, raw\ (the game's outputDir, the logs). Failed runs are kept and marked
  (validation.json status "failed", FAILED file). One row per run in .recording\<game>\runs.jsonl.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [Parameter(Mandatory = $true)][string]$Build,
    [int]$Scenario = 1,   # a scenario: start state + win/lose condition (a level, chapter, race stage, start setup)
    [int]$Runs = 1,
    [double]$Skill = -1,
    [long]$Seed = -1,
    [int]$MaxSeconds = 600,   # the run's time limit, in the run's own time (the video's seconds)
    [int]$WallSeconds = 0,    # how long the machine may take to render the run before it is ended; 0: 6 x MaxSeconds + 600
    [string]$ExtraArgs = '',  # more arguments for the game (after the contract's flags; split at spaces)
    [string]$CaptureNote = '',   # what the recording does differently; metadata.json capture_notes, then the dataset's manifest and README
    [switch]$OnScreen,        # show the game's window on this desktop instead of a desktop of its own
    [switch]$KeepMovie        # keep raw\movie.avi (gigabytes) after a good gameplay.mp4
)

. (Join-Path $PSScriptRoot 'common.ps1')

$info = Get-GameInfo $Game
if ($Build -eq 'latest') {
    $Build = (Get-ChildItem (Join-Path $BuildsRoot $Game) -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '_*' -and (Test-Path (Join-Path $_.FullName 'build_info.json')) } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    if (-not $Build) { throw "no release build of $Game under $BuildsRoot\$Game (run build.ps1)" }
}
$buildInfo = Read-JsonFile (Join-Path $Build 'build_info.json')
if (-not $buildInfo -or $buildInfo.status -ne 'ok') { throw "$Build has no build_info.json with status ok (run build.ps1)" }
# The AutoPlay drop-in writes every file a run is checked on: a build without it cannot be recorded (its game would play
# on without ever writing ready.json).
$autoplayVersion = Get-Prop $buildInfo 'autoplay_version'
if ($null -eq $autoplayVersion) { throw "$Build was built from a commit without the AutoPlay drop-in (build_info.json autoplay_version is null): add it to the game (docs/autoplay-contract.md), commit, build again" }
$projectName = [string]$buildInfo.project
$exe = Join-Path $Build "Windows\$projectName.exe"
if (-not (Test-Path -LiteralPath $exe)) { $exe = [string]$buildInfo.exe_path }
if (-not (Test-Path -LiteralPath $exe)) { throw "no player in $Build (expected Windows\$projectName.exe)" }
# The frame of every run: 1920x1080, or the phone's size of a mobile game's build held upright (1080x1920).
$mobile = ((Get-Prop $buildInfo 'platform') -eq 'mobile')
$width, $height = Get-BuildWindow $buildInfo
if ($WallSeconds -le 0) { $WallSeconds = 6 * $MaxSeconds + 600 }

$ffmpeg = Find-FFmpeg
$ffmpegVersion = "$(Invoke-Native $ffmpeg @('-hide_banner', '-version') | Select-Object -First 1)"
$python = Get-GGFPython
if (-not $OnScreen -and (-not $python -or -not (Test-Path -LiteralPath $Desk))) {
    Write-Step "no python or no $Desk for a desktop of its own: the game's window shows on this desktop"
    $OnScreen = $true
}
Write-Step "ffmpeg: $ffmpeg ($ffmpegVersion); frames ${width}x${height}$(if ($mobile) { ' (a mobile game)' })"
$skillCycle = @(1.0, 0.75, 0.5, 0.25)
$rng = New-Object System.Random

$results = New-Object System.Collections.ArrayList
for ($i = 0; $i -lt $Runs; $i++) {
    $runSeed = if ($Seed -ge 0) { $Seed + $i } else { $rng.Next(1, [int]::MaxValue) }
    $runSkill = if ($Skill -ge 0) { $Skill } else { $skillCycle[$i % $skillCycle.Count] }
    $runId = '{0}_S{1}_{2}_s{3}' -f $Game, $Scenario, (Get-Date -Format 'yyyyMMdd-HHmmss'), $runSeed
    $runDir = Join-Path (Join-Path $RecordingsRoot $Game) $runId
    $rawDir = Join-Path $runDir 'raw'
    New-Item -ItemType Directory -Force $rawDir | Out-Null
    $moviePath = Join-Path $rawDir 'movie.avi'
    $problems = New-Object System.Collections.ArrayList
    $warnings = New-Object System.Collections.ArrayList
    $job = $null; $gameExit = $null; $killed = $false; $watchdog = $null; $command = $null
    $tStart = Get-Date

    Enter-PipelineLock "record $Game $runId" -Game $Game
    try {
        Write-Step "run $($i + 1)/$Runs $runId (skill $runSkill, seed $runSeed)"
        # The engine's own arguments, then after "--" the contract's flags (docs/autoplay-contract.md section 1). The
        # movie is every frame the engine renders with the sound it mixes, at 60 frames a second of the run's time.
        $command = @($exe, '--write-movie', $moviePath, '--fixed-fps', "$MovieFps", '--disable-vsync', '--log-file', (Join-Path $rawDir 'game.log'), '--',
                     '-autoplay', '-size', "${width}x${height}", '-scenario', "$Scenario", '-seed', "$runSeed", '-skill', $runSkill.ToString($Inv),
                     '-outputDir', $rawDir, '-maxSeconds', "$MaxSeconds", '-buildCommit', "$($buildInfo.commit)", '-runId', $runId, '-goTimeout', '300') +
                   @($ExtraArgs -split '\s+' | Where-Object { $_ })
        if (-not $OnScreen) { $command = @($python, $Desk) + $command }
        $job = Start-Heavy "record $Game $runId" $command (Join-Path $rawDir 'player.log') -Gpu

        # ---- wait for the game to start (the limiter may hold it for a slot), then for ready.json; then go ----
        $readyPath = Join-Path $rawDir 'ready.json'
        $outcomePath = Join-Path $rawDir 'outcome.json'
        $started = $null; $said = $false; $t0 = Get-Date
        while (-not (Test-Path $readyPath)) {
            if ($job.HasExited) { throw "the game ended (code $($job.ExitCode)) before it was ready" }
            if (-not $started -and ((Test-Path (Join-Path $rawDir 'game.log')) -or (Test-Path $moviePath))) { $started = Get-Date }
            if (-not $started -and -not $said -and ((Get-Date) - $t0).TotalSeconds -gt 15) { Write-Step 'waiting for a GPU slot of the machine'; $said = $true }
            if ($started -and ((Get-Date) - $started).TotalSeconds -gt 180) { throw 'no ready.json within 180 s of the game''s start' }
            Start-Sleep -Milliseconds 200
        }
        [System.IO.File]::WriteAllText((Join-Path $rawDir 'go'), (Get-IsoNow), $Utf8NoBom)
        Write-Step 'ready; go written'

        # ---- wait for the run to end: the game quits by itself after outcome.json and the movie's last frame ----
        if (-not $job.WaitForExit($WallSeconds * 1000)) {
            $killed = $true
            [void]$problems.Add("timeout: the game was still running $WallSeconds s after go and was ended (-MaxSeconds $MaxSeconds of the run's time)")
            Stop-Heavy $job
        }
        $gameExit = $job.ExitCode
        # watchdog.json: the AutoPlay drop-in's exit watchdog ended a game that hung (contract section 3).
        $wdPath = Join-Path $rawDir 'watchdog.json'
        if (Test-Path $wdPath) { try { $watchdog = Read-JsonFile $wdPath } catch { $watchdog = [pscustomobject]@{ reason = 'unreadable' } } }
        if (-not $killed -and $watchdog) { [void]$problems.Add("game ended by the AutoPlay exit watchdog ($(Get-Prop $watchdog 'reason'))") }
        elseif (-not $killed -and $gameExit -ne 0) { [void]$problems.Add("game exit code $gameExit") }
        elseif (-not $killed -and -not (Test-Path $outcomePath)) { [void]$problems.Add('the game quit before writing outcome.json') }
    } catch {
        [void]$problems.Add("run error: $($_.Exception.Message)")
        Write-Step "ERROR: $($_.Exception.Message)"
        if ($job -and -not $job.HasExited) { Stop-Heavy $job; $killed = $true }
    } finally {
        Exit-PipelineLock
    }

    # ---- post-process (CPU work, outside the lock) ----
    $outcome = $null; try { $outcome = Read-JsonFile (Join-Path $rawDir 'outcome.json') } catch { [void]$problems.Add("outcome.json is not JSON: $($_.Exception.Message)") }
    $gameClock = $null; try { $gameClock = Read-JsonFile (Join-Path $rawDir 'clock.json') } catch { }
    foreach ($f in 'inputs.jsonl', 'telemetry.jsonl', 'outcome.json') {
        $src = Join-Path $rawDir $f
        if (Test-Path $src) {
            try { Copy-Item $src (Join-Path $runDir $f) -Force } catch { [void]$problems.Add("could not copy ${f}: $($_.Exception.Message)") }
        } else { [void]$problems.Add("missing $f") }
    }
    if (-not $gameClock) { [void]$problems.Add('missing clock.json') }
    $gs = @{}; if ($gameClock) { foreach ($s in @(Get-Prop $gameClock 'samples')) { if ($s) { $gs[[string]$s.label] = $s } } }

    # The video is the movie's frames from go to the end of the result hold: the game's own go and end clock samples
    # name them (a movie frame is an engine frame, counted from 0).
    $movie = Get-MediaInfo $moviePath
    $gameplayMp4 = $null; $renderFps = $null
    if (-not $movie) { [void]$problems.Add('missing raw\movie.avi (the engine wrote no movie)') }
    elseif (-not ($gs.ContainsKey('go') -and $gs.ContainsKey('end'))) { [void]$problems.Add('no go and end clock samples to cut the movie by') }
    else {
        $first = [int]$gs['go'].frame
        $last = [math]::Min([int]$gs['end'].frame, $movie.frames - 1)
        if ([math]::Abs($movie.frames - ([int]$gs['end'].frame + 1)) -gt 1) { [void]$warnings.Add("the movie has $($movie.frames) frames, the game counted $([int]$gs['end'].frame + 1)") }
        $wall = ([long]$gs['end'].t_ns - [long]$gs['go'].t_ns) / 1e9
        if ($wall -gt 0) { $renderFps = [math]::Round(($last - $first + 1) / $wall, 1) }
        $gameplayMp4 = Export-GameplayMp4 $runDir $first $last $width $height
        if ($gameplayMp4.error) { [void]$problems.Add("gameplay.mp4 not written: $($gameplayMp4.error)") }
        else { Write-Step ("gameplay.mp4: {0:N1} s, {1} frames, rendered at {2} fps" -f $gameplayMp4.duration_s, $gameplayMp4.frames, $renderFps) }
    }

    # ---- validation ----
    $inputs = Read-RunRows (Join-Path $runDir 'inputs.jsonl') 'type'
    $telemetry = Read-RunRows (Join-Path $runDir 'telemetry.jsonl') 'event'
    $checks = [ordered]@{}
    if ($outcome) {
        $result = Get-Prop $outcome 'result'
        $checks.outcome = [ordered]@{ ok = ($result -in @('win', 'lose', 'timeout', 'abort') -and -not (Get-Prop $outcome 'go_timed_out')); result = $result; score = (Get-Prop $outcome 'score'); duration_s = (Get-Prop $outcome 'duration_s') }
        if ($result -notin @('win', 'lose', 'timeout', 'abort')) { [void]$problems.Add("bad outcome.result '$result'") }
        if ($result -eq 'abort') { [void]$warnings.Add('run ended with abort') }
        if (Get-Prop $outcome 'go_timed_out') { [void]$problems.Add('game never saw the go file') }
        # the frame the game rendered, and how
        $vp = @(Get-Prop $outcome 'viewport')
        $frameOk = ($vp.Count -eq 2 -and [int]$vp[0] -eq $width -and [int]$vp[1] -eq $height)
        $rendererOk = (-not $mobile -or (Get-Prop $outcome 'renderer') -eq 'mobile')
        $movieOk = ((Get-Prop $outcome 'movie') -eq $true -and [int](Get-Prop $outcome 'fixed_fps') -eq $MovieFps)
        $checks.frame = [ordered]@{ ok = ($frameOk -and $rendererOk -and $movieOk); viewport = $vp; renderer = (Get-Prop $outcome 'renderer'); movie = (Get-Prop $outcome 'movie'); fixed_fps = (Get-Prop $outcome 'fixed_fps') }
        if (-not $frameOk) { [void]$problems.Add("the game rendered $($vp -join 'x') frames, not ${width}x${height}") }
        if (-not $rendererOk) { [void]$problems.Add("a mobile game ran on the $(Get-Prop $outcome 'renderer') renderer, not the mobile renderer") }
        if (-not $movieOk) { [void]$problems.Add("the game did not run as a $MovieFps fps movie (movie $(Get-Prop $outcome 'movie'), fixed_fps $(Get-Prop $outcome 'fixed_fps'))") }
    } else { [void]$problems.Add('no outcome.json') }
    if ($inputs) {
        $injects = 0; if ($inputs.counts.ContainsKey('inject')) { $injects = $inputs.counts['inject'] }
        $checks.inputs = [ordered]@{ ok = ($injects -gt 0 -and $inputs.bad_lines -eq 0 -and $inputs.unstamped -eq 0 -and $inputs.non_monotonic -eq 0); lines = $inputs.lines; injects = $injects; bad_lines = $inputs.bad_lines; non_monotonic = $inputs.non_monotonic; counts = $inputs.counts }
        if ($injects -eq 0) { [void]$problems.Add('no injected inputs') }
        if ($inputs.bad_lines -gt 0) { [void]$problems.Add("inputs.jsonl has $($inputs.bad_lines) unparseable lines") }
        if ($inputs.unstamped -gt 0) { [void]$problems.Add("inputs.jsonl has $($inputs.unstamped) rows without t_ns, qpc and frame") }
        if ($inputs.non_monotonic -gt 0) { [void]$problems.Add("inputs.jsonl t_ns goes backwards $($inputs.non_monotonic) times") }
    }
    if ($telemetry) {
        $missingEvents = @(@('run_start', 'scenario_start', 'scenario_end', 'run_end') | Where-Object { -not $telemetry.counts.ContainsKey($_) })
        $checks.telemetry = [ordered]@{ ok = ($missingEvents.Count -eq 0 -and $telemetry.bad_lines -eq 0); lines = $telemetry.lines; missing = @($missingEvents); counts = $telemetry.counts }
        foreach ($e in $missingEvents) { [void]$problems.Add("telemetry has no $e") }
        if ($telemetry.bad_lines -gt 0) { [void]$problems.Add("telemetry.jsonl has $($telemetry.bad_lines) unparseable lines") }
    }
    if ($gameplayMp4 -and -not $gameplayMp4.error) {
        $mp4 = Get-MediaInfo (Join-Path $runDir 'gameplay.mp4')
        $checks.video = [ordered]@{
            ok = $true; codec = $mp4.video.codec_name; profile = $mp4.video.profile; pix_fmt = $mp4.video.pix_fmt
            width = [int]$mp4.video.width; height = [int]$mp4.video.height; avg_frame_rate = $mp4.video.avg_frame_rate
            duration_s = $mp4.duration_s; frames = $mp4.frames; first_frame = $gameplayMp4.first_frame; last_frame = $gameplayMp4.last_frame
            movie_frames = $movie.frames; movie_size = "$($movie.video.width)x$($movie.video.height)"; render_fps = $renderFps
        }
        if ([int]$movie.video.width -ne $width -or [int]$movie.video.height -ne $height) {
            # the engine scales a movie's frames to the project's viewport size: one that is not the game's size is a
            # project setting gone wrong (display/window/size/viewport_width and viewport_height)
            $checks.video.ok = $false
            [void]$problems.Add("the engine's movie is $($movie.video.width)x$($movie.video.height), not ${width}x${height}: the project's viewport size is not the game's")
        }
        if ($mp4.video.avg_frame_rate -ne "$MovieFps/1") { $checks.video.ok = $false; [void]$problems.Add("the video's frame rate is $($mp4.video.avg_frame_rate)") }
        if ($mp4.audio) {
            $vol = Get-AudioVolume (Join-Path $runDir 'gameplay.mp4')
            $silent = ($null -eq $vol.max_volume_db) -or ($vol.max_volume_db -lt -60)
            $checks.audio = [ordered]@{ ok = $true; codec = $mp4.audio.codec_name; sample_rate = [int]$mp4.audio.sample_rate; channels = [int]$mp4.audio.channels; silent = $silent; mean_volume_db = $vol.mean_volume_db; max_volume_db = $vol.max_volume_db }
            if ($silent) { [void]$warnings.Add('audio is silent (max volume below -60 dB)') }
        } else { $checks.audio = [ordered]@{ ok = $false }; [void]$problems.Add('the video has no sound track') }
    }
    $checks.process = [ordered]@{ ok = (-not $killed -and $gameExit -eq 0); exit_code = $gameExit; killed = $killed; desktop = $(if ($OnScreen) { 'screen' } else { 'own' }) }
    $checks.watchdog = [ordered]@{ ok = (-not $watchdog); reason = (Get-Prop $watchdog 'reason') }

    $status = if ($problems.Count -gt 0) { 'failed' } elseif ($warnings.Count -gt 0) { 'warn' } else { 'ok' }

    # ---- stills for README screenshots (runs whose video is valid); never changes the run's status ----
    $stills = $null
    if ($status -in @('ok', 'warn')) {
        $stills = Export-RunStills $runDir $runId (Join-Path (Join-Path $RecordingsRoot $Game) '_stills')
        if ($stills.error) { Write-Step "WARNING: stills not extracted: $($stills.error)" } else { Write-Step "$($stills.count) stills -> $runDir\stills" }
    }
    # The movie is the video's source and runs to gigabytes: it goes once the video is good.
    if ($status -in @('ok', 'warn') -and -not $KeepMovie) { Remove-Item -LiteralPath $moviePath -Force -ErrorAction SilentlyContinue }

    # ---- metadata, manifest ----
    $metadata = [ordered]@{
        schema = 'godot-autoplay-bundle/v1'
        run_id = $runId; game = $Game; project = $projectName
        scenario = $Scenario; scenario_name = (Get-Prop $outcome 'scenario_name')
        seed = $runSeed; skill = $runSkill; max_seconds = $MaxSeconds
        extra_args = $(if ($ExtraArgs) { $ExtraArgs } else { $null }); capture_notes = $(if ($CaptureNote) { $CaptureNote } else { $null })
        result = (Get-Prop $outcome 'result'); score = (Get-Prop $outcome 'score')
        player = [ordered]@{ kind = 'bot'; name = 'autoplay'; input_injection = 'Godot InputEvents (Input.parse_input_event)' }
        build = [ordered]@{ commit = $buildInfo.commit; short_sha = $buildInfo.short_sha; config = (Get-Prop $buildInfo 'config'); godot_version = (Get-Prop $buildInfo 'godot_version'); path = $Build; exe = $exe; autoplay_version = $autoplayVersion }
        clock = [ordered]@{
            source = 'the engine''s monotonic clock, microseconds'; qpc_frequency = (Get-Prop $gameClock 'qpc_frequency'); t_ns_definition = 'qpc * 1e9 / qpc_frequency'
            samples = @(@(Get-Prop $gameClock 'samples') | Where-Object { $_ })
        }
        video = [ordered]@{
            file = 'gameplay.mp4'; codec = 'h264'; width = $width; height = $height; fps = $MovieFps; cfr = $true; audio = $true
            capture = 'movie'; source = 'the engine''s Movie Maker mode (--write-movie, MJPEG + PCM), frames go..end'
            first_frame = $(if ($gameplayMp4) { $gameplayMp4.first_frame } else { $null }); last_frame = $(if ($gameplayMp4) { $gameplayMp4.last_frame } else { $null })
            time_definition = 'video_time_s = a row''s t = (frame - first_frame) / fps'
            command = $(if ($command) { Format-CommandLine $command } else { $null }); ffmpeg_version = $ffmpegVersion
        }
        machine = [ordered]@{ cpu = (@(Get-CimInstance Win32_Processor | ForEach-Object { $_.Name.Trim() }) -join '; '); gpu = (@(Get-CimInstance Win32_VideoController | Where-Object { $_.CurrentHorizontalResolution -gt 0 } | ForEach-Object { $_.Name }) -join '; '); os = [Environment]::OSVersion.VersionString }
        created_utc = (Get-Date).ToUniversalTime().ToString('o')
        status = $status
        stills = $stills
        gameplay_mp4 = $gameplayMp4
    }
    Write-JsonFile (Join-Path $runDir 'metadata.json') $metadata
    $validation = [ordered]@{ run_id = $runId; status = $status; problems = @($problems); warnings = @($warnings); checks = $checks; game_exit_code = $gameExit; killed = $killed }
    Write-JsonFile (Join-Path $runDir 'validation.json') $validation
    if ($status -eq 'failed') { [System.IO.File]::WriteAllText((Join-Path $runDir 'FAILED'), (($problems -join "`n") + "`n"), $Utf8NoBom) }
    Write-BundleManifest $runDir $runId

    $tEnd = Get-Date
    $row = [ordered]@{
        schema = 'godot-run/v1'; run_id = $runId; game = $Game; scenario = $Scenario; scenario_name = (Get-Prop $outcome 'scenario_name'); seed = $runSeed; skill = $runSkill
        build_commit = $buildInfo.commit; build_path = $Build; status = $status
        result = $metadata.result; score = $metadata.score; duration_s = (Get-Prop $outcome 'duration_s')
        start = $tStart.ToString('o'); end = $tEnd.ToString('o'); wall_s = [math]::Round(($tEnd - $tStart).TotalSeconds, 1)
        capture = 'movie'; render_fps = $renderFps
        problems = @($problems); warnings = @($warnings); bundle = $runDir
    }
    Add-JsonLine (Join-Path $info.LogDir 'runs.jsonl') $row
    Write-Step ("{0}: {1} ({2}){3}" -f $runId, $status, $metadata.result, $(if ($problems.Count) { ' - ' + ($problems -join '; ') } else { '' }))
    [void]$results.Add($row)
}
$results
if (@($results | Where-Object { $_.status -eq 'failed' }).Count -gt 0) { exit 1 }
