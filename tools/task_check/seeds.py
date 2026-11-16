"""A commit of the game as a project folder outside its repo, for the checker to build and play.

- materialize: the game's files at a commit, exactly as committed, read straight from its repository (git objects, and
  the Git LFS objects in its local store), written into a scratch folder; each LFS file is a hardlink of its object when
  the folder is on the repo's volume (it costs no disk), else a copy. Nothing in the repo is written or checked out, and
  nothing from another commit is added: a task is built exactly as committed (no patch).
- what a task's agent never sees is left out (ANSWERS): Tasks/, History/, Dataset/ and Dataset.zip at the root.
- add_probe: the task probe addon as addons/task_probe/, and three lines in the copy's project.godot: the addon's
  autoload, first in [autoload] (it runs before the game's own), and a user data folder of the copy's own, so a play
  never reads or writes the real game's saved data. The only things the checker adds."""

import hashlib
import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path

LFS_POINTER = re.compile(rb"^version https://git-lfs\.github\.com/spec/v1\noid sha256:([0-9a-f]{64})\nsize (\d+)\n")
POINTER_MAX = 300  # bytes: a Git LFS pointer is smaller (about 130)
PROBE = "addons/task_probe"
PROBE_SOURCE = Path(__file__).resolve().parent / "task_probe"
PROBE_JUNK = ("__pycache__", ".godot")  # leftovers a run may leave in the addon's folder
AUTOLOAD = ("TaskProbe", '"*res://addons/task_probe/task_probe.gd"')  # the addon's autoload: its name and value
ANSWERS = ("tasks", "history", "dataset", "dataset.zip")  # never materialized (case-insensitive, at the root)
ENGINE = "4.7"
PROJECT_FILE = "project.godot"
HELD = 10  # seconds remove() waits for a process that was just killed to let go of its files


class WrongEngine(ValueError):
    """A start that isn't a Godot 4.7 project as committed."""


def _git(repo, *args, data=None):
    found = subprocess.run(["git", "-C", str(repo), *args], input=data, capture_output=True, check=False)
    if found.returncode != 0:
        raise RuntimeError(f"git {args[0]} in {Path(repo).name} failed: {found.stderr.decode(errors='replace')[:300]}")
    return found.stdout


def resolve(repo, commit):
    """The full sha of `commit` in `repo`."""
    return _git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").decode().strip()


def lfs_store(repo):
    """Where a repository keeps its Git LFS objects: its lfs.storage, else .git/lfs/objects (lfs/objects when bare)."""
    repo = Path(repo)
    found = subprocess.run(["git", "-C", str(repo), "config", "--get", "lfs.storage"], capture_output=True, text=True)
    if found.returncode == 0 and found.stdout.strip():
        base = Path(found.stdout.strip())
        base = base if base.is_absolute() else Path(_git(repo, "rev-parse", "--absolute-git-dir").decode().strip()) / base
        return base / "objects" if (base / "objects").is_dir() else base
    git_dir = Path(_git(repo, "rev-parse", "--absolute-git-dir").decode().strip())
    common = _git(repo, "rev-parse", "--git-common-dir").decode().strip()
    common = Path(common) if os.path.isabs(common) else (Path(repo) / common).resolve()
    for base in (common, git_dir):
        if (base / "lfs" / "objects").is_dir():
            return base / "lfs" / "objects"
    return common / "lfs" / "objects"


def answer(path):
    """Whether a project-relative path (posix) is under ANSWERS."""
    return path.split("/", 1)[0].lower() in ANSWERS


def place(stored, target, link=True):
    """`target` as a hardlink of the LFS object `stored` (a copy across volumes or when `link` is off)."""
    if link:
        try:
            os.link(stored, target)
            return "linked"
        except OSError:
            pass
    shutil.copyfile(stored, target)
    return "copied"


