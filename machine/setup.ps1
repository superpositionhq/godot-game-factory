<#
.SYNOPSIS
  One entry point for a clean Windows 11 PC: from nothing to building Godot games. Idempotent: run it again after any
  manual step and it continues where it stopped.
.DESCRIPTION
  1. Hardware precheck against the stated minimums (below).
  2. Software through winget (asks once, lists what is missing; winget accepts each package's licence):
     Git (+ Git LFS), GitHub CLI, Python 3.12, and the Codex CLI when Codex is one of the agents.
  3. GitHub sign-in (asked first: only people who push game repos need it) and git user.name / user.email.
  4. godot-game-factory: cloned into <root>\godot-game-factory when this script runs from outside a clone, then
     machine\get-godot.ps1 (the pinned Godot editor and its export templates into <root>\godot\<version>\; nothing
     machine-wide), machine\bootstrap.ps1 (config, tools, ffmpeg, hooks after its own question, skills; -CloneGames
     when you say so), with -Android machine\get-android.ps1 (the JDK, the Android SDK and the keystores a mobile
     game's APK needs, into <root>\android\; it asks before accepting the Android SDK licence agreements), and
     machine\check.ps1.
  5. What cannot be scripted (signing in to the coding agent): exact steps.
  The coding agent: -Agent claude (Claude Code), codex (OpenAI Codex CLI) or both; passed on to bootstrap.ps1, which
  wires the recording hooks, skills and root instructions into each (default: the config's, else what is installed).
  Ends with a PASS / TODO list. Log: <root>\.setup\setup.log.
  Other factories may already be set up on this PC: this one uses its own root, config, hooks and skills (godot-*) and
  leaves theirs alone; they share only the machine-wide job slots.

  Minimums: Windows 11; 8 logical cores and 16 GB RAM (32 GB recommended: job slots scale with RAM); 100 GB free on
  the root's drive (the engine with its export templates is 2 GB, the Android toolchain with its Gradle home 2 GB, game repos, builds,
  recordings and packages grow); a GPU with Vulkan and a current driver (plays and recordings are rendered).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org>
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org> -Agent codex -Android
  powershell -ExecutionPolicy Bypass -File setup.ps1 -Org <org> -Root D:\GodotWork -CloneGames
  # dry run against a scratch root (installs, downloads, sign-ins and game clones are only reported):
  powershell -ExecutionPolicy Bypass -File machine\setup.ps1 -Org <org> -DryRun -Root C:\ggf-test\GodotWork `
      -ClaudeDir C:\ggf-test\home\.claude -CodexDir C:\ggf-test\home\.codex -AgentsSkillsDir C:\ggf-test\home\.agents\skills `
      -HooksDir C:\ggf-test\home\.godot-game-factory\hooks -ConfigPath C:\ggf-test\home\.godot-game-factory\config.json -Agent both
#>
param(
    # default: the config's root, else asked (%USERPROFILE%\GodotWork offered)
    [string]$Root,
    # GitHub org/user that owns godot-game-factory and the game repos (config github_org)
    [string]$Org,
    # also install the Android toolchain (machine\get-android.ps1): needed only for a mobile game's APK
    [switch]$Android,
    # also clone every <org>/godot-game-* repo
    [switch]$CloneGames,
    # answer yes to every question (installs, the Android SDK licence agreements, hooks)
    [switch]$Yes,
    # no installs, downloads, sign-ins or game clones; bootstrap runs only
    # given -ConfigPath, -ClaudeDir, -CodexDir, -AgentsSkillsDir and -HooksDir
    [switch]$DryRun,
    # where to clone godot-game-factory from (default https://github.com/<org>/godot-game-factory)
    [string]$RepoUrl,
    # the coding agent(s); default: the config's, else what is installed
    [ValidateSet('', 'claude', 'codex', 'both')][string]$Agent = '',
    [string]$ClaudeDir = (Join-Path $env:USERPROFILE '.claude'),
    # default: CODEX_HOME / %USERPROFILE%\.codex
    [string]$CodexDir,
    # default: %USERPROFILE%\.agents\skills (Codex's personal skills)
    [string]$AgentsSkillsDir,
    # default: the config's hooks_dir
    [string]$HooksDir,
    [string]$ConfigPath,
    [switch]$SkipFfmpeg
)
$ErrorActionPreference = 'Stop'
$items = New-Object Collections.Generic.List[object]
function Item([string]$Status, [string]$What, [string]$Detail = '', [string]$Todo = '') {
    $items.Add([pscustomobject]@{ status = $Status; what = $What; detail = $Detail; todo = $Todo })
    $c = @{ PASS = 'Green'; TODO = 'Yellow'; INFO = 'DarkGray'; SKIP = 'DarkGray' }[$Status]
    Write-Host ("  [{0}] {1}{2}" -f $Status, $What, $(if ($Detail) { " - $Detail" } else { '' })) -ForegroundColor $c
}
$interactive = [Environment]::UserInteractive -and -not [Console]::IsInputRedirected
function Ask([string]$Question, [bool]$Default = $false) {
    if ($Yes) { return $true }
    if (-not $interactive) { return $false }
    $hint = if ($Default) { '[Y/n]' } else { '[y/N]' }
    $a = (Read-Host "  $Question $hint").Trim()
    if (-not $a) { return $Default }
    return ($a -match '^(y|yes)$')
}
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Has([string]$Cmd) { [bool](Get-Command $Cmd -ErrorAction SilentlyContinue) }
function Quiet([scriptblock]$Body) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $out = & $Body 2>&1 | ForEach-Object { "$_" }; return [pscustomobject]@{ code = $LASTEXITCODE; out = ($out -join "`n") } }
    catch { return [pscustomobject]@{ code = -1; out = $_.Exception.Message } }
    finally { $ErrorActionPreference = $old }
}
# Run one of this repo's scripts in a PowerShell of its own; its output is shown. Returns the exit code.
function Run-Script([string]$Path, $Named) {
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Path)
    foreach ($k in $Named.Keys) { if ($Named[$k] -is [bool]) { if ($Named[$k]) { $a += "-$k" } } else { $a += @("-$k", [string]$Named[$k]) } }
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & powershell @a | Out-Host; return $LASTEXITCODE } finally { $ErrorActionPreference = $old }
}

