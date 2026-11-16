<#
.SYNOPSIS
  Build one game's Windows release player at a commit, and a mobile game's Android APK too. See docs/godot-pipeline.md.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File build.ps1 harbor-run
  powershell -ExecutionPolicy Bypass -File build.ps1 harbor-run -Commit milestone/autoplay-1

  Builds from a private clone (<ggb>\src\<game>) of the committed tree, never from the game's working copy: the game
  session keeps its half-edited files to itself. Uncommitted changes are not built. The player is the game's own
  "Windows Desktop" export preset, exported with the release template through the machine's job limiter.
  Output: builds\<game>\<short-sha>\Windows\<Project>.exe, for a mobile game Android\<Project>.apk as well when the
  machine has the Android toolchain, build_info.json, logs\. One row per run in .recording\<game>\builds.jsonl. Holds
  the game's pipeline lock (one build or recording of a game at a time).
#>
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Game,
    [string]$Commit = 'HEAD',
    [switch]$Force,
    [switch]$NoAndroid   # a mobile game: leave the APK out (android.status "skipped")
)

. (Join-Path $PSScriptRoot 'common.ps1')

$info = Get-GameInfo $Game
$commandLine = "build.ps1 $Game -Commit $Commit" + $(if ($Force) { ' -Force' } else { '' }) + $(if ($NoAndroid) { ' -NoAndroid' } else { '' })

$sha = (Invoke-Git $info.Dir @('rev-parse', '--verify', "$Commit^{commit}")).Trim()
$short = $sha.Substring(0, 8)
$outDir = Join-Path (Join-Path $BuildsRoot $Game) $short
$logDir = Join-Path $outDir 'logs'
$winDir = Join-Path $outDir 'Windows'
$apkDir = Join-Path $outDir 'Android'
$buildInfoPath = Join-Path $outDir 'build_info.json'

$existing = Read-JsonFile $buildInfoPath
if (-not $Force -and $existing -and $existing.status -eq 'ok' -and (Test-Path -LiteralPath "$($existing.exe_path)")) {
    Write-Step "$Game $short already built ($outDir); use -Force to rebuild"
    return $existing
}

Set-BelowNormalPriority
Enter-PipelineLock "build $Game $short" -Game $Game
$start = Get-Date
$steps = New-Object System.Collections.ArrayList
$failure = ''
$autoplayVersion = $null
$leakScan = $null
$godot = $null
$godotVersion = ''
$projectName = $info.ProjectName
$platform = $null
$android = $null
$playerBytes = $null
$status = 'ok'
$stamp = $start.ToString('yyyyMMdd-HHmmss')

# One headless engine run through the limiter; what it prints is the step's log.
function Invoke-Step([string]$Name, [string[]]$GodotArgs) {
    $log = Join-Path $logDir "$stamp-$Name.log"
    Write-Step "$Name ..."
    $t0 = Get-Date
    $command = @($godot, '--headless') + $GodotArgs
    $code = Invoke-Heavy "pipeline $Game $short $Name" $command $log
    $t1 = Get-Date
    $row = [ordered]@{
        name = $Name; command = (Format-CommandLine $command); start = $t0.ToString('o'); end = $t1.ToString('o')
        duration_s = [math]::Round(($t1 - $t0).TotalSeconds, 1); exit_code = $code; log_path = $log
        error_excerpt = $(if ($code -ne 0) { Get-ErrorExcerpt $log } else { '' })
    }
    [void]$steps.Add($row)
    Write-Step ("{0} exit {1} in {2}s" -f $Name, $code, $row.duration_s)
    return $row
}

# aapt's "dump badging" of an APK: the package name, the SDK levels and the ABIs it holds.
function Read-Apk([string]$Apk, $Toolchain) {
    $aapt = Join-Path $Toolchain.sdk "build-tools\$($Toolchain.build_tools)\aapt.exe"
    if (-not (Test-Path -LiteralPath $aapt)) { throw "no aapt.exe in the SDK's build-tools $($Toolchain.build_tools)" }
    $text = (Invoke-Native $aapt @('dump', 'badging', $Apk)) -join "`n"
    $r = [ordered]@{ package = $null; min_sdk = $null; target_sdk = $null; abis = @() }
    if ($text -match "(?m)^package: name='([^']+)'") { $r.package = $Matches[1] }
    if ($text -match "(?m)^sdkVersion:'(\d+)'") { $r.min_sdk = [int]$Matches[1] }
    if ($text -match "(?m)^targetSdkVersion:'(\d+)'") { $r.target_sdk = [int]$Matches[1] }
    if ($text -match "(?m)^native-code: (.+)$") { $r.abis = @([regex]::Matches($Matches[1], "'([^']+)'") | ForEach-Object { $_.Groups[1].Value }) }
    if (-not $r.package) { throw "aapt read no package name from $Apk" }
    return $r
}