def materialize(repo, commit, dest, link=True):
    """Write the files of `repo` at `commit` into `dest` (which must not exist), each Git LFS pointer replaced by its
    object from the repo's LFS store (hardlinked when `link` and the volume allows, else copied), and none of ANSWERS.
    Raises FileNotFoundError when an object isn't in the local store (`git lfs fetch` it first). {"files", "linked",
    "copied", "objects"}."""
    repo, dest = Path(repo), Path(dest)
    if dest.exists():
        raise FileExistsError(dest)
    listing = _git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0")
    entries = []
    for line in listing:
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, oid = meta.split()
        path = path.decode("utf-8")
        if kind == b"blob" and not answer(path):
            entries.append((path, oid.decode()))
    lfs = lfs_store(repo)
    counts = {"files": 0, "linked": 0, "copied": 0, "objects": {}}  # objects: LFS sha -> its file in the store
    missing = []
    with subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE) as batch:
        for path, oid in entries:
            batch.stdin.write(oid.encode() + b"\n")
            batch.stdin.flush()
            header = batch.stdout.readline().split()
            size = int(header[2])
            data = batch.stdout.read(size)
            batch.stdout.read(1)  # the newline after each object
            target = dest / path
            target.parent.mkdir(parents=True, exist_ok=True)
            pointer = LFS_POINTER.match(data) if size < POINTER_MAX else None
            counts["files"] += 1
            if pointer:
                sha = pointer.group(1).decode()
                stored = lfs / sha[:2] / sha[2:4] / sha
                if not stored.is_file():
                    missing.append(path)
                    continue
                counts[place(stored, target, link)] += 1
                counts["objects"][sha] = stored
            else:
                target.write_bytes(data)
        batch.stdin.close()
    if missing:
        raise FileNotFoundError(f"{len(missing)} Git LFS object(s) of {commit[:12]} aren't in {repo.name}'s local store "
                                f"(e.g. {missing[0]}): run `git -C {repo} lfs fetch origin {commit}` first")
    return counts


def engine_of(project):
    """The engine features the project's project.godot names in config/features (["4.7", "Forward Plus"]); [] without
    the file or the line."""
    path = Path(project) / PROJECT_FILE
    if not path.is_file():
        return []
    found = re.search(r"^config/features\s*=\s*PackedStringArray\((.*)\)\s*$",
                      path.read_text(encoding="utf-8-sig", errors="replace"), re.M)
    return re.findall(r'"([^"]*)"', found.group(1)) if found else []


def set_setting(text, section, key, value, first=False):
    """`text` (a project.godot) with `key=value` in `[section]`: the key's line replaced when the section has it, else
    added at the section's end (right under its header when `first`); the section added at the end when missing."""
    lines = text.split("\n")
    start = next((i for i, at in enumerate(lines) if at.strip() == f"[{section}]"), None)
    if start is None:
        return text.rstrip("\n") + f"\n\n[{section}]\n\n{key}={value}\n"
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^\[[\w.]+\]\s*$", lines[i])), len(lines))
    at = next((i for i in range(start + 1, end) if lines[i].startswith(f"{key}=")), None)
    if at is not None and not first:
        lines[at] = f"{key}={value}"
        return "\n".join(lines)
    if at is not None:
        del lines[at]
        end -= 1
    if first:
        under = start + 2 if start + 1 < len(lines) and not lines[start + 1].strip() else start + 1
        lines[under:under] = [f"{key}={value}"]
    else:
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        lines[end:end] = [f"{key}={value}"]
    return "\n".join(lines)


def add_probe(project):
    """Add the task probe to `project`: the addon as addons/task_probe/, its autoload first in project.godot's
    [autoload], and the copy's own user data folder (saves_company) in [application]. Raises WrongEngine when the
    project isn't a Godot 4.7 project: a task starts from a commit that runs on 4.7 as committed."""
    project = Path(project)
    engine = engine_of(project)
    if ENGINE not in engine:
        raise WrongEngine(f"{PROJECT_FILE} names Godot {next((e for e in engine if e[:1].isdigit()), '?')} in "
                          f"config/features: a task's commits must be Godot {ENGINE} projects as committed")
    target = project / PROBE
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(PROBE_SOURCE, target, ignore=shutil.ignore_patterns(*PROBE_JUNK))
    settings = project / PROJECT_FILE
    text = settings.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
    text = set_setting(text, "autoload", *AUTOLOAD, first=True)
    text = set_setting(text, "application", "config/use_custom_user_dir", "true")
    text = set_setting(text, "application", "config/custom_user_dir_name", f'"{saves_company(project)}"')
    settings.write_bytes(text.encode("utf-8"))
    return project