# --- where things go -------------------------------------------------------------------------------------------------
if ($ConfigPath) { $env:GGF_CONFIG = $ConfigPath }
$cfgFile = if ($env:GGF_CONFIG) { $env:GGF_CONFIG } else { Join-Path $env:USERPROFILE '.godot-game-factory\config.json' }
$cfgNow = if (Test-Path -LiteralPath $cfgFile) { [IO.File]::ReadAllText($cfgFile) | ConvertFrom-Json } else { $null }
if (-not $Root -and $env:GGF_ROOT) { $Root = $env:GGF_ROOT }
if (-not $Root -and $cfgNow -and $cfgNow.root) { $Root = [string]$cfgNow.root }
if (-not $Root) {
    $def = Join-Path $env:USERPROFILE 'GodotWork'
    $Root = if ($interactive -and -not $Yes) { $r = (Read-Host "  Machine root for godot-game-factory, the engine, games, builds and recordings [$def]").Trim(); if ($r) { $r } else { $def } } else { $def }
}
$Root = [IO.Path]::GetFullPath($Root.TrimEnd('\'))
$env:GGF_ROOT = $Root
$setupDir = Join-Path $Root '.setup'
New-Item -ItemType Directory -Force $setupDir | Out-Null
try { Start-Transcript -Path (Join-Path $setupDir 'setup.log') -Append | Out-Null } catch { }
Write-Host "godot-game-factory setup: root $Root$(if ($DryRun) { ' (dry run: nothing is installed, downloaded or changed outside the root and the scratch folders given)' })"

if (-not $Org -and $cfgNow -and $cfgNow.PSObject.Properties['github_org']) { $Org = [string]$cfgNow.github_org }
if (-not $Org -and $interactive -and -not $Yes) { $Org = (Read-Host '  GitHub organisation (or user) that owns godot-game-factory and the godot-game-<slug> repos').Trim() }
if (-not $Agent -and $cfgNow -and $cfgNow.PSObject.Properties['agents'] -and @($cfgNow.agents).Count) {
    $Agent = if (@($cfgNow.agents).Count -ge 2) { 'both' } else { [string]@($cfgNow.agents)[0] }
}
$useCodex = $Agent -in 'codex', 'both'
Write-Host "  agent: $(if ($Agent) { $Agent } else { 'auto (what is installed)' })"

# --- 1. hardware -------------------------------------------------------------------------------------------------------
Write-Host "1. hardware (minimums: Windows 11, 8 threads, 16 GB RAM, 100 GB free, a GPU with Vulkan)"
$os = Get-CimInstance Win32_OperatingSystem
$build = [int]$os.BuildNumber
if ($build -ge 22000) { Item PASS 'Windows' "$($os.Caption) build $build" } else { Item TODO 'Windows' "$($os.Caption) build $build" 'Windows 11 is required' }
$cs = Get-CimInstance Win32_ComputerSystem
$ram = [math]::Round($cs.TotalPhysicalMemory / 1GB)
$cores = [int]$cs.NumberOfLogicalProcessors
if ($cores -ge 8) { Item PASS 'CPU' "$cores logical cores" } else { Item TODO 'CPU' "$cores logical cores" 'at least 8 logical cores (the job limiter then allows one job at a time)' }
if ($ram -ge 32) { Item PASS 'Memory' "$ram GB" } elseif ($ram -ge 16) { Item PASS 'Memory' "$ram GB (32 GB recommended; fewer parallel jobs)" } else { Item TODO 'Memory' "$ram GB" 'at least 16 GB RAM (32 GB recommended)' }
$drive = (Split-Path -Qualifier $Root).TrimEnd(':')
$free = [math]::Round((Get-PSDrive -Name $drive).Free / 1GB)
if ($free -ge 100) { Item PASS 'Free disk' "$free GB on ${drive}:" }
else { Item TODO 'Free disk' "$free GB on ${drive}:" "free space or pick a roomier drive (-Root <drive>:\GodotWork): 100 GB" }
$gpus = @(Get-CimInstance Win32_VideoController | Where-Object { $_.Name -notmatch 'Microsoft Basic|Remote|Virtual' })
Item $(if ($gpus) { 'PASS' } else { 'TODO' }) 'GPU' $(if ($gpus) { ($gpus.Name -join ', ') } else { 'no display adapter found' }) 'a GPU with Vulkan and a current driver (plays and recordings are rendered)'

# --- 2. software -----------------------------------------------------------------------------------------------------
Write-Host "2. software (winget)"
function Test-Python { foreach ($c in @('py -3.12', 'python')) { $r = Quiet { Invoke-Expression "$c -c `"import sys; print(sys.version_info[1])`"" }; if ($r.code -eq 0 -and $r.out -match '^\d+$' -and [int]$r.out -ge 12) { return $true } }; return $false }
$packages = @(
    @{ id = 'Git.Git'; name = 'Git'; test = { Has git } },
    @{ id = 'GitHub.GitLFS'; name = 'Git LFS'; test = { (Has git) -and (Quiet { git lfs version }).code -eq 0 } },
    @{ id = 'GitHub.cli'; name = 'GitHub CLI'; test = { Has gh } },
    @{ id = 'Python.Python.3.12'; name = 'Python 3.12'; test = { Test-Python } },
    @{ id = 'OpenAI.Codex'; name = 'Codex CLI (OpenAI)'; agent = 'codex'; test = { Has codex } }
)
$packages = @($packages | Where-Object { -not $_.agent -or ($_.agent -eq 'codex' -and $useCodex) })
$missing = @($packages | Where-Object { -not (& $_.test) })
foreach ($p in $packages) { if ($missing -notcontains $p) { Item PASS $p.name 'installed' } }
if ($missing) {
    $hasWinget = Has winget
    if (-not $hasWinget) { Item TODO 'winget' 'not found' 'install "App Installer" from the Microsoft Store, then run setup again' }
    Write-Host ("  missing: " + (($missing | ForEach-Object { $_.name }) -join '; '))
    $go = $hasWinget -and -not $DryRun -and (Ask "Install these with winget (accepting each package's licence; some show a UAC prompt)?" $true)
    foreach ($p in $missing) {
        if (-not $go) { Item TODO $p.name $(if ($DryRun) { 'missing (dry run)' } else { 'missing' }) "winget install -e --id $($p.id)"; continue }
        Write-Host "  winget install $($p.id) ..."
        & winget @('install', '-e', '--id', $p.id, '--accept-package-agreements', '--accept-source-agreements', '--silent') | Out-Host
        Refresh-Path
        if (& $p.test) { Item PASS $p.name 'installed now' } else { Item TODO $p.name 'install did not complete' "winget install -e --id $($p.id) (or run setup again; a new terminal may be needed)" }
    }
}

# --- 3. GitHub sign-in and git identity ------------------------------------------------------------------------------
Write-Host "3. GitHub and git"
$ghOk = $false
if (Has gh) {
    $ghOk = (Quiet { gh auth status }).code -eq 0
    # Only people who push the game repos sign in: a game that is built and submitted from this PC stays on it (it
    # ships in the dataset zip), and needs no GitHub account.
    if (-not $ghOk -and -not $DryRun -and $interactive -and -not $Yes) {
        if (Ask 'Sign in to GitHub? Only people who push game repos to the org need it' $false) {
            Write-Host '  GitHub sign-in: a browser page opens; sign in with the account that is a member of the org.'
            & gh auth login --hostname github.com --git-protocol https --web
            $ghOk = (Quiet { gh auth status }).code -eq 0
        }
    }
    if ($ghOk) { if (-not $DryRun) { Quiet { gh auth setup-git } | Out-Null }; Item PASS 'GitHub sign-in' (Quiet { gh api user --jq .login }).out }
    else { Item INFO 'GitHub sign-in' 'not signed in' 'not needed to build and submit a game; people who push game repos: gh auth login --web' }
} else { Item INFO 'GitHub sign-in' 'no GitHub CLI' 'not needed to build and submit a game; people who push game repos: install it (step 2), then run setup again' }
if (Has git) {
    foreach ($k in 'user.name', 'user.email') {
        $v = (Quiet { git config --global --get $k }).out
        if (-not $v -and -not $DryRun -and $interactive -and -not $Yes) { $v = (Read-Host "  git $k (for your commits)").Trim(); if ($v) { Quiet { git config --global $k $v } | Out-Null } }
        if ($v) { Item PASS "git $k" 'set' } else { Item TODO "git $k" 'not set' "git config --global $k `"<value>`"" }
    }
}
if (-not $Org) { Item TODO 'GitHub org' 'not set' 'run setup again with -Org <org> (the organisation or user that owns godot-game-factory)' }

# --- 4. godot-game-factory: the engine, bootstrap, the Android toolchain -----------------------------------------------
Write-Host "4. godot-game-factory"
$here = Split-Path $PSScriptRoot -Parent
$inClone = (Test-Path (Join-Path $here 'machine\bootstrap.ps1')) -and (Test-Path (Join-Path $here '.git'))
$repo = if ($inClone) { $here } else { Join-Path $Root 'godot-game-factory' }
if (-not (Test-Path (Join-Path $repo 'machine\bootstrap.ps1'))) {
    $src = if ($RepoUrl) { $RepoUrl } elseif ($Org) { "https://github.com/$Org/godot-game-factory.git" } else { $null }
    if (-not $src -or -not (Has git)) { Item TODO 'godot-game-factory clone' "not at $repo" 'needs git and the org (steps above); then run setup again' }
    elseif ($DryRun -and -not $RepoUrl) { Item TODO 'godot-game-factory clone' "would clone $src into $repo (dry run)" '' }
    else {
        Write-Host "  cloning $src into $repo ..."
        $r = Quiet { git clone --quiet $src $repo }
        if ($r.code -eq 0) { Item PASS 'godot-game-factory clone' $repo } else { Item TODO 'godot-game-factory clone' "git clone failed: $($r.out)" "check that -Org is right and you are online, then: git clone $src $repo (a private copy of the repo needs gh auth login --web first)" }
    }
} else { Item PASS 'godot-game-factory clone' $repo }
$haveRepo = Test-Path (Join-Path $repo 'machine\bootstrap.ps1')

# The engine: self-contained under the root, so a dry run only says whether it is there.
if ($haveRepo) {
    . (Join-Path $repo 'machine\lib\ggf-root.ps1')
    $eng = Get-GGFEngine
    if ($DryRun) {
        $exe = Get-GGFGodot -ErrorAction SilentlyContinue
        if ($exe) { Item PASS "Godot $($eng.version)" $exe } else { Item TODO "Godot $($eng.version)" 'not installed (dry run)' 'machine\get-godot.ps1' }
    } else {
        Write-Host "  machine\get-godot.ps1 ..."
        $code = Run-Script (Join-Path $repo 'machine\get-godot.ps1') @{ Root = $Root }
        if ($code -eq 0) { Item PASS "Godot $($eng.version)" (Join-Path $Root "godot\$($eng.version)") } else { Item TODO "Godot $($eng.version)" "get-godot.ps1 exit $code" 'read its output above, fix, run setup again' }
    }
}

# A dry run changes nothing outside the root, and bootstrap.ps1 writes the config, the hooks dir, the skills and (after
# its question) the agents' settings: in a dry run it runs only when every one of those is given (a scratch home).
$notGiven = @('ConfigPath', 'ClaudeDir', 'CodexDir', 'AgentsSkillsDir', 'HooksDir' | Where-Object { -not $PSBoundParameters.ContainsKey($_) })
if ($DryRun -and $notGiven) { Item INFO 'bootstrap.ps1' "not run: a dry run runs it only with every scratch folder given (missing -$($notGiven -join ', -'))" }
elseif ($haveRepo) {
    $ba = [ordered]@{ Root = $Root; ClaudeDir = $ClaudeDir }
    if ($Agent) { $ba.Agent = $Agent }
    if ($CodexDir) { $ba.CodexDir = $CodexDir }
    if ($AgentsSkillsDir) { $ba.AgentsSkillsDir = $AgentsSkillsDir }
    if ($HooksDir) { $ba.HooksDir = $HooksDir }
    if ($Org) { $ba.Org = $Org }
    if ($env:GGF_CONFIG) { $ba.ConfigPath = $env:GGF_CONFIG }
    if ($Yes) { $ba.Yes = $true }
    if ($CloneGames -and -not $DryRun) { $ba.CloneGames = $true }
    if ($SkipFfmpeg -or $DryRun) { $ba.SkipFfmpeg = $true }
    Write-Host "  machine\bootstrap.ps1 ..."
    $code = Run-Script (Join-Path $repo 'machine\bootstrap.ps1') $ba
    if ($code -eq 0) { Item PASS 'bootstrap.ps1' 'done (its warnings are above)' } else { Item TODO 'bootstrap.ps1' "exit $code" 'read the bootstrap output above, fix, run setup again' }
}

# The Android toolchain: only with -Android. Without it a mobile game is still made, played, recorded and task-checked;
# only its APK is skipped (its release needs the APK).
if ($haveRepo -and $Android) {
    if ($DryRun) {
        if (Get-GGFAndroid) { Item PASS 'Android toolchain' (Get-GGFAndroidHome) } else { Item TODO 'Android toolchain' 'not installed (dry run)' 'machine\get-android.ps1' }
    } else {
        Write-Host "  machine\get-android.ps1 ..."
        $aa = [ordered]@{ Root = $Root }
        if ($env:GGF_CONFIG) { $aa.ConfigPath = $env:GGF_CONFIG }
        if ($Yes) { $aa.Yes = $true }
        $code = Run-Script (Join-Path $repo 'machine\get-android.ps1') $aa
        if ($code -eq 0) { Item PASS 'Android toolchain' (Get-GGFAndroidHome) } else { Item TODO 'Android toolchain' "get-android.ps1 exit $code" 'read its output above, fix, then machine\get-android.ps1 (or setup again with -Android)' }
    }
} elseif ($haveRepo) {
    if (Get-GGFAndroid) { Item PASS 'Android toolchain' (Get-GGFAndroidHome) }
    else { Item INFO 'Android toolchain' 'not installed: mobile games still work, except the APK their release needs' 'setup.ps1 -Android (or machine\get-android.ps1)' }
}

# --- 5. what cannot be scripted -------------------------------------------------------------------------------------------
Write-Host "5. sign-ins only you can do"
if ($Agent -in '', 'claude', 'both') { Item INFO 'Claude Code sign-in' 'run claude once (or open the desktop app) and sign in with your account; not detectable' }
if ($useCodex) {
    if (-not (Has codex)) { Item TODO 'Codex sign-in' 'needs the Codex CLI' 'install it (step 2), then run setup again' }
    elseif ((Quiet { codex login status }).code -eq 0) { Item PASS 'Codex sign-in' ((Quiet { codex login status }).out -split "`n")[0] }
    else { Item TODO 'Codex sign-in' 'not signed in' 'codex login (or codex login --device-auth), then run setup again' }
}
Item INFO 'First session' "start Claude Code (claude) or Codex (codex) in $Root and paste the brief (docs/new-machine.md, 'The first session')"

# --- check + summary -----------------------------------------------------------------------------------------------------
$check = Join-Path $repo 'machine\check.ps1'
if (Test-Path $check) {
    Write-Host "6. machine\check.ps1"
    $json = Join-Path $setupDir 'check.json'
    $ca = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $check, '-Root', $Root, '-ClaudeDir', $ClaudeDir, '-Json', $json)
    if ($CodexDir) { $ca += @('-CodexDir', $CodexDir) }
    if ($AgentsSkillsDir) { $ca += @('-AgentsSkillsDir', $AgentsSkillsDir) }
    if ($HooksDir) { $ca += @('-HooksDir', $HooksDir) }
    if ($env:GGF_CONFIG) { $ca += @('-ConfigPath', $env:GGF_CONFIG) }
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & powershell @ca | Out-Null
    $ErrorActionPreference = $old
    if (Test-Path $json) {
        $cr = [IO.File]::ReadAllText($json) | ConvertFrom-Json
        # check.ps1 rows that setup already reported above (same subject under setup's name)
        $same = @{ 'GitHub CLI' = 'GitHub sign-in'; 'Memory' = 'Memory'; 'Free disk' = 'Free disk'; 'GPU' = 'GPU'; 'Codex' = 'Codex sign-in' }
        if ($haveRepo) { $same["Godot $($eng.version)"] = "Godot $($eng.version)"; $same['Godot export templates'] = "Godot $($eng.version)" }
        $known = @($items | ForEach-Object { $_.what })
        foreach ($r in $cr.results) {
            if ($r.status -eq 'PASS') { continue }
            if ($same.ContainsKey($r.check) -and $known -contains $same[$r.check]) { continue }
            if ($r.check -like 'Android *' -and $known -contains 'Android toolchain') { continue }
            $st = if ($r.status -eq 'FAIL') { 'TODO' } else { 'INFO' }
            Item $st "check: $($r.check)" $r.detail $r.fix
        }
        Item $(if ($cr.fail -eq 0) { 'PASS' } else { 'TODO' }) 'check.ps1' "$($cr.fail) FAIL, $($cr.warn) WARN (full report: $json)"
    }
}
Write-Host ""
Write-Host "godot-game-factory setup summary (root $Root)"
$todo = @($items | Where-Object status -eq 'TODO')
foreach ($i in $items | Where-Object { $_.status -in 'PASS', 'TODO' }) {
    Write-Host ("  {0}  {1,-36} {2}" -f $i.status, $i.what, $i.detail) -ForegroundColor $(if ($i.status -eq 'PASS') { 'Green' } else { 'Yellow' })
    if ($i.status -eq 'TODO' -and $i.todo) { Write-Host ("        -> {0}" -f $i.todo) -ForegroundColor DarkGray }
}
foreach ($i in $items | Where-Object status -eq 'INFO') { Write-Host ("  note  {0}: {1}{2}" -f $i.what, $i.detail, $(if ($i.todo) { " ($($i.todo))" } else { '' })) -ForegroundColor DarkGray }
Write-Host ""
if ($todo) { Write-Host "$($todo.Count) TODO. Do them, then run setup again: it picks up where it stopped. Log: $setupDir\setup.log" -ForegroundColor Yellow }
else { Write-Host "Ready. Next: the first session (docs/new-machine.md, 'The first session'). Log: $setupDir\setup.log" -ForegroundColor Green }
[IO.File]::WriteAllText((Join-Path $setupDir 'summary.json'), ([ordered]@{ time = (Get-Date).ToString('o'); root = $Root; todo = $todo.Count; items = $items } | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
try { Stop-Transcript | Out-Null } catch { }
exit $todo.Count