try {
    # a rebuild never leaves an older build_info.json that says ok next to a player that is gone
    Remove-Item -LiteralPath $buildInfoPath -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $logDir | Out-Null

    # ---- source: private clone at the exact commit, LFS files copied from the game's own LFS store ----
    $src = Join-Path $SrcRoot $Game
    $env:GIT_LFS_SKIP_SMUDGE = '1'
    if (-not (Test-Path (Join-Path $src '.git'))) {
        Write-Step "cloning $($info.Dir) -> $src"
        New-Item -ItemType Directory -Force (Split-Path $src) | Out-Null
        # --local hard-links the object files, which fails across volumes: a clone on another drive copies instead
        $cloneArgs = @('clone', '--quiet', '--no-checkout', '--local')
        if ([IO.Path]::GetPathRoot($info.Dir) -ne [IO.Path]::GetPathRoot($src)) { $cloneArgs += '--no-hardlinks' }
        Invoke-Git $WorkRoot ($cloneArgs + @($info.Dir, $src)) | Out-Null
    }
    Invoke-Git $src @('fetch', '--quiet', '--force', '--tags', 'origin', '+refs/heads/*:refs/remotes/origin/*') | Out-Null
    Invoke-Git $src @('-c', 'advice.detachedHead=false', 'checkout', '--quiet', '--force', $sha) | Out-Null
    # .godot\ (the import cache) stays, so later builds import only what changed: kept by name, whatever the game's
    # .gitignore at this commit says.
    Invoke-Git $src @('clean', '-ffdq', '-e', '/.godot/') | Out-Null
    $lfsStore = Get-LfsStore $info.Dir
    $missing = New-Object System.Collections.ArrayList
    $copied = 0
    $lfsList = @(Invoke-Git $src @('-c', 'core.quotepath=false', 'lfs', 'ls-files', '-l') -AllowFail)
    foreach ($line in $lfsList) {
        if ($line.Length -lt 68 -or $line -notmatch '^[0-9a-f]{64} ') { continue }
        $oid = $line.Substring(0, 64); $rel = $line.Substring(67)
        $target = Join-Path $src $rel
        $item = Get-Item -LiteralPath $target -ErrorAction SilentlyContinue
        if ($item -and $item.Length -lt 1024 -and ((Get-Content -LiteralPath $target -TotalCount 1) -like 'version https://git-lfs*')) {
            $obj = Join-Path $lfsStore ("{0}\{1}\{2}" -f $oid.Substring(0, 2), $oid.Substring(2, 2), $oid)
            # a copy, never a hard link: an import that rewrote the file in the clone would change the game's object
            if (Test-Path -LiteralPath $obj) { Copy-Item -LiteralPath $obj -Destination $target -Force; $copied++ }
            else { [void]$missing.Add($rel) }
        }
    }
    Remove-Item Env:\GIT_LFS_SKIP_SMUDGE
    if ($missing.Count -gt 0) { throw "LFS objects missing from $lfsStore for: $($missing -join ', ') (git -C `"$($info.Dir)`" lfs fetch origin $sha)" }
    Write-Step "source at $short in $src ($copied LFS files copied)"

    # The game as the commit has it: its name, its platform, its AutoPlay drop-in (null: none; record.ps1 refuses such
    # a build).
    $projectName = Get-ProjectName $src $Game
    $platform = Get-GGFPlatform -Folder $src
    $autoplayVersion = Get-AutoPlayVersion $src
    if (-not (Test-ExportPreset $src 'Windows Desktop')) { throw "export_presets.cfg at $short has no preset named `"Windows Desktop`"" }
    $godot = Get-GGFGodot -Console -Cfg $GGFConfig -WarningAction SilentlyContinue
    if (-not $godot) { throw "the engine is not installed: run machine\get-godot.ps1" }
    $godotVersion = "$(Invoke-Native $godot @('--version') | Select-Object -First 1)".Trim()
    Write-Step "Godot $godotVersion at $godot; $($platform.platform)$(if ($platform.orientation) { " $($platform.orientation)" }) game -> $projectName.exe; AutoPlay drop-in $(if ($null -ne $autoplayVersion) { "v$autoplayVersion" } else { 'none' })"

    # ---- import: the project's scripts must load ----
    $r = Invoke-Step 'import' @('--path', $src, '--import')
    $scriptErrors = @(Get-ScriptErrors $r.log_path)
    if ($r.exit_code -ne 0 -or $scriptErrors.Count) {
        if ($scriptErrors.Count) { $r.error_excerpt = ($scriptErrors -join "`n"); if ($r.exit_code -eq 0) { $r.exit_code = 1 } }
        throw 'the import failed: the project''s scripts do not load'
    }

    # ---- the Windows release player (a fresh folder) ----
    if (Test-Path -LiteralPath $winDir) { Remove-Item -LiteralPath $winDir -Recurse -Force }
    New-Item -ItemType Directory -Force $winDir | Out-Null
    $exePath = Join-Path $winDir "$projectName.exe"
    $r = Invoke-Step 'player' @('--path', $src, '--export-release', 'Windows Desktop', $exePath)
    if ($r.exit_code -ne 0) { throw 'the Windows export failed' }
    if (-not (Test-Path -LiteralPath $exePath)) { $r.exit_code = 1; $r.error_excerpt = Get-ErrorExcerpt $r.log_path; throw "the export ended without error but $exePath is missing" }
    $playerBytes = (Get-ChildItem -LiteralPath $winDir -Recurse -File | Measure-Object Length -Sum).Sum
    # The recorder starts this player with the engine's own --write-movie: its game data must be inside the exe or in a
    # .pck beside it, as the template's preset (embed_pck) makes it.

    # ---- a mobile game: the Android APK, when this machine can build one ----
    if ($platform.platform -eq 'mobile') {
        $android = [ordered]@{ status = 'skipped'; reason = $null; apk = $null; bytes = $null; package = $null; min_sdk = $null; target_sdk = $null; abis = @() }
        $toolchain = $null
        if ($NoAndroid) { $android.reason = '-NoAndroid' }
        elseif (-not (Test-ExportPreset $src 'Android')) { $android.status = 'failed'; $android.reason = "export_presets.cfg at $short has no preset named `"Android`"" }
        else {
            $toolchain = Set-GGFAndroidEnv $GGFConfig
            if (-not $toolchain) { $android.reason = 'this machine has no Android toolchain (machine\get-android.ps1 installs it)' }
        }
        if ($toolchain) {
            try {
                if (Test-Path -LiteralPath $apkDir) { Remove-Item -LiteralPath $apkDir -Recurse -Force }
                New-Item -ItemType Directory -Force $apkDir | Out-Null
                $apk = Join-Path $apkDir "$projectName.apk"
                # the Gradle build template of this engine version in the clone's android\build (android\.build_version
                # names it); the engine installs it from the export templates' android_source.zip
                $r = Invoke-Step 'android' @('--path', $src, '--install-android-build-template', '--export-release', 'Android', $apk)
                if ($r.exit_code -ne 0 -or -not (Test-Path -LiteralPath $apk)) {
                    if ($r.exit_code -eq 0) { $r.exit_code = 1; $r.error_excerpt = Get-ErrorExcerpt $r.log_path }
                    throw "the Android export failed: $(($r.error_excerpt -split "`n")[0])"
                }
                $read = Read-Apk $apk $toolchain
                $android.apk = $apk; $android.bytes = (Get-Item -LiteralPath $apk).Length
                $android.package = $read.package; $android.min_sdk = $read.min_sdk; $android.target_sdk = $read.target_sdk; $android.abis = @($read.abis)
                $wrong = @()
                $wantPackage = "com.$($projectName.ToLowerInvariant()).game"
                if ($read.package -ne $wantPackage) { $wrong += "package $($read.package), not $wantPackage" }
                if ($read.min_sdk -ne 26) { $wrong += "minSdk $($read.min_sdk), not 26" }
                if ($read.target_sdk -ne 34) { $wrong += "targetSdk $($read.target_sdk), not 34" }
                if ((@($read.abis) -join ',') -ne 'arm64-v8a') { $wrong += "ABIs $(@($read.abis) -join ', '), not arm64-v8a alone" }
                if ($wrong.Count) { $android.status = 'failed'; $android.reason = "the APK is not the Android build of a mobile game: $($wrong -join '; ')" }
                else { $android.status = 'ok' }
            } catch { $android.status = 'failed'; $android.reason = $_.Exception.Message }
        }
        Write-Step "Android: $($android.status)$(if ($android.reason) { " ($($android.reason))" })$(if ($android.status -eq 'ok') { " $($android.package), minSdk $($android.min_sdk), targetSdk $($android.target_sdk), $($android.abis -join ' ')" })"
    }

    # Strings that must not ship: the user name inside paths and $ForbiddenNamePatterns (common.ps1). Recorded and
    # warned about; recording still works, but such a build must not be handed out.
    $scanned = @('Windows\')
    $leakHits = @(Find-LeakedStrings $winDir @($UserNamePatterns + $ForbiddenNamePatterns) | ForEach-Object { $_.file = "Windows\$($_.file)"; $_ })
    if ($android -and $android.status -eq 'ok') {
        $scanned += 'Android\'
        $leakHits += @(Find-LeakedStrings $apkDir @($UserNamePatterns + $ForbiddenNamePatterns) | ForEach-Object { $_.file = "Android\$($_.file)"; $_ })
    }
    $leakScan = [ordered]@{ scanned = ($scanned -join ', '); hits = @($leakHits | ForEach-Object { [ordered]@{ file = $_.file; pattern = $_.pattern; count = $_.count; example = $_.example } }) }
    if ($leakHits.Count) { Write-Step "WARNING: the build's files contain names that must not ship: $(($leakHits | ForEach-Object { "$($_.file) ($($_.pattern) x$($_.count))" }) -join '; ')" }
    else { Write-Step 'leak scan: no user name or forbidden names in the build''s files' }
} catch {
    $status = 'failed'
    $failure = $_.Exception.Message
    Write-Step "FAILED: $failure"
} finally {
    Remove-Item Env:\GIT_LFS_SKIP_SMUDGE -ErrorAction SilentlyContinue
    Exit-PipelineLock
}

