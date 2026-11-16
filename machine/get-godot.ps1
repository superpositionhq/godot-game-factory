<#
.SYNOPSIS
  Download, checksum-verify and unpack the pinned Godot editor and its export templates (idempotent).
.DESCRIPTION
  The engine is the one machine\godot.json names. Result, under <root>\godot\<version>\:
    <exe>, <console_exe>                              the editor and its console wrapper
    ._sc_                                             an empty file: the editor is self-contained, so its data and
                                                      settings stay in editor_data\ here and nothing goes to %APPDATA%
    editor_data\export_templates\<templates>\         the export templates (Windows, Android, ...)
  A part that is already there is left alone and not downloaded again: the editor when both exes are there, the
  templates when their version.txt names <templates> and the Windows release template is there. -Force fetches both
  again.
  Each archive is verified against the SHA-512 in godot.json (the release's SHA512-SUMS.txt) before anything is
  unpacked; one that does not match is deleted and the script fails. Archives are downloaded to
  <root>\godot\<version>\_download\ and removed after unpacking (the templates are 1.3 GB). Binaries are never
  committed.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File machine\get-godot.ps1
  powershell -ExecutionPolicy Bypass -File machine\get-godot.ps1 -EditorArchive D:\dl\Godot_v4.7.2-stable_win64.exe.zip -TemplatesArchive D:\dl\Godot_v4.7.2-stable_export_templates.tpz
#>
param(
    # machine root; default from machine/lib/ggf-root.ps1
    [string]$Root,
    # already downloaded archives to use instead of downloading (still verified)
    [string]$EditorArchive,
    [string]$TemplatesArchive,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'lib\ggf-root.ps1')
if ($Root) { $env:GGF_ROOT = $Root }
$Root = Get-GGFRoot
$eng = Get-GGFEngine
$dir = Join-Path $Root "godot\$($eng.version)"
$exe = Join-Path $dir $eng.exe
$console = Join-Path $dir $eng.console_exe
$templates = Join-Path $dir "editor_data\export_templates\$($eng.templates)"
$dl = Join-Path $dir '_download'

function Get-Sha512([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA512).Hash.ToLowerInvariant() }

# A verified archive: the one given, else a download into $dl.
function Get-Archive([string]$What, [string]$Given) {
    $want = ([string]$eng.sha512.$What).ToLowerInvariant()
    if ($Given) {
        if ((Get-Sha512 $Given) -ne $want) { throw "SHA-512 mismatch for $Given (expected $want)" }
        return $Given
    }
    $url = [string]$eng.urls.$What
    $dest = Join-Path $dl ([IO.Path]::GetFileName($url))
    New-Item -ItemType Directory -Force $dl | Out-Null
    if ((Test-Path -LiteralPath $dest) -and (Get-Sha512 $dest) -eq $want) { return $dest }
    Write-Host "downloading $url"
    Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    if (Test-Path -LiteralPath $curl) {
        & $curl -sSL --fail -o $dest $url
        if ($LASTEXITCODE -ne 0) { throw "download failed (curl exit $LASTEXITCODE): $url" }
    } else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        (New-Object Net.WebClient).DownloadFile($url, $dest)
    }
    $h = Get-Sha512 $dest
    if ($h -ne $want) {
        $len = (Get-Item -LiteralPath $dest).Length
        Remove-Item -LiteralPath $dest -Force
        throw "SHA-512 mismatch for $url ($len bytes, sha512 $h; expected $want): discarded, nothing was unpacked"
    }
    return $dest
}

# Unpack a zip into a fresh folder (Windows' tar.exe reads zip, and a .tpz is one).
function Expand-To([string]$Archive, [string]$Stage) {
    Remove-Item -LiteralPath $Stage -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force $Stage | Out-Null
    & "$env:SystemRoot\System32\tar.exe" -xf $Archive -C $Stage
    if ($LASTEXITCODE -ne 0) { throw "unpacking $Archive failed (exit $LASTEXITCODE)" }
}

New-Item -ItemType Directory -Force $dir | Out-Null

$haveEditor = (Test-Path -LiteralPath $exe -PathType Leaf) -and (Test-Path -LiteralPath $console -PathType Leaf)
if ($haveEditor -and -not $Force) { Write-Host "Godot $($eng.version) editor present: $exe" }
else {
    $arc = Get-Archive 'editor' $EditorArchive
    $stage = Join-Path $dir "_unpack-$PID"
    Expand-To $arc $stage
    foreach ($f in $eng.exe, $eng.console_exe) {
        if (-not (Test-Path -LiteralPath (Join-Path $stage $f))) { throw "unexpected archive layout: no $f in $arc" }
        Move-Item -LiteralPath (Join-Path $stage $f) (Join-Path $dir $f) -Force
    }
    Remove-Item -LiteralPath $stage -Recurse -Force
    Write-Host "Godot $($eng.version) editor ready: $exe"
}
# self-contained: without this file the editor keeps its settings and export templates in %APPDATA%
$sc = Join-Path $dir '._sc_'
if (-not (Test-Path -LiteralPath $sc)) { New-Item -ItemType File -Force $sc | Out-Null }

$verFile = Join-Path $templates 'version.txt'
$haveTemplates = (Test-Path -LiteralPath $verFile) -and ([IO.File]::ReadAllText($verFile).Trim() -eq $eng.templates) -and
    (Test-Path -LiteralPath (Join-Path $templates 'windows_release_x86_64.exe'))
if ($haveTemplates -and -not $Force) { Write-Host "export templates $($eng.templates) present: $templates" }
else {
    $arc = Get-Archive 'templates' $TemplatesArchive
    $stage = Join-Path $dir "_unpack-$PID"
    Expand-To $arc $stage
    if (-not (Test-Path -LiteralPath (Join-Path $stage 'templates\version.txt'))) { throw "unexpected archive layout: no templates\version.txt in $arc" }
    New-Item -ItemType Directory -Force (Split-Path $templates) | Out-Null
    Remove-Item -LiteralPath $templates -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath (Join-Path $stage 'templates') $templates
    Remove-Item -LiteralPath $stage -Recurse -Force
    Write-Host "export templates $($eng.templates) ready: $templates"
}
Remove-Item -LiteralPath $dl -Recurse -Force -ErrorAction SilentlyContinue
return $exe
