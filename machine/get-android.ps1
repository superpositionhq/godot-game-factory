<#
.SYNOPSIS
  Install the Android toolchain a mobile game's APK needs, all of it under <root>\android\ (idempotent).
.DESCRIPTION
  Godot builds an APK with Gradle (the export option "Use Gradle Build"), which needs a JDK, the Android SDK and two
  keystores. This script puts them in one folder, the toolchain's home (-AndroidHome, else "android": {"home": ...} in
  the machine config, else <root>\android), and tells the pinned editor where they are:
    jdk\             the JDK machine\android.json pins (Eclipse Temurin 17; SHA-256 verified)
    sdk\             the Android SDK: the command-line tools android.json pins (SHA-256 verified), then through their
                     sdkmanager "platform-tools" and the build-tools and platform the installed engine version's own
                     Android build template names (compileSdk and buildTools in config.gradle of the export templates'
                     android_source.zip). -Ndk also installs the NDK that file names: a Gradle build of a game works
                     without it (the engine's libraries in the template are already built).
    keystores\       debug.keystore (alias androiddebugkey, password android: the Android debug convention) and
                     release.keystore (alias release, a random password), made here with the JDK's keytool
    gradle\          GRADLE_USER_HOME of every Android build; its gradle.properties turns the Gradle daemon off, so no
                     Java process outlives an export
    .android\        ANDROID_USER_HOME: what the Android tools would otherwise keep in %USERPROFILE%\.android
    toolchain.json   what was installed: the engine version, the SDK packages, the keystores' users and passwords
  Then it writes the editor settings an export reads (export/android/java_sdk_path, android_sdk_path, debug_keystore,
  debug_keystore_pass; the debug key's alias is the editor's default) into the self-contained editor's settings file
  (<root>\godot\<version>\editor_data\editor_settings-<feature>.tres; a backup .bak-<time> of a file it changes), and
  "android": {"home": ...} into the machine config when there is one.
  Nothing is installed machine-wide and no PATH or environment variable is changed. A piece that is already there is
  left alone. The Android SDK packages come under the Android SDK licence agreements: the script says so and asks
  before accepting them for you; -Yes accepts without asking, a non-interactive run without -Yes stops there.
  The release keystore signs every APK this machine builds. Keep the keystores folder: an APK signed with another key
  does not install over one signed with this.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File machine\get-android.ps1
  powershell -ExecutionPolicy Bypass -File machine\get-android.ps1 -Yes -Ndk
#>
param(
    # machine root; default from machine/lib/ggf-root.ps1
    [string]$Root,
    # the toolchain's folder; default: the config's android.home, else <root>\android
    [string]$AndroidHome,
    # default: GGF_CONFIG / %USERPROFILE%\.godot-game-factory\config.json
    [string]$ConfigPath,
    # the editor settings file to write; default: the self-contained editor's (lib\ggf-root.ps1 Get-GGFEditorSettingsPath)
    [string]$EditorSettings,
    # accept the Android SDK licence agreements without asking
    [switch]$Yes,
    # also install the NDK the engine's build template names
    [switch]$Ndk,
    # the release certificate's name (it is inside every APK signed with it)
    [string]$ReleaseDname = 'CN=Android Release,O=Android,C=US',
    # already downloaded archives to use instead of downloading (still verified)
    [string]$JdkArchive,
    [string]$CmdlineToolsArchive
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib\ggf-root.ps1')
if ($ConfigPath) { $env:GGF_CONFIG = $ConfigPath }
if ($Root) { $env:GGF_ROOT = $Root }
$cfg = Get-GGFConfig
$Root = $cfg.root
$eng = Get-GGFEngine
$pins = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'android.json')) | ConvertFrom-Json
$ah = if ($AndroidHome) { [IO.Path]::GetFullPath($AndroidHome.TrimEnd('\', '/')) } else { Get-GGFAndroidHome $cfg }
$jdk = Join-Path $ah 'jdk'
$sdk = Join-Path $ah 'sdk'
$ksDir = Join-Path $ah 'keystores'
$dl = Join-Path $ah '_download'
$log = Join-Path $ah 'get-android.log'
$utf8 = New-Object Text.UTF8Encoding($false)
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
function Say([string]$Status, [string]$What, [string]$Detail = '') { Write-Host ("  [{0,-7}] {1}{2}" -f $Status, $What, $(if ($Detail) { " - $Detail" } else { '' })) }

# What the installed engine's Android build template needs: read from its own config.gradle.
$source = Join-Path (Get-GGFGodotDir $cfg) "editor_data\export_templates\$($eng.templates)\android_source.zip"
if (-not (Test-Path -LiteralPath $source)) { throw "$source is not there: the export templates hold the Android build template; run machine\get-godot.ps1 first" }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($source)
try {
    $entry = $zip.Entries | Where-Object { $_.FullName -eq 'config.gradle' } | Select-Object -First 1
    if (-not $entry) { throw "no config.gradle in $source" }
    $reader = New-Object IO.StreamReader($entry.Open())
    try { $gradle = $reader.ReadToEnd() } finally { $reader.Dispose() }
} finally { $zip.Dispose() }
function Get-GradleValue([string]$Key) {
    $m = [regex]::Match($gradle, "(?m)^\s*$Key\s*:\s*'?([^',\s]+)'?\s*,")
    if (-not $m.Success) { throw "config.gradle in $source names no $Key" }
    return $m.Groups[1].Value
}
$compileSdk = [int](Get-GradleValue 'compileSdk')
$buildTools = Get-GradleValue 'buildTools'
$ndkVersion = Get-GradleValue 'ndkVersion'
$packages = @('platform-tools', "build-tools;$buildTools", "platforms;android-$compileSdk")
if ($Ndk) { $packages += "ndk;$ndkVersion" }

Write-Host "Android toolchain for Godot $($eng.version) in $ah"
New-Item -ItemType Directory -Force $ah | Out-Null

function Get-Sha256([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
# A verified archive: the one given, else a download into $dl.
function Get-Archive($Pin, [string]$Given) {
    $want = ([string]$Pin.sha256).ToLowerInvariant()
    if ($Given) {
        if ((Get-Sha256 $Given) -ne $want) { throw "SHA-256 mismatch for $Given (expected $want)" }
        return $Given
    }
    $url = [string]$Pin.url
    $dest = Join-Path $dl ([IO.Path]::GetFileName(([uri]$url).LocalPath))
    New-Item -ItemType Directory -Force $dl | Out-Null
    if ((Test-Path -LiteralPath $dest) -and (Get-Sha256 $dest) -eq $want) { return $dest }
    Write-Host "  downloading $url"
    Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    if (Test-Path -LiteralPath $curl) {
        & $curl -sSL --fail -o $dest $url
        if ($LASTEXITCODE -ne 0) { throw "download failed (curl exit $LASTEXITCODE): $url" }
    } else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        (New-Object Net.WebClient).DownloadFile($url, $dest)
    }
    $h = Get-Sha256 $dest
    if ($h -ne $want) {
        Remove-Item -LiteralPath $dest -Force
        throw "SHA-256 mismatch for $url (sha256 $h; expected $want): discarded, nothing was unpacked"
    }
    return $dest
}
# Unpack a zip whose content is one top folder, and put that folder at $Target.
function Expand-TopFolder([string]$Archive, [string]$Target) {
    $stage = Join-Path $ah "_unpack-$PID"
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $stage | Out-Null
    & "$env:SystemRoot\System32\tar.exe" -xf $Archive -C $stage
    if ($LASTEXITCODE -ne 0) { throw "unpacking $Archive failed (exit $LASTEXITCODE)" }
    $top = @(Get-ChildItem -LiteralPath $stage -Directory)
    if ($top.Count -ne 1) { throw "unexpected archive layout in ${Archive}: $($top.Count) top folders" }
    New-Item -ItemType Directory -Force (Split-Path $Target) | Out-Null
    Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $top[0].FullName $Target
    Remove-Item -LiteralPath $stage -Recurse -Force
}
# Run a tool of the toolchain with its own JDK and its own Android user folder; output to the log. Returns the exit code.
function Invoke-Tool([string]$Exe, [string[]]$ArgList, [string]$Stdin = '') {
    $saved = @{}
    foreach ($k in 'JAVA_HOME', 'ANDROID_USER_HOME', 'ANDROID_PREFS_ROOT', 'ANDROID_HOME') { $saved[$k] = [Environment]::GetEnvironmentVariable($k) }
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try {
        $env:JAVA_HOME = $jdk; $env:ANDROID_USER_HOME = (Join-Path $ah '.android'); $env:ANDROID_PREFS_ROOT = $ah; $env:ANDROID_HOME = $sdk
        # the log never holds a keystore's password
        $shown = for ($i = 0; $i -lt $ArgList.Count; $i++) { if ($i -gt 0 -and $ArgList[$i - 1] -in '-keypass', '-storepass') { '***' } else { $ArgList[$i] } }
        [IO.File]::AppendAllText($log, "`n== $(Get-Date -Format s) $Exe $($shown -join ' ')`n", $utf8)
        if ($Stdin) { $out = $Stdin | & $Exe @ArgList 2>&1 | ForEach-Object { "$_" } }
        else { $out = & $Exe @ArgList 2>&1 | ForEach-Object { "$_" } }
        $code = $LASTEXITCODE
        [IO.File]::AppendAllText($log, (@($out) -join "`n") + "`n", $utf8)
        return $code
    } finally {
        $ErrorActionPreference = $old
        foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
    }
}

# --- JDK ------------------------------------------------------------------------------------------------------------
$release = Join-Path $jdk 'release'
$haveJdk = (Test-Path -LiteralPath (Join-Path $jdk 'bin\java.exe')) -and (Test-Path -LiteralPath $release) -and
    ([IO.File]::ReadAllText($release) -match ('JAVA_VERSION="' + [regex]::Escape($pins.jdk.java_version) + '"'))
if ($haveJdk) { Say ok "JDK $($pins.jdk.version)" $jdk }
else {
    Expand-TopFolder (Get-Archive $pins.jdk $JdkArchive) $jdk
    if (-not (Test-Path -LiteralPath (Join-Path $jdk 'bin\java.exe'))) { throw "unexpected archive layout: no bin\java.exe in the JDK" }
    Say added "JDK $($pins.jdk.version)" $jdk
}

# --- Android SDK: command-line tools ------------------------------------------------------------------------------------
$cmdline = Join-Path $sdk 'cmdline-tools\latest'
$sdkmanager = Join-Path $cmdline 'bin\sdkmanager.bat'
$props = Join-Path $cmdline 'source.properties'
$haveCmdline = (Test-Path -LiteralPath $sdkmanager) -and (Test-Path -LiteralPath $props) -and
    ([IO.File]::ReadAllText($props) -match ('(?m)^Pkg\.Revision=' + [regex]::Escape($pins.cmdline_tools.revision) + '\s*$'))
if ($haveCmdline) { Say ok "Android SDK command-line tools $($pins.cmdline_tools.revision)" $cmdline }
else {
    Expand-TopFolder (Get-Archive $pins.cmdline_tools $CmdlineToolsArchive) $cmdline
    if (-not (Test-Path -LiteralPath $sdkmanager)) { throw "unexpected archive layout: no bin\sdkmanager.bat in the command-line tools" }
    Say added "Android SDK command-line tools $($pins.cmdline_tools.revision)" $cmdline
}

# --- Android SDK: packages ----------------------------------------------------------------------------------------------
$probe = @{ 'platform-tools' = 'platform-tools\adb.exe'; "build-tools;$buildTools" = "build-tools\$buildTools\apksigner.bat"
    "platforms;android-$compileSdk" = "platforms\android-$compileSdk\android.jar"; "ndk;$ndkVersion" = "ndk\$ndkVersion\source.properties" }
$missing = @($packages | Where-Object { -not (Test-Path -LiteralPath (Join-Path $sdk $probe[$_])) })
foreach ($p in $packages) { if ($missing -notcontains $p) { Say ok "Android SDK $p" (Join-Path $sdk $probe[$p]) } }
if ($missing) {
    if (-not $Yes) {
        Write-Host ""
        Write-Host "  About to install with the Android SDK's sdkmanager: $($missing -join ', ')"
        Write-Host "  They come under the Android SDK licence agreements (https://developer.android.com/studio/terms);"
        Write-Host "  installing them accepts those agreements for this machine (the acceptance is kept in $sdk\licenses)."
        $ok = $false
        if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) { $ok = (Read-Host '  Accept the licence agreements and install? [y/N]') -match '^(y|yes)$' }
        if (-not $ok) { throw 'the Android SDK packages were not installed (declined or non-interactive; -Yes accepts the licence agreements without asking)' }
    }
    $answers = ((1..80 | ForEach-Object { 'y' }) -join "`r`n") + "`r`n"
    $code = Invoke-Tool $sdkmanager @("--sdk_root=$sdk", '--licenses') $answers
    if ($code -ne 0) { throw "sdkmanager --licenses failed (exit $code): see $log" }
    Write-Host "  installing $($missing -join ', ') (a few minutes) ..."
    # the package names go in through a file: a ";" in an argument is cut by cmd.exe on its way into sdkmanager.bat
    $list = Join-Path $ah '_packages.txt'
    [IO.File]::WriteAllText($list, (($missing -join "`r`n") + "`r`n"), $utf8)
    $code = Invoke-Tool $sdkmanager @("--sdk_root=$sdk", "--package_file=$list")
    Remove-Item -LiteralPath $list -Force -ErrorAction SilentlyContinue
    $still = @($missing | Where-Object { -not (Test-Path -LiteralPath (Join-Path $sdk $probe[$_])) })
    if ($code -ne 0 -or $still) { throw "sdkmanager failed (exit $code; not installed: $($still -join ', ')): see $log" }
    foreach ($p in $missing) { Say added "Android SDK $p" (Join-Path $sdk $probe[$p]) }
}

# --- keystores ------------------------------------------------------------------------------------------------------------
$tcPath = Join-Path $ah 'toolchain.json'
$tc = if (Test-Path -LiteralPath $tcPath) { [IO.File]::ReadAllText($tcPath) | ConvertFrom-Json } else { $null }
$keytool = Join-Path $jdk 'bin\keytool.exe'
New-Item -ItemType Directory -Force $ksDir | Out-Null
$keys = [ordered]@{}
foreach ($k in 'debug', 'release') {
    $file = Join-Path $ksDir "$k.keystore"
    $have = if ($tc -and $tc.PSObject.Properties["${k}_keystore"]) { $tc."${k}_keystore" } else { $null }
    if ((Test-Path -LiteralPath $file) -and $have -and $have.user -and $have.password) {
        $keys[$k] = [ordered]@{ user = [string]$have.user; password = [string]$have.password }
        Say ok "$k keystore" $file
        continue
    }
    # a keystore whose password this machine no longer knows cannot sign: it is kept aside, never deleted
    if (Test-Path -LiteralPath $file) { Move-Item -LiteralPath $file "$file.bak-$stamp" }
    if ($k -eq 'debug') { $user = 'androiddebugkey'; $pass = 'android'; $dname = 'CN=Android Debug,O=Android,C=US' }
    else { $user = 'release'; $pass = [Guid]::NewGuid().ToString('N'); $dname = $ReleaseDname }
    # Godot needs the keystore's and the key's password to be the same
    $code = Invoke-Tool $keytool @('-genkeypair', '-keyalg', 'RSA', '-keysize', '2048', '-alias', $user, '-keypass', $pass, '-keystore', $file,
        '-storepass', $pass, '-dname', $dname, '-validity', '10000', '-deststoretype', 'pkcs12')
    if ($code -ne 0 -or -not (Test-Path -LiteralPath $file)) { throw "keytool could not make $file (exit $code): see $log" }
    $keys[$k] = [ordered]@{ user = $user; password = $pass }
    Say added "$k keystore" "$file (alias $user)"
}
New-Item -ItemType Directory -Force (Join-Path $ah 'gradle'), (Join-Path $ah '.android') | Out-Null
# No Gradle daemon: one would outlive the export that started it, keep 4 GB of memory and the export's output pipes
# (a tool waiting for the export's output then never returns), and hold files of the game's android\ folder open.
$gp = Join-Path $ah 'gradle\gradle.properties'
$gpText = if (Test-Path -LiteralPath $gp) { [IO.File]::ReadAllText($gp) } else { '' }
if ($gpText -match '(?m)^\s*org\.gradle\.daemon\s*=\s*false\s*$') { Say ok 'Gradle daemon off' $gp }
else {
    $gpText = (($gpText -split "`r?`n") | Where-Object { $_ -notmatch '^\s*org\.gradle\.daemon\s*=' -and $_ -ne '' }) -join "`n"
    [IO.File]::WriteAllText($gp, ($(if ($gpText) { "$gpText`n" } else { '' }) + "org.gradle.daemon=false`n"), $utf8)
    Say added 'Gradle daemon off' $gp
}

# --- toolchain.json -------------------------------------------------------------------------------------------------------
$ndkHave = if (Test-Path -LiteralPath (Join-Path $sdk $probe["ndk;$ndkVersion"])) { $ndkVersion } else { '' }
$want = [ordered]@{
    schema           = 'godot-android-toolchain/1'
    godot            = [string]$eng.version
    jdk              = [string]$pins.jdk.version
    cmdline_tools    = [string]$pins.cmdline_tools.revision
    compile_sdk      = $compileSdk
    build_tools      = $buildTools
    ndk              = $ndkHave
    debug_keystore   = $keys['debug']
    release_keystore = $keys['release']
}
$text = ($want | ConvertTo-Json -Depth 5) + "`n"
if ((Test-Path -LiteralPath $tcPath) -and [IO.File]::ReadAllText($tcPath) -ceq $text) { Say ok 'toolchain.json' $tcPath }
else { [IO.File]::WriteAllText($tcPath, $text, $utf8); Say $(if ($tc) { 'changed' } else { 'added' }) 'toolchain.json' $tcPath }
Remove-Item -LiteralPath $dl -Recurse -Force -ErrorAction SilentlyContinue

# --- the editor's settings ------------------------------------------------------------------------------------------------
# An export reads the JDK, the SDK and the debug keystore from the editor settings (the release keystore comes from the
# environment, lib\ggf-root.ps1 Set-GGFAndroidEnv). Only these four lines are set; every other line stays as it was.
if (-not $EditorSettings) { $EditorSettings = Get-GGFEditorSettingsPath $cfg }
if (-not $EditorSettings) {
    Say warn 'editor settings' "the editor is not self-contained: set Export > Android > Java SDK Path ($jdk) and Android SDK Path ($sdk) in its Editor Settings by hand"
} else {
    $slash = { param($p) ([string]$p) -replace '\\', '/' }
    $values = [ordered]@{
        'export/android/java_sdk_path'        = (& $slash $jdk)
        'export/android/android_sdk_path'     = (& $slash $sdk)
        'export/android/debug_keystore'       = (& $slash (Join-Path $ksDir 'debug.keystore'))
        'export/android/debug_keystore_pass'  = $keys['debug'].password
    }
    $exists = Test-Path -LiteralPath $EditorSettings
    $lines = New-Object Collections.Generic.List[string]
    if ($exists) { $lines.AddRange([string[]]([IO.File]::ReadAllText($EditorSettings) -replace "`r`n", "`n").TrimEnd("`n").Split("`n")) }
    else { $lines.AddRange([string[]]@('[gd_resource type="EditorSettings" format=3]', '', '[resource]')) }
    $start = $lines.IndexOf('[resource]')
    if ($start -lt 0) { throw "$EditorSettings has no [resource] section: nothing was written to it" }
    $end = $lines.Count
    for ($i = $start + 1; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^\[') { $end = $i; break } }
    $changed = -not $exists
    foreach ($k in $values.Keys) {
        $line = $k + ' = "' + (([string]$values[$k]) -replace '\\', '\\' -replace '"', '\"') + '"'
        $at = -1
        for ($i = $start + 1; $i -lt $end; $i++) { if ($lines[$i].StartsWith("$k = ")) { $at = $i; break } }
        if ($at -ge 0) { if ($lines[$at] -cne $line) { $lines[$at] = $line; $changed = $true } }
        else {
            $ins = $end
            while ($ins -gt $start + 1 -and -not $lines[$ins - 1].Trim()) { $ins-- }
            $lines.Insert($ins, $line); $end++; $changed = $true
        }
    }
    if (-not $changed) { Say ok 'editor settings' $EditorSettings }
    else {
        New-Item -ItemType Directory -Force (Split-Path $EditorSettings) | Out-Null
        if ($exists) { Copy-Item -LiteralPath $EditorSettings "$EditorSettings.bak-$stamp" }
        [IO.File]::WriteAllText($EditorSettings, (($lines -join "`n") + "`n"), $utf8)
        Say $(if ($exists) { 'changed' } else { 'added' }) 'editor settings' "$EditorSettings (export/android/java_sdk_path, android_sdk_path, debug_keystore, debug_keystore_pass)"
    }
}

# --- the machine config -----------------------------------------------------------------------------------------------------
$cfgPath = Get-GGFConfigPath
if (Test-Path -LiteralPath $cfgPath) {
    $now = [IO.File]::ReadAllText($cfgPath) | ConvertFrom-Json
    $cur = if ($now.PSObject.Properties['android'] -and $now.android) { [string]$now.android.home } else { '' }
    if ($cur -eq $ah) { Say ok "config $cfgPath" "android.home = $ah" }
    else {
        Copy-Item -LiteralPath $cfgPath "$cfgPath.bak-$stamp"
        if ($now.PSObject.Properties['android']) { $now.android = [pscustomobject]@{ home = $ah } } else { $now | Add-Member android ([pscustomobject]@{ home = $ah }) }
        [IO.File]::WriteAllText($cfgPath, ($now | ConvertTo-Json -Depth 100) + "`n", $utf8)
        Say changed "config $cfgPath" "android.home = $ah (backup .bak-$stamp)"
    }
} elseif ($ah -ne (Join-Path $Root 'android')) {
    Say warn "config $cfgPath" "not there yet: run machine\bootstrap.ps1, then this script again with -AndroidHome $ah (the config must name a toolchain that is not in <root>\android)"
} else { Say ok 'config' "no $cfgPath yet; <root>\android is the default" }

$a = Get-GGFAndroid ([pscustomobject]@{ root = $Root; android = [pscustomobject]@{ home = $ah } })
if (-not $a) { throw "the toolchain in $ah is not complete: run machine\check.ps1" }
Write-Host "Android toolchain ready: JDK $($pins.jdk.version), build-tools $buildTools, platform android-$compileSdk$(if ($ndkHave) { ", NDK $ndkHave" }), keystores in $ksDir"
