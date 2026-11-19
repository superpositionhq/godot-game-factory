<#
.SYNOPSIS
  Check that this machine can run godot-game-factory sessions; prints a PASS / WARN / FAIL report. Read-only.
.DESCRIPTION
  Toolchain: the pinned Godot editor (machine\godot.json) and its export templates, git + Git LFS, gh (logged in, can
  see the org's repos), Python, ffmpeg. Space: free disk on the root's drive, memory. Agents (the config's "agents":
  Claude Code and/or Codex): installed, signed in where it can tell. Setup done by bootstrap.ps1: config, job slots
  (and where each count comes from), godot-heavy.ps1, the recording hooks and each agent's wiring (Claude Code
  settings.json; Codex hooks.json + trust), skills, root CLAUDE.md / AGENTS.md, and each game repo's post-commit hook
  (the commit recorder). The Android toolchain (machine\get-android.ps1), piece by piece: the JDK, the Android SDK
  packages, the keystores, the editor settings an export reads. A missing piece of it is a WARN, never a FAIL: mobile
  games are still made, played, recorded and task-checked; only their APK is skipped, which their release needs.
  Exit code = number of FAILs. -Json writes the report as JSON too (the only thing this script ever writes).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File machine\check.ps1
  powershell -ExecutionPolicy Bypass -File machine\check.ps1 -Root C:\ggf-test\GodotWork -ClaudeDir C:\ggf-test\home\.claude -CodexDir C:\ggf-test\home\.codex `
      -AgentsSkillsDir C:\ggf-test\home\.agents\skills -HooksDir C:\ggf-test\home\.godot-game-factory\hooks `
      -ConfigPath C:\ggf-test\home\.godot-game-factory\config.json -Json C:\ggf-test\check.json
#>
param(
    [string]$Root,
    [string]$ClaudeDir = (Join-Path $env:USERPROFILE '.claude'),
    # default: CODEX_HOME / %USERPROFILE%\.codex
    [string]$CodexDir,
    [string]$AgentsSkillsDir = (Join-Path $env:USERPROFILE '.agents\skills'),
    # default: config hooks_dir
    [string]$HooksDir,
    [string]$ConfigPath,
    # default: the config's github_org (GGF_ORG)
    [string]$Org,
    # WARN below this, FAIL below a third of it
    [int]$MinFreeGB = 100,
    [string]$Json
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot 'lib\ggf-root.ps1')
. (Join-Path $PSScriptRoot 'lib\codex-hooks.ps1')
if ($ConfigPath) { $env:GGF_CONFIG = $ConfigPath }
if ($Root) { $env:GGF_ROOT = $Root }
$cfg = Get-GGFConfig
$Root = $cfg.root
if (-not $CodexDir) { $CodexDir = Get-GGFCodexHome }
if (-not $HooksDir) { $HooksDir = Get-GGFHooksDir $cfg }
$HooksDir = [IO.Path]::GetFullPath($HooksDir)
$Agents = @(Get-GGFAgents $cfg)
if (-not $Org) { $Org = Get-GGFOrg $cfg }
$eng = Get-GGFEngine
$results = New-Object Collections.Generic.List[object]

function Add-Result([string]$Status, [string]$Check, [string]$Detail, [string]$Fix = '') {
    $results.Add([pscustomobject]@{ status = $Status; check = $Check; detail = $Detail; fix = $Fix })
}
function Try-Check([string]$Check, [scriptblock]$Body) {
    try { & $Body } catch { Add-Result FAIL $Check "check errored: $($_.Exception.Message)" }
}
function Run([string]$Exe, [string[]]$ArgList) {
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { $out = & $Exe @ArgList 2>&1 | ForEach-Object { "$_" }; return [pscustomobject]@{ code = $LASTEXITCODE; out = ($out -join "`n") } }
    catch { return [pscustomobject]@{ code = -1; out = $_.Exception.Message } }
    finally { $ErrorActionPreference = $old }
}

