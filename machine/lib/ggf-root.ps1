# Machine root for godot-game-factory tooling. Dot-source it; Windows PowerShell 5.1 compatible.
#
# Everything machine-specific hangs off one root (the "GodotWork" folder holding games\, tasks\, builds\, recordings\,
# .recording\, deliverables\, asset-library\, tools\, godot\<version>\, android\ and the godot-game-factory clone).
# Resolution order:
#   1. $env:GGF_ROOT
#   2. "root" in the config file: $env:GGF_CONFIG, else %USERPROFILE%\.godot-game-factory\config.json (bootstrap.ps1 writes it)
#   3. %USERPROFILE%\GodotWork
# The same config file also holds "ggb" (default <root>\_build: the release builds' private clones), "godot" (optional:
# the full path of another editor exe than the pinned one; Get-GGFGodot), "checkout" (the godot-game-factory clone the
# installed copies of this file belong to; Get-GGFCheckout), "record_extra_projects" (top-level folders under the root
# that the recording hooks treat as projects besides games\<slug>), "github_org" (the GitHub organisation or user that
# owns godot-game-factory and the private godot-game-<slug> repos; Get-GGFOrg), "agents" (the coding agents
# bootstrap.ps1 wired up: "claude", "codex", "antigravity"), "hooks_dir" (where the recording hooks live, shared by
# every agent; Get-GGFHooksDir), "ffmpeg" (optional: the full path of an ffmpeg.exe; Get-GGFFfmpeg) and "android" (optional:
# {"home": "<folder>"}, where the Android toolchain is when it is not <root>\android; Get-GGFAndroid). Installed copies
# of the hooks and godot-heavy.ps1 carry a copy of this file next to them (and <root>\tools\ a copy of godot.json).
#
# Other factories may run on the same machine, each with its own root and config (%USERPROFILE%\.game-factory\,
# %USERPROFILE%\.unity-game-factory\). They never share a root, a config or a hooks folder; they share only the
# machine-wide job slots (the mutexes below), and godot-heavy.ps1 also honours the other factories' recording flags and
# reads their job logs (Get-GGFRecordingFlags, Get-GGFJobLogs), so all together never oversubscribe the PC. Nothing of
# another factory is ever written.

function Get-GGFConfigPath {
    if ($env:GGF_CONFIG) { return $env:GGF_CONFIG }
    return (Join-Path $env:USERPROFILE '.godot-game-factory\config.json')
}

