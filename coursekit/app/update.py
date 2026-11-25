"""In-app updates: fast-forward this clone to the branch it tracks on GitHub.

Lesson work and progress live in workspace/, which git ignores, so an update never touches them.
Only a clone that tracks a remote branch can update itself; anywhere else the button stays hidden.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .. import paths

MAX_CHANGES = 12


class UpdateError(Exception):
    pass


def _git(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "LC_ALL": "C"}     # never wait for a password
    try:
        return subprocess.run(["git", *args], cwd=paths.ROOT, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", "git took too long")


def _out(*args: str) -> str:
    res = _git(*args)
    return res.stdout.strip() if res.returncode == 0 else ""


def supported() -> bool:
    """True when this folder is itself a git clone whose current branch tracks a remote branch."""
    if not shutil.which("git"):
        return False
    top = _out("rev-parse", "--show-toplevel")
    return bool(top) and Path(top).resolve() == paths.ROOT.resolve() and bool(_out("rev-parse", "--abbrev-ref", "@{u}"))


def status() -> dict:
    """Ask GitHub what's new. Never raises: no network just means no update is offered."""
    if not supported():
        return {"supported": False, "count": 0, "changes": []}
    fetched = _git("fetch", "--quiet")
    data = {"supported": True, "version": _out("log", "-1", "--format=%h (%cs)"), "count": 0, "changes": []}
    if fetched.returncode != 0:
        return {**data, "error": "Could not reach GitHub. Check your internet connection and try again."}
    data["count"] = int(_out("rev-list", "--count", "HEAD..@{u}") or 0)
    data["changes"] = _out("log", f"-{MAX_CHANGES}", "--format=%s", "HEAD..@{u}").splitlines()
    return data


def apply() -> None:
    """Fast-forward to the fetched version, or explain why that isn't possible. Never merges or discards anything."""
    if not supported():
        raise UpdateError("This copy of the course can't update itself. Clone it with git (see the README) to get updates.")
    res = _git("merge", "--ff-only", "--quiet", "@{u}")
    if res.returncode == 0:
        return
    out = (res.stderr + res.stdout).strip()
    if "would be overwritten" in out:
        files = [line.strip() for line in out.splitlines() if line.startswith("\t")]
        raise UpdateError("Not updated: you changed course files that the update also changes: " + ", ".join(files)
                          + ". Undo your change with `git checkout -- <file>` (delete it if it's a new file), then update again.")
    if int(_out("rev-list", "--count", "@{u}..HEAD") or 0):
        raise UpdateError("Not updated: this copy has commits of its own. Run `git pull --rebase` in the course folder.")
    raise UpdateError("Not updated: " + (out or "git failed"))