SAVES = re.compile(r"TaskProbe\.[0-9a-f]{12}")  # the only names forget_saves ever deletes


def saves_company(project):
    """The name of a scratch copy's user data folder (add_probe writes it into the copy's project.godot): "TaskProbe."
    and 12 hex digits of the sha256 of its folder, lower-cased. A play's saved data (`user://`) goes under that name,
    never under the real game's, and each side's copy has its own."""
    folder = os.path.abspath(str(project)).lower()
    return "TaskProbe." + hashlib.sha256(folder.encode("utf-8")).hexdigest()[:12]


def _saves_parent():
    """Where the engine keeps a project's custom user folder on Windows (%APPDATA%, as the engine reads it); None
    elsewhere."""
    return os.environ.get("APPDATA") if os.name == "nt" else None


def forget_saves(project):
    """What the plays of the scratch copy `project` left outside it: its user data folder, <saves_company> in
    _saves_parent. Only a name of SAVES' form directly under an absolute folder is ever deleted; rmtree never goes
    through a link."""
    company, parent = saves_company(project), _saves_parent()
    if parent and os.path.isabs(parent) and SAVES.fullmatch(company):
        shutil.rmtree(os.path.join(parent, company), ignore_errors=True)


def _projects(path, depth=3):
    """The Godot projects at or under `path`, down to `depth` folders."""
    path = Path(path)
    if (path / PROJECT_FILE).is_file():
        return [path]
    if depth <= 0 or not path.is_dir():
        return []
    found = []
    try:
        for child in path.iterdir():
            if child.is_dir() and not child.is_symlink():
                found += _projects(child, depth - 1)
    except OSError:
        pass
    return found


def forget(path):
    """The saved data the plays of every scratch copy at or under `path` left outside it (forget_saves)."""
    for project in _projects(path):
        forget_saves(project)


def refused(path):
    """Why remove() never deletes `path`, or None: what can never be a folder of the checker's own. An empty path is
    the current folder (remove("") emptied it); a drive's or share's root, the current folder or one above it (the
    checker's own run is in it) and the user's home or one above it."""
    if not str(path).strip():
        return "an empty path is the current folder"
    full = os.path.normcase(os.path.abspath(path))
    if os.path.dirname(full) == full:
        return "a drive's root"
    for what, folder in (("the current folder", os.getcwd()), ("the user's home", os.path.expanduser("~"))):
        if os.path.isabs(folder):
            try:
                if os.path.commonpath([full, os.path.normcase(os.path.abspath(folder))]) == full:
                    return f"{what}, or a folder above it"
            except ValueError:  # on another drive
                pass
    return None


def remove(path):
    """`path` removed (a folder, read-only files included, or a file), and with a scratch copy the saved data its plays
    left outside it. What another process still holds is tried again for up to HELD seconds, then the error raised: a
    game killed at its timeout still held its log for a moment, and the next play of its copy failed on it. A link (a
    junction too) goes as the link, never what it points at (rmtree refused one and left it without a word); a path
    `refused` names raises ValueError."""

    def writable(func, target, _):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    why = refused(path)
    if why:
        raise ValueError(f"won't delete {path}: {why}")
    path = Path(path)
    if path.is_symlink() or os.path.isjunction(path):
        os.unlink(path)  # (for a link to a folder too: Windows removes the link itself)
        return
    if path.is_dir():
        forget(path)
    end = time.monotonic() + HELD
    while True:
        try:
            if path.is_dir():
                shutil.rmtree(path, onexc=writable)
            elif path.exists():
                path.unlink()
            return
        except OSError:
            if time.monotonic() > end:
                raise
            time.sleep(0.25)