# --- toolchain ------------------------------------------------------------------------------------------------------
$godotName = "Godot $($eng.version)"
Try-Check $godotName {
    $exe = Get-GGFGodot -Cfg $cfg -ErrorAction SilentlyContinue
    if (-not $exe) { Add-Result FAIL $godotName "no editor at $(Join-Path (Get-GGFGodotDir $cfg) $eng.exe)" 'machine\get-godot.ps1 (or name the editor exe in "godot" in the config)'; return }
    $console = Get-GGFGodot -Console -Cfg $cfg -ErrorAction SilentlyContinue
    if ($console -eq $exe) { Add-Result WARN $godotName "$exe has no console wrapper beside it (tools then get no output or exit code from a run)" 'machine\get-godot.ps1 -Force'; return }
    $v = (Run $console @('--version')).out.Trim()
    $want = "$($eng.version).$($eng.flavor)"
    if ($v -like "$want*") { Add-Result PASS $godotName "$v at $exe" }
    else { Add-Result FAIL $godotName "$exe is version $v, the factory pins $want" 'machine\get-godot.ps1 (the pinned version into <root>\godot\<version>), and remove "godot" from the config' }
}
Try-Check 'Godot export templates' {
    if (-not (Get-GGFGodot -Cfg $cfg -ErrorAction SilentlyContinue)) { Add-Result FAIL 'Godot export templates' 'no editor, so no templates' 'machine\get-godot.ps1'; return }
    $ed = Get-GGFEditorData $cfg
    if (-not $ed) { Add-Result WARN 'Godot export templates' 'the editor is not self-contained (no ._sc_ beside it): its templates and settings are in %APPDATA%, where this check does not look' 'machine\get-godot.ps1 installs a self-contained editor'; return }
    $t = Join-Path $ed "export_templates\$($eng.templates)"
    $ver = Join-Path $t 'version.txt'
    if (-not ((Test-Path -LiteralPath $ver) -and [IO.File]::ReadAllText($ver).Trim() -eq $eng.templates)) { Add-Result FAIL 'Godot export templates' "no $($eng.templates) templates in $t" 'machine\get-godot.ps1'; return }
    $need = @('windows_release_x86_64.exe', 'android_release.apk', 'android_source.zip')
    $miss = @($need | Where-Object { -not (Test-Path -LiteralPath (Join-Path $t $_)) })
    if ($miss) { Add-Result FAIL 'Godot export templates' "$t lacks $($miss -join ', ')" 'machine\get-godot.ps1 -Force' }
    else { Add-Result PASS 'Godot export templates' "$($eng.templates) at $t (Windows and Android)" }
}
Try-Check 'git' {
    $r = Run git @('--version')
    if ($r.code -eq 0) { Add-Result PASS 'git' $r.out } else { Add-Result FAIL 'git' 'not found' 'winget install Git.Git' }
}
Try-Check 'Git LFS' {
    $r = Run git @('lfs', 'version')
    if ($r.code -ne 0) { Add-Result FAIL 'Git LFS' 'git lfs not found' 'winget install GitHub.GitLFS'; return }
    $f = Run git @('config', '--get', 'filter.lfs.process')   # global or system (Git for Windows sets it system-wide)
    if ($f.out) { Add-Result PASS 'Git LFS' ($r.out -split "`n")[0] } else { Add-Result FAIL 'Git LFS' 'installed but filters not set up' 'git lfs install --skip-repo (bootstrap.ps1 does this)' }
}
Try-Check 'GitHub CLI' {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Add-Result FAIL 'GitHub CLI' 'gh not found' 'winget install GitHub.cli'; return }
    $login = Run gh @('api', 'user', '--jq', '.login')
    # Not a FAIL: building and submitting a game needs no GitHub account (the game stays on the PC, in the dataset zip).
    if ($login.code -ne 0) { Add-Result WARN 'GitHub CLI' 'not logged in' 'only people who push game repos to the org need it: gh auth login (GitHub.com, HTTPS, browser)'; return }
    if (-not $Org) { Add-Result FAIL 'GitHub org' "logged in as $($login.out); no github_org in the config" 'machine/bootstrap.ps1 -Org <GitHub org or user that owns godot-game-factory and the game repos>'; return }
    $v = Run gh @('repo', 'view', "$Org/godot-game-factory", '--json', 'name,visibility', '--jq', '.visibility')
    if ($v.code -ne 0) { Add-Result FAIL "GitHub access to $Org" "logged in as $($login.out), but cannot see $Org/godot-game-factory" "ask an $Org owner to add the account (needs repo create rights for godot-game-<slug> repos)"; return }
    $n = Run gh @('repo', 'list', $Org, '--limit', '500', '--json', 'name', '--jq', '.[].name')
    $games = @(($n.out -split "`n") | Where-Object { $_ -match '^godot-game-.' -and $_ -ne 'godot-game-factory' }).Count
    Add-Result PASS "GitHub access to $Org" "logged in as $($login.out); godot-game-* repos visible: $games"
}
Try-Check 'Python' {
    $cmd = Get-GGFPython
    if (-not $cmd) { Add-Result FAIL 'Python' 'no python.exe (the Microsoft Store stub does not count)' 'winget install Python.Python.3.12 (validate-game, task-check, task-try and sfx tools)'; return }
    $r = Run $cmd @('-c', 'import sys; print(sys.version.split()[0])')
    if ($r.code -eq 0 -and $r.out -match '^3\.(\d+)' -and [int]$Matches[1] -ge 12) { Add-Result PASS 'Python' "$($r.out) ($cmd)" }
    else { Add-Result FAIL 'Python' "unusable: $($r.out)" 'install Python 3.12+ (the task check uses os.path.isjunction, new in 3.12)' }
}
Try-Check 'ffmpeg' {
    $ff = Get-GGFFfmpeg $cfg
    if (-not $ff) { Add-Result FAIL 'ffmpeg' 'none found (GGF_FFMPEG, "ffmpeg" in the config, <root>\tools\ffmpeg-8.1.2, PATH)' 'machine\get-ffmpeg.ps1 (bootstrap.ps1 runs it)'; return }
    if (-not (Get-GGFFfprobe $cfg)) { Add-Result FAIL 'ffmpeg' "$ff has no ffprobe.exe beside it" 'machine\get-ffmpeg.ps1 -Force (the pinned build has both)'; return }
    $v = ((Run $ff @('-hide_banner', '-version')).out -split "`n")[0]
    Add-Result PASS 'ffmpeg' "$v ($ff)"
}
Try-Check 'GPU' {
    # A rendered run (a play, a recording, a task play) needs a GPU with Vulkan and a signed-in desktop; imports, exports
    # and generator scripts run headless without one.
    $gpus = @(Get-CimInstance Win32_VideoController | Where-Object { $_.Name -notmatch 'Microsoft Basic|Remote|Virtual' } | ForEach-Object { $_.Name })
    if ($gpus) { Add-Result PASS 'GPU' ($gpus -join ', ') }
    else { Add-Result WARN 'GPU' 'no display adapter found' 'plays, recordings and task plays render with Vulkan: a GPU with a current driver' }
}
Try-Check 'Free disk' {
    $drive = (Split-Path -Qualifier $Root).TrimEnd(':')
    $d = Get-PSDrive -Name $drive
    $gb = [math]::Round($d.Free / 1GB)
    if ($gb -ge $MinFreeGB) { Add-Result PASS 'Free disk' "$gb GB free on ${drive}:" }
    elseif ($gb -ge [int]($MinFreeGB / 3)) { Add-Result WARN 'Free disk' "$gb GB free on ${drive}: (want $MinFreeGB)" 'game repos with LFS, builds, recordings and packages grow' }
    else { Add-Result FAIL 'Free disk' "$gb GB free on ${drive}:" "free space; under $([int]($MinFreeGB/3)) GB builds and packaging fail" }
}
Try-Check 'Memory' {
    $gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    if ($gb -ge 30) { Add-Result PASS 'Memory' "$gb GB" } else { Add-Result WARN 'Memory' "$gb GB" 'fewer heavy slots fit: the slot formula sizes them from RAM (check Job slots below)' }
}