function Get-GGFConfig {
    $cfg = [ordered]@{
        root                  = (Join-Path $env:USERPROFILE 'GodotWork')
        ggb                   = ''
        record_extra_projects = @()
    }
    $path = Get-GGFConfigPath
    if (Test-Path -LiteralPath $path) {
        # a path typed with single backslashes is the usual cause: name the file, not just the parser's complaint
        try { $json = [IO.File]::ReadAllText($path) | ConvertFrom-Json }
        catch { throw "$path is not valid JSON ($($_.Exception.Message)): write a Windows path in it with doubled backslashes or forward slashes" }
        foreach ($p in $json.PSObject.Properties) { $cfg[$p.Name] = $p.Value }
    }
    if ($env:GGF_ROOT) { $cfg.root = $env:GGF_ROOT }
    foreach ($k in 'root', 'ggb') {
        $v = ([string]$cfg[$k]).TrimEnd('\', '/')
        if (-not $v) { continue }
        if ($v -match '^[A-Za-z]:$') { $v += '\' }
        $cfg[$k] = [IO.Path]::GetFullPath($v)
    }
    # the release builds' private clones: inside the root unless the config says otherwise (a Godot export compiles no
    # path into the player, and the leak scan proves it per build)
    if (-not $cfg.ggb) { $cfg.ggb = Join-Path $cfg.root '_build' }
    $cfg.record_extra_projects = @($cfg.record_extra_projects | Where-Object { $_ })
    return [pscustomobject]$cfg
}

function Get-GGFRoot { return (Get-GGFConfig).root }

# The coding agents this machine is set up for ("claude", "codex", "antigravity"): "agents" in the config (bootstrap.ps1
# -Agent writes it); else the ones found installed (the claude / codex / agy command or their home folder, Antigravity's
# under ~\.gemini); else Claude Code and Codex.
function Get-GGFAgents($Cfg = (Get-GGFConfig)) {
    if ($Cfg.PSObject.Properties['agents'] -and @($Cfg.agents | Where-Object { $_ }).Count) { return @($Cfg.agents | ForEach-Object { ([string]$_).ToLower() } | Where-Object { $_ -in 'claude', 'codex', 'antigravity' } | Select-Object -Unique) }
    $found = @()
    if ((Get-Command claude -ErrorAction SilentlyContinue) -or (Test-Path -LiteralPath (Join-Path $env:USERPROFILE '.claude'))) { $found += 'claude' }
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
    if ((Get-Command codex -ErrorAction SilentlyContinue) -or (Test-Path -LiteralPath $codexHome)) { $found += 'codex' }
    $gemini = Join-Path $env:USERPROFILE '.gemini'
    if ((Get-Command agy -ErrorAction SilentlyContinue) -or @('antigravity', 'antigravity-cli', 'antigravity-ide' | Where-Object { Test-Path -LiteralPath (Join-Path $gemini $_) }).Count) { $found += 'antigravity' }
    if (-not $found) { $found = @('claude', 'codex') }
    return $found
}

# The recording hooks' folder (record-godot-action.ps1, record-godot-commit.ps1, the session map), one for every agent:
# "hooks_dir" in the config, else %USERPROFILE%\.godot-game-factory\hooks. Never another factory's hooks folder: each
# factory's hooks record only the sessions mapped to its own root, and each keeps its own session map.
function Get-GGFHooksDir($Cfg = (Get-GGFConfig)) {
    if ($Cfg.PSObject.Properties['hooks_dir'] -and $Cfg.hooks_dir) { return [IO.Path]::GetFullPath([string]$Cfg.hooks_dir) }
    return (Join-Path $env:USERPROFILE '.godot-game-factory\hooks')
}

# The godot-game-factory clone: the one this file is in (machine\lib), else "checkout" in the config (bootstrap.ps1
# writes the clone it ran from, for the installed copies of this file), else <root>\godot-game-factory.
function Get-GGFCheckout($Cfg = (Get-GGFConfig)) {
    $here = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    if ($here -and (Test-Path -LiteralPath (Join-Path $here 'machine\lib\ggf-root.ps1'))) { return [IO.Path]::GetFullPath($here) }
    if ($Cfg.PSObject.Properties['checkout'] -and $Cfg.checkout) { return [IO.Path]::GetFullPath(([string]$Cfg.checkout).TrimEnd('\', '/')) }
    return (Join-Path $Cfg.root 'godot-game-factory')
}

# ---- the engine ------------------------------------------------------------------------------------------------------
# The pinned engine, machine\godot.json (the one place that names it): version, flavor, feature ("4.7": what a game's
# project.godot names in config/features), exe, console_exe, templates (the export templates' folder name), urls,
# sha512. Read from next to this file (<root>\tools\ holds a copy) or from the clone.
function Get-GGFEngine {
    $p = @((Join-Path $PSScriptRoot 'godot.json'), (Join-Path $PSScriptRoot '..\godot.json'), (Join-Path (Get-GGFCheckout) 'machine\godot.json')) |
        Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $p) { throw "godot.json not found next to $PSScriptRoot\ggf-root.ps1 or in the godot-game-factory clone: run machine\bootstrap.ps1" }
    return ([IO.File]::ReadAllText($p) | ConvertFrom-Json)
}

# The pinned engine's folder: <root>\godot\<version>. Self-contained (an empty ._sc_ file beside the exe), so the
# editor's data and settings are in its editor_data\ and the export templates in editor_data\export_templates\<templates>\.
function Get-GGFGodotDir($Cfg = (Get-GGFConfig)) { return (Join-Path $Cfg.root "godot\$((Get-GGFEngine).version)") }

# The editor exe: $env:GODOT_EDITOR, else "godot" in the config, else <root>\godot\<version>\<exe>. -Console gives the
# console wrapper beside it (it waits for the engine and passes its output and exit code on: what tools run); an editor
# without one is returned as it is. $null with a warning naming what installs it when the exe is missing (none under
# -ErrorAction SilentlyContinue / Ignore): callers decide whether that is fatal.
function Get-GGFGodot {
    [CmdletBinding()]
    param([switch]$Console, $Cfg = (Get-GGFConfig))
    $exe = ''
    if ($env:GODOT_EDITOR) { $exe = $env:GODOT_EDITOR }
    elseif ($Cfg.PSObject.Properties['godot'] -and $Cfg.godot) { $exe = [string]$Cfg.godot }
    else { $exe = Join-Path (Get-GGFGodotDir $Cfg) (Get-GGFEngine).exe }
    $exe = [IO.Path]::GetFullPath($exe)
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        if ($ErrorActionPreference -notin 'SilentlyContinue', 'Ignore') {
            Write-Warning "Godot $((Get-GGFEngine).version) is not at ${exe}: run machine\get-godot.ps1, or name the editor exe in `"godot`" in $(Get-GGFConfigPath)"
        }
        return $null
    }
    if ($Console -and $exe -notmatch '(?i)_console\.exe$') {
        $c = $exe -replace '(?i)\.exe$', '_console.exe'
        if (Test-Path -LiteralPath $c -PathType Leaf) { return $c }
    }
    return $exe
}

# The editor's data folder when the editor is self-contained (._sc_ or _sc_ beside the exe): <exe folder>\editor_data.
# '' for an editor that keeps its data in %APPDATA% (one named in the config or GODOT_EDITOR that is not self-contained).
function Get-GGFEditorData($Cfg = (Get-GGFConfig)) {
    $exe = Get-GGFGodot -Cfg $Cfg -ErrorAction SilentlyContinue
    $dir = if ($exe) { Split-Path $exe -Parent } else { Get-GGFGodotDir $Cfg }
    if ((Test-Path -LiteralPath (Join-Path $dir '._sc_')) -or (Test-Path -LiteralPath (Join-Path $dir '_sc_'))) { return (Join-Path $dir 'editor_data') }
    return ''
}

# The editor settings file of the self-contained editor (editor_data\editor_settings-<feature>.tres), '' without one.
function Get-GGFEditorSettingsPath($Cfg = (Get-GGFConfig)) {
    $d = Get-GGFEditorData $Cfg
    if (-not $d) { return '' }
    return (Join-Path $d "editor_settings-$((Get-GGFEngine).feature).tres")
}

# python.exe for the factory's Python tools (the Microsoft Store stub does not count), else the py launcher, else ''.
function Get-GGFPython {
    $py = Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' } | Select-Object -First 1
    if ($py) { return $py.Source }
    if (Get-Command py -ErrorAction SilentlyContinue) { return 'py' }
    return ''
}

# A game's platform, read by the one reader of Platform.json: tools\validate-game.py --platform <folder> (it prints
# one JSON line, {"platform": "desktop"} or {"platform": "mobile", "orientation", "width", "height"}; a bad file is
# an error, never read as desktop). Returns
# @{ platform; orientation; width; height }: the size every play, still and recording of the game has (desktop and
# mobile landscape 1920x1080, mobile portrait 1080x1920); orientation is $null for a desktop game.
function Get-GGFPlatform {
    param([Parameter(Mandatory = $true)][string]$Folder)
    $tool = Join-Path (Get-GGFCheckout) 'tools\validate-game.py'
    if (-not (Test-Path -LiteralPath $tool)) { throw "Get-GGFPlatform: $tool is not there (the godot-game-factory clone; `"checkout`" in $(Get-GGFConfigPath))" }
    $py = Get-GGFPython
    if (-not $py) { throw 'Get-GGFPlatform: no python.exe (winget install Python.Python.3.12)' }
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $out = @(& $py $tool --platform $Folder 2>&1 | ForEach-Object { "$_" }); $code = $LASTEXITCODE }
    finally { $ErrorActionPreference = $old }
    if ($code -ne 0) { throw "Get-GGFPlatform ${Folder}: $(($out -join ' ').Trim())" }
    $line = [string](@($out | Where-Object { "$_".Trim() }) | Select-Object -Last 1)
    $said = $null
    try { $said = $line | ConvertFrom-Json } catch { }
    if ($said -and $said.platform -eq 'desktop') { return [ordered]@{ platform = 'desktop'; orientation = $null; width = 1920; height = 1080 } }
    if ($said -and $said.platform -eq 'mobile' -and $said.orientation -and $said.width -and $said.height) {
        return [ordered]@{ platform = 'mobile'; orientation = [string]$said.orientation; width = [int]$said.width; height = [int]$said.height }
    }
    throw "Get-GGFPlatform ${Folder}: validate-game.py --platform printed '$line'"
}

# ---- the Android toolchain (machine\get-android.ps1) -------------------------------------------------------------------
# Everything is in one folder, the toolchain's home: "android": {"home": ...} in the config, else <root>\android.
#   jdk\            the JDK (jdk\bin\java.exe, keytool.exe)
#   sdk\            the Android SDK (cmdline-tools\latest, platform-tools, build-tools\<version>, platforms\android-<n>)
#   keystores\      debug.keystore and release.keystore, made on this machine
#   gradle\         GRADLE_USER_HOME of every Android build (Gradle itself and what it downloads; its gradle.properties
#                   turns the Gradle daemon off, so no Java process outlives an export)
#   .android\       ANDROID_USER_HOME: what the Android tools would otherwise keep in %USERPROFILE%\.android
#   toolchain.json  what get-android.ps1 installed: the engine version it was made for, the SDK packages, the keystores'
#                   users and passwords
# Nothing of it is installed machine-wide, and no PATH or environment variable is changed.
function Get-GGFAndroidHome($Cfg = (Get-GGFConfig)) {
    if ($Cfg.PSObject.Properties['android'] -and $Cfg.android -and $Cfg.android.PSObject.Properties['home'] -and $Cfg.android.home) {
        return [IO.Path]::GetFullPath(([string]$Cfg.android.home).TrimEnd('\', '/'))
    }
    return (Join-Path $Cfg.root 'android')
}

# The toolchain piece by piece, for machine\check.ps1 and get-android.ps1: objects { name; present; detail }.
function Get-GGFAndroidParts($Cfg = (Get-GGFConfig)) {
    $h = Get-GGFAndroidHome $Cfg
    $tcPath = Join-Path $h 'toolchain.json'
    $tc = $null
    if (Test-Path -LiteralPath $tcPath) { try { $tc = [IO.File]::ReadAllText($tcPath) | ConvertFrom-Json } catch { $tc = $null } }
    $parts = @()
    $java = Join-Path $h 'jdk\bin\java.exe'
    $parts += [pscustomobject]@{ name = 'JDK'; present = (Test-Path -LiteralPath $java); detail = $java }
    $sdk = Join-Path $h 'sdk'
    $files = [ordered]@{ 'cmdline-tools;latest' = 'cmdline-tools\latest\bin\sdkmanager.bat'; 'platform-tools' = 'platform-tools\adb.exe' }
    if ($tc) {
        $files["build-tools;$($tc.build_tools)"] = "build-tools\$($tc.build_tools)\apksigner.bat"
        $files["platforms;android-$($tc.compile_sdk)"] = "platforms\android-$($tc.compile_sdk)\android.jar"
        if ($tc.PSObject.Properties['ndk'] -and $tc.ndk) { $files["ndk;$($tc.ndk)"] = "ndk\$($tc.ndk)\source.properties" }
    }
    foreach ($k in $files.Keys) {
        $f = Join-Path $sdk $files[$k]
        $parts += [pscustomobject]@{ name = "SDK $k"; present = (Test-Path -LiteralPath $f); detail = $f }
    }
    foreach ($k in 'debug', 'release') {
        $ks = if ($tc -and $tc.PSObject.Properties["${k}_keystore"]) { $tc."${k}_keystore" } else { $null }
        $f = Join-Path $h "keystores\$k.keystore"
        $ok = (Test-Path -LiteralPath $f) -and $ks -and $ks.user -and $ks.password
        $parts += [pscustomobject]@{ name = "$k keystore"; present = [bool]$ok; detail = $f }
    }
    $parts += [pscustomobject]@{ name = 'toolchain.json'; present = [bool]$tc; detail = $tcPath }
    return $parts
}

# The toolchain a Godot Android export needs, or $null when any piece of it is missing (then a mobile game is still
# made, played, recorded and task-checked; only its APK is skipped). Keys: home, jdk (JAVA_HOME), java, keytool, sdk
# (ANDROID_HOME), gradle_home (GRADLE_USER_HOME), godot (the engine version it was made for), build_tools, compile_sdk,
# ndk ('' when none is installed), debug_keystore and release_keystore (each: path, user, password).
function Get-GGFAndroid($Cfg = (Get-GGFConfig)) {
    $parts = @(Get-GGFAndroidParts $Cfg)
    if (@($parts | Where-Object { -not $_.present }).Count) { return $null }
    $h = Get-GGFAndroidHome $Cfg
    $tc = [IO.File]::ReadAllText((Join-Path $h 'toolchain.json')) | ConvertFrom-Json
    $ks = { param($k) [pscustomobject]@{ path = (Join-Path $h "keystores\$k.keystore"); user = [string]$tc."${k}_keystore".user; password = [string]$tc."${k}_keystore".password } }
    return [pscustomobject][ordered]@{
        home             = $h
        jdk              = (Join-Path $h 'jdk')
        java             = (Join-Path $h 'jdk\bin\java.exe')
        keytool          = (Join-Path $h 'jdk\bin\keytool.exe')
        sdk              = (Join-Path $h 'sdk')
        gradle_home      = (Join-Path $h 'gradle')
        godot            = [string]$tc.godot
        build_tools      = [string]$tc.build_tools
        compile_sdk      = [int]$tc.compile_sdk
        ndk              = $(if ($tc.PSObject.Properties['ndk'] -and $tc.ndk) { [string]$tc.ndk } else { '' })
        debug_keystore   = (& $ks 'debug')
        release_keystore = (& $ks 'release')
    }
}

# Give this process (and the engine it starts) what an Android export reads from the environment: GRADLE_USER_HOME (the
# toolchain's own Gradle home), JAVA_HOME, ANDROID_HOME, ANDROID_USER_HOME and ANDROID_PREFS_ROOT (the toolchain's
# .android: without both, the Android Gradle plugin writes into %USERPROFILE%\.android) and the keystores (GODOT_ANDROID_KEYSTORE_DEBUG_* and
# GODOT_ANDROID_KEYSTORE_RELEASE_*: PATH, USER, PASSWORD; they override an export preset's own). The JDK and SDK paths
# the export itself uses are in the editor settings (get-android.ps1 writes them). Returns Get-GGFAndroid's object, or
# $null (and sets nothing) when the toolchain is not installed. Only this process's environment is changed.
function Set-GGFAndroidEnv($Cfg = (Get-GGFConfig)) {
    $a = Get-GGFAndroid $Cfg
    if (-not $a) { return $null }
    $env:GRADLE_USER_HOME = $a.gradle_home
    $env:JAVA_HOME = $a.jdk
    $env:ANDROID_HOME = $a.sdk
    $env:ANDROID_USER_HOME = (Join-Path $a.home '.android')
    $env:ANDROID_PREFS_ROOT = $a.home
    $env:GODOT_ANDROID_KEYSTORE_DEBUG_PATH = $a.debug_keystore.path
    $env:GODOT_ANDROID_KEYSTORE_DEBUG_USER = $a.debug_keystore.user
    $env:GODOT_ANDROID_KEYSTORE_DEBUG_PASSWORD = $a.debug_keystore.password
    $env:GODOT_ANDROID_KEYSTORE_RELEASE_PATH = $a.release_keystore.path
    $env:GODOT_ANDROID_KEYSTORE_RELEASE_USER = $a.release_keystore.user
    $env:GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD = $a.release_keystore.password
    return $a
}

# ---- ffmpeg ------------------------------------------------------------------------------------------------------------
# ffmpeg.exe for the recording pipeline and the sound tools: $env:GGF_FFMPEG, else "ffmpeg" in the config, else the
# pinned copy machine\get-ffmpeg.ps1 puts in <root>\tools\ffmpeg-8.1.2, else the one on PATH. '' when there is none.
function Get-GGFFfmpeg($Cfg = (Get-GGFConfig)) {
    if ($env:GGF_FFMPEG -and (Test-Path -LiteralPath $env:GGF_FFMPEG -PathType Leaf)) { return [IO.Path]::GetFullPath($env:GGF_FFMPEG) }
    if ($Cfg.PSObject.Properties['ffmpeg'] -and $Cfg.ffmpeg -and (Test-Path -LiteralPath ([string]$Cfg.ffmpeg) -PathType Leaf)) { return [IO.Path]::GetFullPath([string]$Cfg.ffmpeg) }
    $pinned = Join-Path $Cfg.root 'tools\ffmpeg-8.1.2\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe'
    if (Test-Path -LiteralPath $pinned) { return $pinned }
    $cmd = Get-Command ffmpeg -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    return ''
}

# ffprobe.exe beside that ffmpeg.exe, '' when there is none.
function Get-GGFFfprobe($Cfg = (Get-GGFConfig)) {
    $ff = Get-GGFFfmpeg $Cfg
    if (-not $ff) { return '' }
    $probe = Join-Path (Split-Path $ff -Parent) 'ffprobe.exe'
    if (Test-Path -LiteralPath $probe) { return $probe }
    return ''
}

# GitHub organisation (or user) that owns godot-game-factory and the private godot-game-<slug> repos: $env:GGF_ORG,
# else "github_org" in the config file (bootstrap.ps1 -Org writes it), else '' (callers that need it say how to set it).
function Get-GGFOrg($Cfg = (Get-GGFConfig)) {
    if ($env:GGF_ORG) { return $env:GGF_ORG.Trim() }
    if ($Cfg.PSObject.Properties['github_org'] -and $Cfg.github_org) { return ([string]$Cfg.github_org).Trim() }
    return ''
}

# Output root for packages (the creation replay's _replay\<slug>\<sha8>\; the dataset packager's commit maps, audit
# files, package-log.jsonl and run lock in <slug>\, its zip next to the game repo unless its --out names another
# folder): $env:GGF_OUT, else "out" in the config file, else <root>\deliverables.
# Point it at a roomy drive (packages and zips run to GBs per game).
function Get-GGFOut {
    if ($env:GGF_OUT) { return [IO.Path]::GetFullPath($env:GGF_OUT.TrimEnd('\', '/')) }
    $cfg = Get-GGFConfig
    if ($cfg.PSObject.Properties['out'] -and $cfg.out) { return [IO.Path]::GetFullPath(([string]$cfg.out).TrimEnd('\', '/')) }
    return (Join-Path $cfg.root 'deliverables')
}

# Refuse to start a disk-heavy job (the dataset packager, the creation replay, the task check and the task try are
# Python and use ggfroot.py check_free) when the drive holding $Path has less than the floor free: $env:GGF_MIN_FREE_GB,
# else "min_free_gb" in the config file, else 50. A full disk mid-job corrupts the result.
function Assert-GGFFreeSpace([string]$Path, [string]$What = 'this job') {
    $min = 50
    $cfg = Get-GGFConfig
    if ($cfg.PSObject.Properties['min_free_gb'] -and $cfg.min_free_gb) { $min = [double]$cfg.min_free_gb }
    if ($env:GGF_MIN_FREE_GB) { $min = [double]$env:GGF_MIN_FREE_GB }
    $full = [IO.Path]::GetFullPath($Path)
    # a game folder may be a junction to another drive (games\<game> -> D:\...): count the drive the data lands on
    for ($d = $full; $d; $d = Split-Path $d -Parent) {
        $it = Get-Item -LiteralPath $d -Force -ErrorAction SilentlyContinue
        if ($it -and $it.LinkType -and $it.Target) { $full = [IO.Path]::GetFullPath([string]@($it.Target)[0] + $full.Substring($d.Length)); break }
    }
    $drive = New-Object IO.DriveInfo ([IO.Path]::GetPathRoot($full))
    $free = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
    if ($free -lt $min) {
        throw ("{0}: only {1} GB free on {2} (floor {3} GB; GGF_MIN_FREE_GB / min_free_gb). Free space or point --scratch (the task check and the task try) / GGF_OUT (packages) at another drive." -f $What, $free, $drive.Name, $min)
    }
    return $free
}

# Regex matching a path under the root in the spellings tool calls use: C:\a\b, C:/a/b, /c/a/b (Git Bash), /mnt/c/a/b.
# The drive must start a path (not follow a letter, digit, dot or hyphen): D:/backup/c/a/b is not under C:\a\b, and
# a path glued to an option (git -C/c/a/b) does not count either.
# Append the part after the root yourself, e.g. (Get-GGFRootPattern) + '[\\/]+games[\\/]+([A-Za-z0-9_-]+)'.
function Get-GGFRootPattern([string]$Root = (Get-GGFRoot)) {
    $full = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $drive = $full.Substring(0, 1)
    $rest = @($full.Substring(2).Split('\') | Where-Object { $_ } | ForEach-Object { [regex]::Escape($_) })
    $head = "(?<![\w.-])(?:$drive`:|/$drive|/mnt/$drive)"
    if ($rest.Count -eq 0) { return "(?i)$head" }
    return "(?i)$head[\\/]+" + ($rest -join '[\\/]+')
}

# The roots of the other factories set up on this machine (none: an empty list). Each is found the way that factory
# finds its own root: its environment variable, else "root" in its config file, else its default folder when that holds
# its clone. Used only to read their recording flags and job logs, so every factory shares the machine's slots fairly.
function Get-GGFOtherFactoryRoots {
    $mine = [IO.Path]::GetFullPath((Get-GGFRoot).TrimEnd('\'))
    $known = @(
        @{ env = 'GF_ROOT'; cfgEnv = 'GF_CONFIG'; cfg = '.game-factory\config.json'; dir = 'Work'; clone = 'game-factory' },
        @{ env = 'UGF_ROOT'; cfgEnv = 'UGF_CONFIG'; cfg = '.unity-game-factory\config.json'; dir = 'UnityWork'; clone = 'unity-game-factory' }
    )
    $roots = @()
    foreach ($k in $known) {
        $r = [Environment]::GetEnvironmentVariable($k.env)
        if (-not $r) {
            $cfg = [Environment]::GetEnvironmentVariable($k.cfgEnv)
            if (-not $cfg) { $cfg = Join-Path $env:USERPROFILE $k.cfg }
            if (Test-Path -LiteralPath $cfg) {
                try { $j = [IO.File]::ReadAllText($cfg) | ConvertFrom-Json; if ($j.root) { $r = [string]$j.root } } catch { }
            }
            if (-not $r) {
                $w = Join-Path $env:USERPROFILE $k.dir
                if (Test-Path -LiteralPath (Join-Path $w $k.clone)) { $r = $w }
            }
        }
        if (-not $r) { continue }
        $full = [IO.Path]::GetFullPath($r.TrimEnd('\', '/'))
        if ($full -ne $mine -and $roots -notcontains $full) { $roots += $full }
    }
    return $roots
}

# The "a recording waits for the GPU" flags godot-heavy.ps1 honours: the other factories'
# (<their root>\builds\_queue\_recording-wants-gpu; their recorders capture the screen and take every GPU slot while
# they run). This factory writes no such flag: its recordings are written by the engine frame by frame and need no
# screen, so they take one GPU slot like any rendered run.
function Get-GGFRecordingFlags {
    $flags = @(Get-GGFOtherFactoryRoots | ForEach-Object { Join-Path $_ 'builds\_queue\_recording-wants-gpu' })
    , $flags
}

# The heavy-job logs every limiter writes (ours first): godot-heavy.ps1 reads waits and recent GPU starts from all, so
# its jobs see the other factories'.
function Get-GGFJobLogs {
    $logs = @(Join-Path (Get-GGFRoot) '.recording\_heavy-jobs.jsonl')
    foreach ($o in @(Get-GGFOtherFactoryRoots)) { $logs += (Join-Path $o '.recording\_heavy-jobs.jsonl') }
    , $logs
}

# Machine-wide job slots (godot-heavy.ps1). Config keys win: heavy_slots (general slots: imports, exports, generator
# scripts, tests; GPU jobs hold one too), gpu_slots (concurrent rendering jobs), gpu_vram_limit_mb (a GPU job starts
# only while less VRAM than this is in use; default half the VRAM). Without them the slots are computed from the
# hardware (bootstrap.ps1 writes the computed values to the config), with the same formula as the other factories'
# limiters, so all factories agree on the counts:
#   heavy_slots = clamp(1..8, min(floor((RAM GB - 6) / 6), floor(logical cores / 4), floor((commit limit GB - 6) / 8)))
#                 (~6 GB per heavy process, 6 GB kept for the desktop and the sessions)
#   gpu_slots   = clamp(1..4, min(floor(VRAM GB of the largest NVIDIA GPU / 4), heavy_slots - 1)); 1 without nvidia-smi
#                 (~4 GB per renderer; one general slot always left for imports and exports)
function Get-GGFHardware {
    $cs = Get-CimInstance Win32_ComputerSystem
    $os = Get-CimInstance Win32_OperatingSystem
    $vram = @()
    try {
        $out = & nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null
        $vram = @($out | ForEach-Object { "$_".Trim() } | Where-Object { $_ -match '^\d+$' } | ForEach-Object { [int]$_ })
    } catch { }
    [pscustomobject]@{
        logical_cores = [int]$cs.NumberOfLogicalProcessors
        ram_gb        = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
        commit_gb     = [math]::Round($os.TotalVirtualMemorySize / 1MB, 1)
        gpu_count     = $vram.Count
        vram_mb       = $(if ($vram.Count) { ($vram | Measure-Object -Maximum).Maximum } else { 0 })
    }
}

function Get-GGFComputedSlots($Hw = (Get-GGFHardware)) {
    $heavy = [math]::Min([math]::Floor(($Hw.ram_gb - 6) / 6), [math]::Floor($Hw.logical_cores / 4))
    $heavy = [math]::Min($heavy, [math]::Floor(($Hw.commit_gb - 6) / 8))
    $heavy = [int][math]::Max(1, [math]::Min(8, $heavy))
    $gpu = if ($Hw.vram_mb -gt 0) { [math]::Min([math]::Floor($Hw.vram_mb / 1024 / 4), $heavy - 1) } else { 1 }
    $gpu = [int][math]::Max(1, [math]::Min(4, $gpu))
    [pscustomobject]@{ heavy_slots = $heavy; gpu_slots = $gpu; hardware = $Hw }
}

# The slots in effect and where each comes from: 'config' (set by hand), 'config (bootstrap)' (written by bootstrap.ps1
# from the formula, recorded in slots_auto), or 'computed' (no config key: the formula at run time).
function Get-GGFSlotPlan($Cfg = (Get-GGFConfig)) {
    $auto = if ($Cfg.PSObject.Properties['slots_auto']) { $Cfg.slots_auto } else { $null }
    $computed = $null
    $plan = [ordered]@{}
    foreach ($k in 'heavy_slots', 'gpu_slots') {
        if ($Cfg.PSObject.Properties[$k] -and [int]$Cfg.$k -gt 0) {
            $plan[$k] = [int]$Cfg.$k
            $plan["${k}_source"] = if ($auto -and $auto.PSObject.Properties[$k] -and [int]$auto.$k -eq [int]$Cfg.$k) { 'config (bootstrap)' } else { 'config' }
        } else {
            if (-not $computed) { $computed = Get-GGFComputedSlots }
            $plan[$k] = $computed.$k
            $plan["${k}_source"] = 'computed'
        }
    }
    $plan['gpu_vram_limit_mb'] = if ($Cfg.PSObject.Properties['gpu_vram_limit_mb'] -and [int]$Cfg.gpu_vram_limit_mb -gt 0) { [int]$Cfg.gpu_vram_limit_mb } else { 0 }
    [pscustomobject]$plan
}

# ---- machine-wide job slots: one named mutex per slot (godot-heavy.ps1) ----------------------------------------------
# A slot is the mutex Global\ue-heavy-slot-<n> (general) or Global\ue-gpu-slot-<n> (GPU), n < heavy_slots / gpu_slots.
# The names are another factory's on purpose: its limiter takes the same mutexes, so every factory on the machine
# draws from one set of slots and together they never run more heavy or GPU jobs than the machine holds. Unlike a
# counted semaphore nothing leaks: a holder that dies without releasing (killed job, crashed engine) leaves its mutex
# "abandoned", and the next taker gets it. The count is the config's at every call, so a new heavy_slots or gpu_slots
# takes effect at once. A mutex belongs to the thread that took it: take and release it in the same script.
function Get-GGFSlotMutexes([ValidateSet('heavy', 'gpu')][string]$Kind, [int]$Count) {
    $prefix = if ($Kind -eq 'gpu') { 'Global\ue-gpu-slot-' } else { 'Global\ue-heavy-slot-' }
    , @(for ($i = 0; $i -lt $Count; $i++) { New-Object Threading.Mutex($false, "$prefix$i") })
}

# Take a mutex within TimeoutMs; an abandoned one (its holder died) is taken over. $true when held.
function Enter-GGFMutex($Mutex, [int]$TimeoutMs = 0) {
    try { return [bool]$Mutex.WaitOne($TimeoutMs) }
    catch {
        $e = $_.Exception
        while ($e -and -not ($e -is [Threading.AbandonedMutexException])) { $e = $e.InnerException }
        if ($e) { return $true }
        throw
    }
}

# One free slot among indices From..Count-1 (Skip: indices this script already holds), without waiting; -1 if none.
function Enter-GGFSlot($Mutexes, [int]$From = 0, [int[]]$Skip = @()) {
    for ($i = [math]::Max(0, $From); $i -lt $Mutexes.Count; $i++) {
        if ($Skip -contains $i) { continue }
        if (Enter-GGFMutex $Mutexes[$i] 0) { return $i }
    }
    return -1
}

function Exit-GGFSlot($Mutexes, [int]$Index) {
    if ($Index -ge 0 -and $Index -lt $Mutexes.Count) { try { $Mutexes[$Index].ReleaseMutex() } catch { } }
}
