<#
.SYNOPSIS
  Create a new game repo from templates\godot-game (Godot 4): project skeleton (project.godot, the export presets, a
  first scene, the scenario list and the AutoPlay drop-in), Scripts\godot.ps1 (import, generator steps, workflow rows,
  builds, plays and AutoPlay runs through the heavy-job limiter), first workflow.jsonl row, git + LFS, the post-commit
  hook (commit recorder), the first import when the editor is installed, first commit, and the private GitHub repo
  <org>/godot-game-<slug> (not pushed; <org> = -Org, else the config's github_org).
.DESCRIPTION
  Placeholders replaced in file names and contents: __PROJECT__ (the exe and APK name), __SLUG__, __TITLE__,
  __DESCRIPTION__, __GODOT_VERSION__ and __GODOT_FEATURE__ (the factory's pinned engine, machine\godot.json); in a
  mobile game's files also __ORIENTATION__ (landscape or portrait), __PORTRAIT__ (true or false), __PHONE_WIDTH__ and
  __PHONE_HEIGHT__ (the phone's size), __HANDHELD__ (the engine's number for the orientation) and __ANDROID_NAME__
  (the project name in lower case, for the package name).
  tools\godot-pipeline\autoplay\addons\autoplay\ (the AutoPlay drop-in) is copied unchanged into addons\autoplay\.
  The first workflow.jsonl row (op project.create) is written at the moment the project is created; the first commit
  names it. Pushing is left to the coordinator's go-ahead (godot-commit-always skill).
  -Path is required: the absolute project folder <root>\games\<slug>, written out in the command (the recording hooks
  see the command text, so %GGF_ROOT% or $env:GGF_ROOT would not map the session). That call files this session under
  the game, and the hooks import its earlier calls from the transcript.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File <root>\godot-game-factory\templates\new-game.ps1 -Slug <game> `
      -Path <root>\games\<game> -Title "<Title>" -Description "<one line>" -Reason "<why>"
  (<root> written out, e.g. C:\Users\<you>\GodotWork)
.EXAMPLE
  ... -Slug <game> -Path <root>\games\<game> -Platform mobile -Orientation portrait
  An Android phone game: the same skeleton with templates\godot-game-mobile laid over it (the Mobile renderer, the
  phone's size and orientation, touch settings, the Android export preset, game\phone.gd, a first scene with a touch
  button) and Platform.json at its root. -Platform desktop (the default) creates a desktop game; -Orientation goes with
  mobile only and is the game's for good.
#>
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^(?!.*--)[a-z0-9][a-z0-9-]*[a-z0-9]$', Options = 'None')][string]$Slug,
    # required: the absolute <root>\games\<slug>, written out
    [string]$Path,
    # default from the slug: island-survival -> IslandSurvival
    [string]$Project,
    # default from the slug: Island Survival
    [string]$Title,
    [string]$Description = '',
    # workflow row id prefix; default the slug's initials (is, rr, td) or its first two letters
    [string]$IdPrefix,
    [string]$Reason = 'Create the project from the standard Godot skeleton (text scenes and settings, the scenario list, the AutoPlay drop-in, LFS for every binary type)',
    [string]$Root,
    # default: the config's hooks_dir (machine/lib/ggf-root.ps1 Get-GGFHooksDir)
    [string]$HooksDir,
    # default: the config's github_org (GGF_ORG)
    [string]$Org,
    # mobile: an Android phone game (Platform.json, the mobile project settings, the Android export preset)
    [ValidateSet('desktop', 'mobile')][string]$Platform = 'desktop',
    # with -Platform mobile: how the phone is held, for good
    [ValidateSet('landscape', 'portrait')][string]$Orientation,
    # skip the first import (tests, or no editor yet): run Scripts/godot.ps1 import later, then commit
    [switch]$NoSetup,
    # skip creating the GitHub repo (tests, offline)
    [switch]$NoGitHub
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
. (Join-Path $repo 'machine\lib\ggf-root.ps1')
if (-not $Root) { $Root = Get-GGFRoot }
if (-not $HooksDir) { $HooksDir = Get-GGFHooksDir }
if (-not $Org) { $Org = Get-GGFOrg }
if (-not $Org -and -not $NoGitHub) { throw 'no GitHub org: set github_org (machine/bootstrap.ps1 -Org <org>), pass -Org, or -NoGitHub' }
# Pre-flight, first: the recording hooks tie this session to the game when a tool call names the project folder as an
# absolute path, so the call must carry -Path <root>\games\<slug> literally (not %GGF_ROOT% / $env:GGF_ROOT, which the
# hook sees unexpanded). The session's earlier calls are then imported from its transcript (machine/README.md).
$want = Join-Path $Root "games\$Slug"
if (-not $Path) { throw "pass -Path $want (the absolute project folder, written out, so the recording hooks file this session under the game)" }
if (-not [IO.Path]::IsPathRooted($Path) -or [IO.Path]::GetFullPath($Path).TrimEnd('\') -ne [IO.Path]::GetFullPath($want).TrimEnd('\')) {
    throw "-Path must be the absolute folder $want (got '$Path')"
}
Write-Host "project folder: $Path (this call maps the session to $Slug for recording)"
if ($Platform -eq 'mobile' -and -not $Orientation) { throw 'a mobile game is held one way: pass -Orientation landscape or -Orientation portrait' }
if ($Platform -ne 'mobile' -and $Orientation) { throw '-Orientation goes with -Platform mobile (a desktop game has none)' }
$words = $Slug -split '-'
# Invariant: under a Turkish culture 'i'.ToUpper() is a dotted capital I (ice-cave was refused as a project name)
if (-not $Project) { $Project = ($words | ForEach-Object { $_.Substring(0, 1).ToUpperInvariant() + $_.Substring(1) }) -join '' }
if (-not $Title) { $Title = ($words | ForEach-Object { $_.Substring(0, 1).ToUpperInvariant() + $_.Substring(1) }) -join ' ' }
if (-not $IdPrefix) { $IdPrefix = if ($words.Count -ge 2) { ($words | ForEach-Object { $_[0] }) -join '' } else { $Slug.Substring(0, 2) } }
# Case-sensitive (-cnotmatch, Options = 'None' above): PowerShell matches ignore case, and an id like Ba-00001 or
# 3m-00001 fails the row schema for good (rows are never edited).
if ($Project -cnotmatch '^[A-Z][A-Za-z0-9]{1,30}$') { throw "project name '$Project' must be PascalCase letters/digits (pass -Project)" }
if ($IdPrefix -cnotmatch '^[a-z]+$') { throw "workflow row id prefix '$IdPrefix' must be lower-case letters (pass -IdPrefix)" }
# The title lands in quoted strings (project.godot: the game's name; the first scene's label) and on the comment line
# that opens Scripts\godot.ps1: keep it plain text. (The description lands only in README.md.)
if ($Title -match '["\\\r\n]') { throw "no quotes, backslashes or line breaks in the title: '$Title'" }

# Names that must never appear inside a game (code, config, commits, builds). The repo's own name counts: the slug
# factory-floor passes alone, but godot-game-factory-floor holds a banned name wherever the repo is named.
foreach ($v in @($Slug, "godot-game-$Slug", $Project, $Title, $Description, $Reason)) {
    if ($v -match '(?i)superposition|game[-_ ]?factory|claude|anthropic|openai' -or ($Org -and $v -match ('(?i)' + [regex]::Escape($Org)))) { throw "banned name in '$v' (see the godot-game-session skill)" }
}
if ((Test-Path -LiteralPath $Path) -and @(Get-ChildItem -LiteralPath $Path -Force).Count) { throw "$Path exists and is not empty" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git not found (run machine\bootstrap.ps1 first)' }

# The engine: the factory's pinned one (machine\godot.json). A game names it in project.godot (config/features).
$engine = Get-GGFEngine
$template = Join-Path $PSScriptRoot 'godot-game'
$map = [ordered]@{
    '__PROJECT__' = $Project; '__SLUG__' = $Slug; '__TITLE__' = $Title; '__DESCRIPTION__' = $Description
    '__GODOT_VERSION__' = [string]$engine.version; '__GODOT_FEATURE__' = [string]$engine.feature
}
$utf8 = New-Object Text.UTF8Encoding($false)
function Expand([string]$s) { foreach ($k in $map.Keys) { $s = $s.Replace($k, $map[$k]) }; return $s }

New-Item -ItemType Directory -Force $Path | Out-Null
$Path = (Resolve-Path -LiteralPath $Path).Path
$count = 0
foreach ($f in Get-ChildItem -LiteralPath $template -Recurse -File -Force) {
    $rel = Expand ($f.FullName.Substring($template.Length + 1))
    $dst = Join-Path $Path $rel
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    [IO.File]::WriteAllText($dst, (Expand ([IO.File]::ReadAllText($f.FullName))), $utf8)
    $count++
}
if ($Platform -eq 'mobile') {
    # A mobile (Android phone) game: the mobile files laid over the skeleton's (the project settings, the export
    # presets, game\phone.gd, the first scene, the README) and Platform.json at the root, which says what the game is
    # to every tool after this one (validate-game.py, the task check, the pipeline, the packager). A desktop game has
    # none of it.
    $phone = if ($Orientation -eq 'portrait') { @(1080, 1920) } else { @(1920, 1080) }
    $map['__ORIENTATION__'] = $Orientation
    $map['__PORTRAIT__'] = if ($Orientation -eq 'portrait') { 'true' } else { 'false' }
    $map['__PHONE_WIDTH__'] = "$($phone[0])"
    $map['__PHONE_HEIGHT__'] = "$($phone[1])"
    $map['__HANDHELD__'] = if ($Orientation -eq 'portrait') { '1' } else { '0' }   # display/window/handheld/orientation
    $map['__ANDROID_NAME__'] = $Project.ToLowerInvariant()
    $overlay = Join-Path $PSScriptRoot 'godot-game-mobile'
    foreach ($f in Get-ChildItem -LiteralPath $overlay -Recurse -File -Force) {
        $rel = Expand ($f.FullName.Substring($overlay.Length + 1))
        $dst = Join-Path $Path $rel
        if (-not (Test-Path -LiteralPath $dst)) { $count++ }
        New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
        [IO.File]::WriteAllText($dst, (Expand ([IO.File]::ReadAllText($f.FullName))), $utf8)
    }
    [IO.File]::WriteAllText((Join-Path $Path 'Platform.json'), (([ordered]@{ platform = 'mobile'; orientation = $Orientation } | ConvertTo-Json -Compress) + "`n"), $utf8)
    $count++
}
# The AutoPlay drop-in, copied unchanged (the template's game\scenarios.gd calls it):
# tools\godot-pipeline\autoplay\addons\autoplay\ into addons\autoplay\ (docs\autoplay-contract.md).
$dropIn = Join-Path $repo 'tools\godot-pipeline\autoplay\addons\autoplay'
if (-not (Test-Path -LiteralPath (Join-Path $dropIn 'autoplay.gd'))) { throw "the AutoPlay drop-in is not at $dropIn" }
foreach ($f in Get-ChildItem -LiteralPath $dropIn -Recurse -File) {
    $dst = Join-Path $Path ('addons\autoplay\' + $f.FullName.Substring($dropIn.Length + 1))
    New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
    [IO.File]::WriteAllText($dst, ([IO.File]::ReadAllText($f.FullName)).Replace("`r`n", "`n"), $utf8)
    $count++
}
$autoplay = if ([IO.File]::ReadAllText((Join-Path $dropIn 'autoplay.gd')) -match '(?m)^const VERSION\b[^=\r\n]*=\s*(\d+)') { [int]$Matches[1] } else { $null }

# workflow.jsonl, first row: the operation this script just performed.
# The hash of this script as committed (LF), as Scripts\godot.ps1 takes a step's: a Windows clone holds it with CRLF.
$latin1 = [Text.Encoding]::GetEncoding(28591)   # one character per byte, so the bytes come back unchanged
$scriptSha = -join ([Security.Cryptography.SHA256]::Create().ComputeHash($latin1.GetBytes($latin1.GetString([IO.File]::ReadAllBytes($PSCommandPath)).Replace("`r`n", "`n"))) | ForEach-Object { $_.ToString('x2') })
# null when this folder is no git work tree (a copy, or one git refuses): under 'Stop' the line git writes to stderr
# would end the script here, with the skeleton half made
$templateCommit = [string](& { $ErrorActionPreference = 'Continue'; & git -C $repo rev-parse --short=12 HEAD 2>$null })
if (-not $templateCommit) { $templateCommit = $null }
$rowId = '{0}-{1:D5}' -f $IdPrefix, 1
$row = [ordered]@{
    schema = 'godot-workflow/v0'; id = $rowId; seq = 1; time = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss.fffzzz', [Globalization.CultureInfo]::InvariantCulture)
    actor = 'agent'; op = 'project.create'; target = 'project.godot'
    params = [ordered]@{ engine = "godot $($engine.version)"; template = 'godot-game'; template_commit = $templateCommit; files = $count; project = $Project; autoplay_version = $autoplay }
    reason = $Reason; reason_source = 'agent_note'; status = 'observed'
    source = [ordered]@{ script = 'new-game.ps1'; sha256 = $scriptSha; commit = $null }
}
if ($Platform -eq 'mobile') { $row.params['platform'] = 'mobile'; $row.params['orientation'] = $Orientation }
[IO.File]::WriteAllText((Join-Path $Path 'workflow.jsonl'), ($row | ConvertTo-Json -Compress -Depth 6) + "`n", $utf8)

# git + LFS + recorder.
$old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
& git -C $Path init -q -b main 2>&1 | Out-Null
& git -C $Path lfs install --local 2>&1 | Out-Null
$ErrorActionPreference = $old
& (Join-Path $repo 'machine\install-git-hook.ps1') -Repo $Path -HooksDir $HooksDir | Out-Null

# The first import (Scripts\godot.ps1 import): the engine writes the .import and .uid files beside what it imports,
# and they belong in the first commit with the files they are for.
$setup = 'skipped (-NoSetup): run Scripts/godot.ps1 import, then commit the .import and .uid files it made'
if (-not $NoSetup) {
    $editor = Get-GGFGodot -ErrorAction SilentlyContinue
    if ($editor -and (Test-Path -LiteralPath $editor)) {
        Write-Host "first import with Godot $($engine.version)"
        $ErrorActionPreference = 'Continue'
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Path 'Scripts\godot.ps1') import | Out-Host
        $code = $LASTEXITCODE
        $ErrorActionPreference = $old
        $setup = if ($code -eq 0) { 'done' } else { "FAILED (exit $code): read Logs/godot-ps1/import.log, fix, run Scripts/godot.ps1 import again, then commit" }
    } else {
        $setup = "not run: Godot $($engine.version) is not installed (machine\get-godot.ps1 installs it), then run Scripts/godot.ps1 import and commit"
    }
}

# The first commit (the post-commit hook records it).
$ErrorActionPreference = 'Continue'
& git -C $Path add -A 2>&1 | Out-Null
$kind = if ($Platform -eq 'mobile') { "`nAn Android phone game, held in $Orientation (Platform.json, the mobile project settings, the APK build)." } else { '' }
$msg = "Create the $Title project (Godot $($engine.version) skeleton)`n`nText scenes and settings, the scenario list, the AutoPlay drop-in v$autoplay, Scripts/godot.ps1,`nroot-anchored .gitignore, LFS for every binary type.$kind`n`nworkflow: $rowId"
$msgFile = Join-Path $Path '.git\NEW_GAME_MSG'
[IO.File]::WriteAllText($msgFile, $msg, $utf8)
& git -C $Path commit -q -F $msgFile 2>&1 | Out-Null
$code = $LASTEXITCODE
Remove-Item -LiteralPath $msgFile -ErrorAction SilentlyContinue
$ErrorActionPreference = $old
# what is left (the files, git, no commit) makes a second run refuse the folder as not empty
if ($code -ne 0) { throw "commit failed (git user.name / user.email set?): set them, delete $Path and run new-game.ps1 again" }
$sha = & git -C $Path rev-parse --short HEAD

$remote = $null
if (-not $NoGitHub) {
    $full = "$Org/godot-game-$Slug"
    $ErrorActionPreference = 'Continue'
    # without gh the call below fails to start and leaves an earlier command's exit code: the repo read as existing
    $gh = [bool](Get-Command gh -ErrorAction SilentlyContinue)
    # a contractor has no GitHub sign-in and no rights in the org: the game stays on the PC and ships in the dataset zip
    $signedIn = $false
    if ($gh) { & gh auth status 2>&1 | Out-Null; $signedIn = ($LASTEXITCODE -eq 0) }
    if ($signedIn) { & gh repo view $full --json name 2>&1 | Out-Null }
    $exists = ($signedIn -and $LASTEXITCODE -eq 0)
    if (-not $signedIn) {
        Write-Host "  no GitHub repo made (not signed in to GitHub): expected for a contractor, whose game stays on this PC and ships in the dataset zip; do not ask for access to $Org. Staff: gh auth login --web, then gh repo create $full --private; git -C `"$Path`" remote add origin https://github.com/$full.git"
    } elseif ($exists) {
        # never linked unseen: it may be another game's (same slug) or public, and a push would ship store content there
        Write-Warning "$full already exists: not linked. Check that it is this game's and private, then: git remote add origin https://github.com/$full.git"
    } else {
        & gh repo create $full --private --description $Title 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
            & git -C $Path remote add origin "https://github.com/$full.git"
            $remote = "https://github.com/$full (private; not pushed: push when the coordinator says)"
        } else { Write-Host "  no GitHub repo made (this account cannot create $full): expected for a contractor, whose game stays on this PC and ships in the dataset zip; do not ask for access to $Org. Staff: ask an owner of $Org for the right to create repos, then gh repo create $full --private" }
    }
    $ErrorActionPreference = $old
}

Write-Host "created $Title ($Project, Godot $($engine.version)) at $Path"
if ($Platform -eq 'mobile') { Write-Host "  platform: mobile (an Android phone game), held in $Orientation; read the godot-mobile-game skill before building" }
Write-Host "  files: $count, AutoPlay drop-in v$autoplay, first row $rowId, commit $sha"
Write-Host "  first import: $setup"
Write-Host "  remote: $(if ($remote) { $remote } else { 'none' })"
Write-Host "  next: write the design doc, build through Scripts/godot.ps1, log every operation in workflow.jsonl"