$end = Get-Date
$failedStep = $steps | Where-Object { $_.exit_code -ne 0 -and $_.name -ne 'android' } | Select-Object -First 1
$lastStep = $steps | Select-Object -Last 1
$subject = "$(Invoke-Git $info.Dir @('log', '-1', '--format=%s', $sha) -AllowFail)"
$commitTime = "$(Invoke-Git $info.Dir @('log', '-1', '--format=%cI', $sha) -AllowFail)"
$row = [ordered]@{
    schema = 'godot-build/1'   # neutral: build_info.json sits next to the game's player
    game = $Game; project = $projectName
    platform = $(if ($platform) { $platform.platform } else { $null }); orientation = $(if ($platform) { $platform.orientation } else { $null })
    commit = $sha; short_sha = $short; requested = $Commit; commit_subject = $subject; commit_time = $commitTime
    command = $commandLine
    start = $start.ToString('o'); end = $end.ToString('o'); duration_s = [math]::Round(($end - $start).TotalSeconds, 1)
    status = $status
    exit_code = $(if ($failedStep) { $failedStep.exit_code } elseif ($status -eq 'ok') { 0 } else { -1 })
    error_excerpt = $(if ($failedStep) { $failedStep.error_excerpt } elseif ($status -ne 'ok') { $failure } else { '' })
    log_path = $(if ($failedStep) { $failedStep.log_path } elseif ($lastStep) { $lastStep.log_path } else { $null })
    output_path = $(if ($status -eq 'ok') { $outDir } else { $null })
    exe_path = $(if ($status -eq 'ok') { Join-Path $winDir "$projectName.exe" } else { $null })
    config = 'release'
    player_bytes = $playerBytes
    android = $android
    autoplay_version = $autoplayVersion
    leak_scan = $leakScan
    godot_version = $godotVersion
    editor = $godot
    steps = @($steps)
}
Add-JsonLine (Join-Path $info.LogDir 'builds.jsonl') $row
if ($status -eq 'ok') { Write-JsonFile $buildInfoPath $row }   # describes a player that is there
Write-Step ("{0} {1}: {2} in {3}s" -f $Game, $short, $status, $row.duration_s)
$row
if ($status -ne 'ok') { exit 1 }
