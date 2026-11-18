"""A package check's export (docs/task-check.md, "The package check"): the game's release export, built from its own
"Windows Desktop" preset and booted.

The game's release export is its "Windows Desktop" preset (tools/godot-pipeline/build.ps1 exports it with the release
template). `derive` adds a preset of the checker's own, PRESET, made from it: its export filter and files, its include
and exclude filters, its custom features, its script export mode and its texture formats, the pck embedded, x86_64 and
nothing encrypted, with the probe addon put in (its folder added to the include filter, and only the exclude patterns
that would leave a file of it out dropped), so the exported game plays through the probe as a copy from source does.
On Windows (the factory's machines) the preset exports for Windows Desktop, elsewhere for Linux: the player must run
on the machine that plays it. The game's own presets are kept as they are; the copy's export_presets.cfg holds the
derived file only for the export, and its own bytes are put back after it, whatever happened (godot.Project.package).

`templates` says where the engine looks for the export templates and whether the release template is there: a machine
without it fails the check with that reason (machine/get-godot.ps1 installs them), never passes it."""

import fnmatch
import os
import re
from pathlib import Path

PRESETS_FILE = "export_presets.cfg"
RELEASE = "Windows Desktop"  # the game's release preset (the factory's release build exports it)
PRESET = "TaskProbe package"  # the checker's own preset, never one of the game's names
# what the engine logs when an export fails
FAILED = r"Project export for preset .* failed|Cannot export project|No export template found"
# the release preset's settings the derived preset keeps as the game wrote them
KEPT = ("dedicated_server", "custom_features", "export_filter", "export_files", "script_export_mode")
KEPT_OPTIONS = ("texture_format/s3tc_bptc", "texture_format/etc2_astc")
OPTIONS = (("binary_format/embed_pck", "true"), ("binary_format/architecture", '"x86_64"'),
           ("shader_baker/enabled", "false"), ("ssh_remote_deploy/enabled", "false"))
# on Windows: no signing, no resource edit (an icon or version info changes nothing the check plays), no console wrapper
WINDOWS_OPTIONS = (("codesign/enable", "false"), ("application/modify_resources", "false"),
                   ("debug/export_console_wrapper", "0"))
SECTION = re.compile(r"^\[([^\]]+)\]\s*$")
KEY = re.compile(r"^([A-Za-z0-9_/.\-]+)\s*=(.*)$")
PRESET_SECTION = re.compile(r"^preset\.(\d+)$")
OPTIONS_SECTION = re.compile(r"^preset\.(\d+)\.options$")


class NoRelease(ValueError):
    """The game has nothing to export: no export_presets.cfg, or no preset named RELEASE in it."""


def target(windows=None):
    """(the export's platform, the release template's file, the exported player's file name) for this machine:
    Windows Desktop on Windows, Linux elsewhere."""
    windows = os.name == "nt" if windows is None else windows
    return ("Windows Desktop", "windows_release_x86_64.exe", "game.exe") if windows else \
        ("Linux", "linux_release.x86_64", "game.x86_64")


def templates(editor, version, windows=None, env=None):
    """The folder where `editor` (the engine's exe) reads the export templates of `version` ("4.7.2.stable"), as the
    engine finds them: beside a self-contained editor (a `._sc_` or `_sc_` file next to it) in editor_data/, else the
    user's own data folder (%APPDATA%\\Godot on Windows, XDG_DATA_HOME or ~/.local/share/godot elsewhere)."""
    windows = os.name == "nt" if windows is None else windows
    env = os.environ if env is None else env
    here = Path(editor).parent
    if (here / "._sc_").is_file() or (here / "_sc_").is_file():
        data = here / "editor_data"
    elif windows:
        data = Path(env.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Godot"
    else:
        data = Path(env.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "godot"
    return data / "export_templates" / version


def missing_template(editor, version, windows=None, env=None):
    """Why this machine can't make the release export, or None: the release template it needs isn't there."""
    _, template, _ = target(windows)
    folder = templates(editor, version, windows, env)
    if (folder / template).is_file():
        return None
    return (f"this machine has no {version} release export template ({template} isn't in {folder}): the release "
            "export can't be made here, so the check fails; machine\\get-godot.ps1 installs the templates")


def sections(text):
    """[(section, [[key, raw value]])] of a Godot config text, in order: a line that isn't `key=value` continues the
    value before it (a value written over lines)."""
    found = []
    for line in text.replace("\r\n", "\n").split("\n"):
        named = SECTION.match(line)
        if named:
            found.append((named.group(1), []))
        elif found and line.strip():
            pair = KEY.match(line)
            if pair:
                found[-1][1].append([pair.group(1), pair.group(2)])
            elif found[-1][1]:
                found[-1][1][-1][1] += "\n" + line
    return found


def unquote(raw):
    raw = (raw or "").strip()
    return raw[1:-1].replace('\\"', '"') if len(raw) >= 2 and raw[0] == raw[-1] == '"' else raw


def patterns(raw):
    return [p.strip() for p in unquote(raw).split(",") if p.strip()]


def quoted(items):
    return '"' + ", ".join(items).replace('"', '\\"') + '"'


def derive(text, addon, addon_files, windows=None):
    """`text` (the game's export_presets.cfg, or None when it has none) with PRESET added, made from its RELEASE
    preset as the module says; `addon`: the probe's folder in the copy, `addon_files`: its files' paths under it.
    NoRelease naming what is missing when there is no release preset."""
    if text is None:
        raise NoRelease(f'the game has no {PRESETS_FILE}, so no "{RELEASE}" preset: its release export')
    found = sections(text)
    presets = {int(m.group(1)): dict(keys) for name, keys in found if (m := PRESET_SECTION.match(name))}
    options = {int(m.group(1)): dict(keys) for name, keys in found if (m := OPTIONS_SECTION.match(name))}
    release = next((n for n, keys in sorted(presets.items()) if unquote(keys.get("name")) == RELEASE), None)
    if release is None:
        raise NoRelease(f'{PRESETS_FILE} has no preset named "{RELEASE}": the game\'s release export')
    keys, own = presets[release], options.get(release, {})
    files = [f"{addon}/{name}" for name in addon_files]
    exclude = [p for p in patterns(keys.get("exclude_filter")) if not any(
        fnmatch.fnmatchcase(f, p) or fnmatch.fnmatchcase(f.rsplit("/", 1)[-1], p) for f in files)]
    include = [*patterns(keys.get("include_filter")), f"{addon}/*"]
    at = max(presets) + 1
    lines = [f"[preset.{at}]", "", f'name="{PRESET}"', f'platform="{target(windows)[0]}"', "runnable=false"]
    lines += [f"{k}={keys[k]}" for k in KEPT if k in keys]
    lines += [f"include_filter={quoted(include)}", f"exclude_filter={quoted(exclude)}", 'export_path=""',
              "encrypt_pck=false", "encrypt_directory=false", "", f"[preset.{at}.options]", ""]
    lines += [f"{k}={own[k]}" for k in KEPT_OPTIONS if k in own]
    windows = os.name == "nt" if windows is None else windows
    lines += [f"{k}={v}" for k, v in (*OPTIONS, *(WINDOWS_OPTIONS if windows else ()))]
    return text.rstrip("\r\n") + "\n\n" + "\n".join(lines) + "\n"
