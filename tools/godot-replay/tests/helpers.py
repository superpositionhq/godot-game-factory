"""Shared by the replay tests: the tool's modules on the path, a scratch folder, small git repos with dated commits
and recorded-action rows."""
import datetime
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(TOOL))
for p in (TOOL, os.path.join(REPO, "machine", "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

T0 = datetime.datetime(2026, 1, 10, 10, 0, 0, tzinfo=datetime.timezone.utc)


def scratch(prefix="ggfr"):
    """A new folder for a test's files: under GGF_TEST_SCRATCH when set, else the system's temporary folder."""
    base = os.environ.get("GGF_TEST_SCRATCH") or None
    if base:
        os.makedirs(base, exist_ok=True)
    return os.path.realpath(tempfile.mkdtemp(prefix=prefix, dir=base)).replace("\\", "/")


def at(minutes, seconds=0):
    """A time `minutes` after the first commit's, as the recorder writes it."""
    return (T0 + datetime.timedelta(minutes=minutes, seconds=seconds)).isoformat(timespec="milliseconds")


def write(root, rel, text):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(text if isinstance(text, bytes) else text.encode("utf-8"))


def read(root, rel):
    with open(os.path.join(root, rel), "rb") as f:
        return f.read().decode("utf-8")


def git(repo, *args, env=None):
    e = dict(os.environ, GIT_AUTHOR_NAME="Builder", GIT_AUTHOR_EMAIL="builder@example.invalid",
             GIT_COMMITTER_NAME="Builder", GIT_COMMITTER_EMAIL="builder@example.invalid")
    e.update(env or {})
    r = subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false"] + list(args),
                       capture_output=True, env=e)
    if r.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace")))
    return r.stdout.decode("utf-8")


def commit(repo, minutes, subject):
    """Commit everything, dated `minutes` after the first commit. Returns the sha."""
    when = (T0 + datetime.timedelta(minutes=minutes)).isoformat()
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", subject, env={"GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    return git(repo, "rev-parse", "HEAD").strip()


class Recording:
    """Rows of .recording/<slug>/actions.jsonl as the action recorder writes them."""

    def __init__(self, folder, repo):
        self.folder, self.repo, self.n = folder, repo, 0
        os.makedirs(folder, exist_ok=True)
        open(os.path.join(folder, "actions.jsonl"), "w").close()

    def row(self, time, tool, inp, response=None, event="PostToolUse"):
        self.n += 1
        r = {"time": time, "tool": tool, "event": event, "tool_use_id": "toolu_%04d" % self.n, "session_id": "s1",
             "agent": "claude", "cwd": self.repo, "input": inp, "response": response}
        with open(os.path.join(self.folder, "actions.jsonl"), "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(r) + "\n")
        return r

    def write(self, time, rel, content):
        """A Write of a repo file, done to the file too."""
        write(self.repo, rel, content)
        return self.row(time, "Write", {"file_path": self.repo + "/" + rel, "content": content})

    def edit(self, time, rel, old, new):
        """An Edit of a repo file, done to the file too."""
        text = read(self.repo, rel)
        assert old in text, (rel, old)
        write(self.repo, rel, text.replace(old, new, 1))
        return self.row(time, "Edit", {"file_path": self.repo + "/" + rel, "old_string": old, "new_string": new})

    def bash(self, time, command, stdout=""):
        return self.row(time, "Bash", {"command": command}, {"stdout": stdout, "stderr": ""})