# --- setup done by bootstrap.ps1 ---------------------------------------------------------------------------------------
Try-Check 'Config' {
    $p = Get-GGFConfigPath
    if (Test-Path $p) { Add-Result PASS 'Config' "$p (root $Root)" }
    elseif ($Root -eq (Join-Path $env:USERPROFILE 'GodotWork')) { Add-Result WARN 'Config' "no $p; using the default root $Root" 'machine\bootstrap.ps1 writes it' }
    else { Add-Result FAIL 'Config' "no $p" 'machine\bootstrap.ps1' }
}
Try-Check 'Job slots' {
    # the slots godot-heavy.ps1 uses and where each comes from: config (set by hand), config (bootstrap) or computed
    $sp = Get-GGFSlotPlan $cfg
    $calc = Get-GGFComputedSlots
    $vl = if ($sp.gpu_vram_limit_mb -gt 0) { "$($sp.gpu_vram_limit_mb) MB (config)" } else { 'half the VRAM' }
    $detail = "heavy_slots $($sp.heavy_slots) [$($sp.heavy_slots_source)], gpu_slots $($sp.gpu_slots) [$($sp.gpu_slots_source)], " +
        "VRAM limit $vl; formula gives $($calc.heavy_slots)/$($calc.gpu_slots) ($($calc.hardware.logical_cores) threads, " +
        "$($calc.hardware.ram_gb) GB RAM, $($calc.hardware.vram_mb) MB VRAM)"
    $others = @(Get-GGFOtherFactoryRoots)
    if ($others) { $detail += "; slots shared with the factory at $($others -join ' and at ') (same machine-wide mutexes)" }
    # with one general slot (what the formula gives a 16 GB PC) a GPU job always holds it: nothing to change then
    if ($sp.gpu_slots -ge $sp.heavy_slots -and $sp.heavy_slots -gt 1) {
        Add-Result WARN 'Job slots' "$detail; GPU jobs also take a general slot, so gpu_slots >= heavy_slots can leave no slot for imports and exports" 'lower gpu_slots or raise heavy_slots in the config'
    } else { Add-Result PASS 'Job slots' $detail }
}
Try-Check 'GodotWork layout' {
    $missing = @('games', 'tasks', 'builds', 'recordings', '.recording', 'deliverables', 'asset-library', 'tools') | Where-Object { -not (Test-Path (Join-Path $Root $_)) }
    # the release builds' private clones (tools/godot-pipeline/build.ps1)
    $ggb = @(Join-Path $cfg.ggb 'src') | Where-Object { -not (Test-Path $_) }
    if (-not $missing -and -not $ggb) { Add-Result PASS 'GodotWork layout' "$Root + $($cfg.ggb)" } else { Add-Result FAIL 'GodotWork layout' "missing: $(@($missing) + @($ggb) -join ', ')" 'machine\bootstrap.ps1' }
}
Try-Check 'godot-game-factory clone' {
    $exp = Join-Path $Root 'godot-game-factory'
    if ([IO.Path]::GetFullPath($repo).TrimEnd('\') -eq $exp) { Add-Result PASS 'godot-game-factory clone' $repo }
    else { Add-Result WARN 'godot-game-factory clone' "running from $repo, briefs and docs assume $exp" "git clone https://github.com/$(if ($Org) { $Org } else { '<org>' })/godot-game-factory $exp" }
}
function Same-File([string]$A, [string]$B) { (Test-Path $A) -and (Test-Path $B) -and ((Get-FileHash $A).Hash -eq (Get-FileHash $B).Hash) }
Try-Check 'godot-heavy.ps1' {
    $dst = Join-Path $Root 'tools\godot-heavy.ps1'
    $lib = Join-Path $Root 'tools\ggf-root.ps1'
    $pin = Join-Path $Root 'tools\godot.json'
    if ((Same-File (Join-Path $PSScriptRoot 'tools\godot-heavy.ps1') $dst) -and (Same-File (Join-Path $PSScriptRoot 'lib\ggf-root.ps1') $lib) -and (Same-File (Join-Path $PSScriptRoot 'godot.json') $pin)) { Add-Result PASS 'godot-heavy.ps1' $dst }
    elseif ((Test-Path $dst) -and (Test-Path $lib) -and (Test-Path $pin)) { Add-Result WARN 'godot-heavy.ps1' "$dst, or ggf-root.ps1 or godot.json next to it, differs from the repo copy" 'machine\bootstrap.ps1 (keeps a backup)' }
    else { Add-Result FAIL 'godot-heavy.ps1' "missing $(@($dst, $lib, $pin | Where-Object { -not (Test-Path $_) }) -join ', ')" 'machine\bootstrap.ps1' }   # without ggf-root.ps1 next to it the limiter does not start
}
Try-Check 'Recording hooks' {
    $hd = $HooksDir
    $files = @('record-godot-action.ps1', 'record-godot-commit.ps1')
    $diff = @($files | Where-Object { -not (Same-File (Join-Path $PSScriptRoot "hooks\$_") (Join-Path $hd $_)) })
    $absent = @($files | Where-Object { -not (Test-Path (Join-Path $hd $_)) })
    $lib = Test-Path (Join-Path $hd 'ggf-root.ps1')
    if ($absent -or -not $lib) { Add-Result FAIL 'Recording hooks' "missing in ${hd}: $(@($absent) + @($(if (-not $lib) { 'ggf-root.ps1' })) -join ', ')" 'machine\bootstrap.ps1'; return }
    if (-not (Same-File (Join-Path $PSScriptRoot 'lib\ggf-root.ps1') (Join-Path $hd 'ggf-root.ps1'))) { $diff += 'ggf-root.ps1' }   # the hooks run with this copy
    if ($diff) { Add-Result WARN 'Recording hooks' "$hd`: older than the repo copy ($($diff -join ', '))" 'machine\bootstrap.ps1 (backs up the old copies)'; return }
    Add-Result PASS 'Recording hooks' $hd
}
# The events each agent must run record-godot-action.ps1 on (Codex has no PostToolUseFailure), each with the command
# bootstrap.ps1 writes for this hooks dir (hooks\settings-hooks.json, hooks\codex-hooks.json): a handler that runs
# another copy (a hooks dir that moved) or an older command line records nothing.
function Get-WiredEvents($Obj, [string[]]$Events, [string]$Fragment) {
    $frag = [IO.File]::ReadAllText((Join-Path $PSScriptRoot "hooks\$Fragment")).Replace('{{HOOKS_DIR}}', ($HooksDir -replace '\\', '/')) | ConvertFrom-Json
    $w = @()
    foreach ($ev in $Events) {
        $want = [string]@(@($frag.hooks.$ev)[0].hooks)[0].command
        $cmds = @($Obj.hooks.$ev | ForEach-Object { $_.hooks } | ForEach-Object { [string]$_.command })
        if ($cmds -contains $want) { $w += $ev }
    }
    return $w
}
if ($Agents -contains 'claude') {
    Try-Check 'Claude Code' {
        $cmd = Get-Command claude -ErrorAction SilentlyContinue
        $v = if ($cmd) { (Run $cmd.Source @('--version')).out } else { $null }
        if ($cmd) { Add-Result PASS 'Claude Code' "$v ($($cmd.Source)); sign-in is not detectable: run claude once and sign in" }
        else { Add-Result WARN 'Claude Code' 'claude not on PATH (the desktop app alone also works)' 'install Claude Code (https://claude.com/claude-code) or the Claude desktop app, then sign in' }
    }
    Try-Check 'Claude Code hooks' {
        $sp = Join-Path $ClaudeDir 'settings.json'
        $events = @('PostToolUse', 'PostToolUseFailure', 'Stop', 'UserPromptSubmit', 'SessionEnd')
        $wired = if (Test-Path $sp) { @(Get-WiredEvents ([IO.File]::ReadAllText($sp) | ConvertFrom-Json) $events 'settings-hooks.json') } else { @() }
        if ($wired.Count -eq $events.Count) { Add-Result PASS 'Claude Code hooks' "$sp wires $($events -join ', ')" }
        else { Add-Result FAIL 'Claude Code hooks' "$sp runs $HooksDir\record-godot-action.ps1 with bootstrap.ps1's command line on: $(if ($wired) { $wired -join ', ' } else { 'none' })" 'machine\bootstrap.ps1 -Agent claude (asks before installing them)' }
        # the recording keeps the reasoning summaries only when Claude Code saves them in the transcript
        $st = if (Test-Path $sp) { [IO.File]::ReadAllText($sp) | ConvertFrom-Json } else { $null }
        $off = @('showThinkingSummaries', 'alwaysThinkingEnabled' | Where-Object { -not $st -or -not $st.PSObject.Properties[$_] -or $st.$_ -ne $true })
        if (-not $off) { Add-Result PASS 'Claude Code reasoning summaries' "${sp}: showThinkingSummaries and alwaysThinkingEnabled are on" }
        else { Add-Result FAIL 'Claude Code reasoning summaries' "${sp}: not on: $($off -join ', ')" 'machine\bootstrap.ps1 -Agent claude (sets both to true)' }
    }
}
if ($Agents -contains 'codex') {
    Try-Check 'Codex' {
        $cmd = Get-Command codex -ErrorAction SilentlyContinue
        if (-not $cmd) { Add-Result FAIL 'Codex' 'codex not on PATH' 'winget install -e --id OpenAI.Codex (or npm install -g @openai/codex), then codex login'; return }
        $v = (Run $cmd.Source @('--version')).out
        $s = Run $cmd.Source @('login', 'status')   # exit 0 and "Logged in using ..." when signed in
        if ($s.code -eq 0) { Add-Result PASS 'Codex' "$v; $(($s.out -split "`n")[0])" }
        else { Add-Result FAIL 'Codex' "$v; not signed in" 'codex login (ChatGPT account in the browser; or --device-auth)' }
    }
    Try-Check 'Codex hooks' {
        $hp = Join-Path $CodexDir 'hooks.json'
        $events = @('PostToolUse', 'Stop', 'SubagentStop', 'UserPromptSubmit', 'SessionEnd')
        $h = if (Test-Path $hp) { [IO.File]::ReadAllText($hp) | ConvertFrom-Json } else { $null }
        $wired = if ($h) { @(Get-WiredEvents $h $events 'codex-hooks.json') } else { @() }
        if ($wired.Count -ne $events.Count) { Add-Result FAIL 'Codex hooks' "$hp runs $HooksDir\record-godot-action.ps1 with bootstrap.ps1's command line on: $(if ($wired) { $wired -join ', ' } else { 'none' })" 'machine\bootstrap.ps1 -Agent codex (asks before installing them)'; return }
        # an untrusted or changed hook is skipped by Codex without a word: compare the trust entries
        $state = Get-GGFCodexTrustState (Join-Path $CodexDir 'config.toml')
        $trust = @(Get-GGFCodexHookTrust $hp $h)
        $bad = @($trust | Where-Object { $state[$_.key] -ne $_.hash -and $state["\\?\$($_.key)"] -ne $_.hash } | ForEach-Object { $_.event })
        if (-not $bad) { Add-Result PASS 'Codex hooks' "$hp wires $($events -join ', '); trusted in config.toml" }
        else { Add-Result FAIL 'Codex hooks' "wired but not trusted (Codex skips them): $($bad -join ', ')" 'machine\bootstrap.ps1 -Agent codex, or in Codex type /hooks and trust the record-godot-action.ps1 hooks' }
        $top = Get-GGFCodexTopLevel (Join-Path $CodexDir 'config.toml')
        $off = @($script:GGFCodexSummary.Keys | Where-Object { $top[$_] -ne $script:GGFCodexSummary[$_] })
        if (-not $off) { Add-Result PASS 'Codex reasoning summaries' 'config.toml: model_reasoning_summary detailed, hide_agent_reasoning false' }
        else { Add-Result FAIL 'Codex reasoning summaries' "config.toml: not set: $($off -join ', ')" 'machine\bootstrap.ps1 -Agent codex (sets both)' }
    }
}
Try-Check 'Skills' {
    $names = @(Get-ChildItem (Join-Path $repo 'skills') -Directory -Filter 'godot-*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
    if (-not $names) { Add-Result FAIL 'Skills' "no godot-* skill folders in $(Join-Path $repo 'skills')" 'a complete clone of godot-game-factory'; return }
    $where = @()
    if ($Agents -contains 'claude') { $where += , @('Claude Code', (Join-Path $ClaudeDir 'skills')) }
    if ($Agents -contains 'codex') { $where += , @('Codex', $AgentsSkillsDir) }
    $bad = @(foreach ($w in $where) { foreach ($n in $names) { if (-not (Same-File (Join-Path $repo "skills\$n\SKILL.md") (Join-Path $w[1] "$n\SKILL.md"))) { "$($w[0]): $n" } } })
    if (-not $bad) { Add-Result PASS 'Skills' "$($names -join ', ') in $(($where | ForEach-Object { $_[1] }) -join ' and ')" }
    else { Add-Result FAIL 'Skills' "missing or outdated: $($bad -join ', ')" 'machine\bootstrap.ps1' }
}
if ($Agents -contains 'claude') {
    Try-Check 'Root CLAUDE.md' {
        $p = Join-Path $Root 'CLAUDE.md'
        if ((Test-Path $p) -and ((Get-Content $p -Raw) -match '@.*godot-game-factory/CLAUDE\.md|@.*/CLAUDE\.md')) { Add-Result PASS 'Root CLAUDE.md' "$p imports the repo CLAUDE.md" }
        else { Add-Result FAIL 'Root CLAUDE.md' "$p missing or not importing godot-game-factory/CLAUDE.md" 'machine\bootstrap.ps1' }
    }
}
if ($Agents -contains 'codex') {
    Try-Check 'Root AGENTS.md' {
        $p = Join-Path $Root 'AGENTS.md'
        if ((Test-Path $p) -and ((Get-Content $p -Raw) -match [regex]::Escape((Join-Path $repo 'AGENTS.md')))) { Add-Result PASS 'Root AGENTS.md' "$p names the repo AGENTS.md" }
        else { Add-Result FAIL 'Root AGENTS.md' "$p missing or not naming $(Join-Path $repo 'AGENTS.md')" 'machine\bootstrap.ps1' }
    }
}
# A game repo's post-commit hook has the commit recorder's line (machine\install-git-hook.ps1): without it the game's
# commits go unrecorded.
Try-Check 'Game repos record commits' {
    # _-prefixed folders (e.g. _pipeline-test) are tool test projects, not game data
    $repos = @(Get-ChildItem (Join-Path $Root 'games') -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike '_*' -and (Test-Path (Join-Path $_.FullName '.git')) })
    if (-not $repos) { Add-Result PASS 'Game repos record commits' 'no game repos yet'; return }
    $missing = @()
    foreach ($r in $repos) {
        $h = Join-Path $r.FullName '.git\hooks\post-commit'
        $text = if (Test-Path $h) { [string](Get-Content $h -Raw) } else { '' }
        if ($text -notmatch 'record-godot-commit\.ps1') { $missing += $r.Name }
    }
    if (-not $missing) { Add-Result PASS 'Game repos record commits' "$($repos.Count) repo(s)" } else { Add-Result FAIL 'Game repos record commits' "no recorder in: $($missing -join ', ')" 'machine\install-git-hook.ps1 <repo> (bootstrap.ps1 does all)' }
}

# --- the Android toolchain (machine\get-android.ps1) ----------------------------------------------------------------------
# Every piece is a WARN when missing: a mobile game is made, played, recorded and task-checked without it, and only
# the APK step is skipped (its release needs the APK).
$apkNote = 'mobile games still work without it, except the APK their release needs'
Try-Check 'Android toolchain (mobile games)' {
    # A mobile game's APK: every piece of the toolchain (lib\ggf-root.ps1 Get-GGFAndroid, what
    # tools\godot-pipeline\build.ps1 asks before its APK step). A WARN, never a FAIL: only a mobile game's release
    # needs it, and without it that step is skipped and says so.
    $parts = @(Get-GGFAndroidParts $cfg)
    $gone = @($parts | Where-Object { -not $_.present })
    if (-not $gone.Count) { Add-Result PASS 'Android toolchain (mobile games)' (@($parts | ForEach-Object { $_.name }) -join ', ') }
    else { Add-Result WARN 'Android toolchain (mobile games)' "missing: $(@($gone | ForEach-Object { "$($_.name) ($($_.detail))" }) -join '; ')" "only for a mobile game's APK, which its release needs (its release build skips the APK without it): machine\get-android.ps1 (docs/new-machine.md, section 3)" }
    $a = Get-GGFAndroid $cfg
    if (-not $a) { return }
    if ($a.godot -ne $eng.version) { Add-Result WARN 'Android toolchain version' "installed for Godot $($a.godot), the factory pins $($eng.version) (its build template may need other SDK packages)" 'machine\get-android.ps1' }
    $v = (Run $a.java @('-version')).out -split "`n" | Select-Object -First 1
    if ($v -match '"(\d+)\.') { if ([int]$Matches[1] -ge 17) { Add-Result PASS 'Android JDK version' "$v" } else { Add-Result WARN 'Android JDK version' "$v (Godot's Android build needs JDK 17; $apkNote)" 'machine\get-android.ps1' } }
    else { Add-Result WARN 'Android JDK version' "java -version said: $v ($apkNote)" 'machine\get-android.ps1' }
    # the editor settings an export reads: where the JDK and the SDK are, and the debug keystore
    $es = Get-GGFEditorSettingsPath $cfg
    if (-not $es) { Add-Result WARN 'Android editor settings' "the editor is not self-contained: its settings are in %APPDATA%, where this check does not look ($apkNote)" 'Editor Settings > Export > Android: Java SDK Path, Android SDK Path'; return }
    $text = if (Test-Path -LiteralPath $es) { [IO.File]::ReadAllText($es) } else { '' }
    $slash = { param($p) ([string]$p) -replace '\\', '/' }
    $want = [ordered]@{ 'export/android/java_sdk_path' = (& $slash $a.jdk); 'export/android/android_sdk_path' = (& $slash $a.sdk)
        'export/android/debug_keystore' = (& $slash $a.debug_keystore.path) }
    $bad = @($want.Keys | Where-Object { $text -notmatch ('(?m)^' + [regex]::Escape($_) + ' = "' + [regex]::Escape($want[$_]) + '"\s*$') })
    if (-not $bad) { Add-Result PASS 'Android editor settings' "$es names the JDK, the SDK and the debug keystore" }
    else { Add-Result WARN 'Android editor settings' "$es does not name this toolchain: $($bad -join ', ') ($apkNote)" 'machine\get-android.ps1' }
}

# --- report ------------------------------------------------------------------------------------------------------------
$colors = @{ PASS = 'Green'; WARN = 'Yellow'; FAIL = 'Red' }
Write-Host ""
Write-Host "godot-game-factory machine check  (root $Root, agents $($Agents -join ' + '), hooks dir $HooksDir)"
foreach ($r in $results) {
    Write-Host ("  {0}  {1,-30} {2}" -f $r.status, $r.check, $r.detail) -ForegroundColor $colors[$r.status]
    if ($r.status -ne 'PASS' -and $r.fix) { Write-Host ("        fix: {0}" -f $r.fix) -ForegroundColor DarkGray }
}
$nFail = @($results | Where-Object status -eq 'FAIL').Count
$nWarn = @($results | Where-Object status -eq 'WARN').Count
Write-Host ("{0} checks: {1} PASS, {2} WARN, {3} FAIL" -f $results.Count, ($results.Count - $nFail - $nWarn), $nWarn, $nFail)
if ($Json) {
    $obj = [ordered]@{ time = (Get-Date).ToString('o'); root = $Root; agents = $Agents; hooks_dir = $HooksDir; claude_dir = $ClaudeDir; codex_dir = $CodexDir; fail = $nFail; warn = $nWarn; results = $results }
    [IO.File]::WriteAllText($Json, ($obj | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
}
exit $nFail
