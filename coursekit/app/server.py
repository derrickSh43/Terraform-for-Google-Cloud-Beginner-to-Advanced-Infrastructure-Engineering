"""The course app: one browser window with the lesson, an editor and the checks.

    python course.py            # starts the app and opens your browser
    python course.py app --port 8024 --no-browser

Local only: it listens on 127.0.0.1, serves files from this repository, reads and writes only inside
workspace/, and runs the same offline checks as `python course.py check`. Stdlib only. The editor is
Monaco (the editor inside VS Code): from the local cache made by `python course.py setup` (hash-pinned),
else a plain text editor.
"""

from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from contextlib import redirect_stdout
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import guide, paths, runner
from .. import terraform as tf
from . import markdown, update, vendor

STATIC = Path(__file__).with_name("static")
BACKUPS = paths.WORKSPACE / ".backups"     # "start over" moves old work here instead of deleting it
EDITABLE = (".tf", ".tfvars", ".tftpl", ".tpl", ".sh", ".yml", ".yaml", ".md", ".hcl", ".json", ".txt", ".ps1")
SKIP_PARTS = {".terraform", "state", "__pycache__", ".git"}
MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
        ".svg": "image/svg+xml", ".ttf": "font/ttf", ".woff": "font/woff", ".woff2": "font/woff2", ".map": "application/json"}

_check_lock = threading.Lock()
_restart = threading.Event()
BOOT = uuid.uuid4().hex             # changes when the app restarts


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------------- helpers
def _lesson(lid: str) -> paths.Lesson:
    for l in paths.load_lessons():
        if l.id == str(lid).zfill(2):
            return l
    raise ApiError(404, f"no lesson {lid}")


def _target(l: paths.Lesson, which: str) -> Path:
    if which == "broken":
        return paths.WORKSPACE / f"{l.id}-broken"
    return l.workspace


def _safe(root: Path, rel: str) -> Path:
    p = (root / rel).resolve()
    if root.resolve() not in p.parents and p != root.resolve():
        raise ApiError(403, "path outside the workspace")
    return p


def _files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if p.is_file() and p.suffix in EDITABLE and not (SKIP_PARTS & set(rel.parts)) and p.name != ".terraform.lock.hcl":
            out.append(rel.as_posix())
    return sorted(out, key=lambda r: ("/" in r, r))     # root files first, then folders, alphabetically


def _task_json(t: guide.Task) -> dict:
    return {"title": t.title, "ids": t.ids, "html": markdown.render(t.body), "final": t.final}


def lesson_json(l: paths.Lesson) -> dict:
    prog = guide.load_progress()
    prev = paths.previous_lesson(l)
    steps = guide.steps_for(l)
    data = {
        "id": l.id, "title": l.title, "phase": l.phase, "status": l.status,
        "started": l.workspace.exists(),
        "prev": prev.id if prev else None,
        "prev_started": bool(prev and prev.workspace.exists()),
        "steps": steps,
        "progress": prog.get("lessons", {}).get(l.id, {}),
        "readme": markdown.render(l.sub("README.md").read_text(encoding="utf-8")),
        "tasks": {s: [_task_json(t) for t in guide.tasks(l, s)] for s in steps if s != "broken"},
    }
    story, objectives = guide.intro_text(l)
    data["story"], data["objectives"] = story, markdown.render(objectives)
    if "broken" in steps:
        data["broken"] = markdown.render(guide.broken_story(l))
    return data


def course_json() -> dict:
    prog = guide.load_progress()
    ready = [l for l in paths.load_lessons() if l.status == "ready"]
    cur = guide.current_lesson(prog, ready)
    lessons = []
    for l in paths.load_lessons():
        st = prog.get("lessons", {}).get(l.id, {})
        lessons.append({"id": l.id, "title": l.title, "phase": l.phase, "status": l.status,
                        "started": l.workspace.exists(),
                        "done": l.status == "ready" and guide.next_step(l, prog) is None and bool(st)})
    return {"lessons": lessons, "current": cur.id if cur else (ready[-1].id if ready else None),
            "editor": vendor.monaco_url(), "boot": BOOT}


def run_check(l: paths.Lesson, which: str, challenge: bool) -> dict:
    target = _target(l, which)
    if not target.is_dir():
        raise ApiError(409, "nothing to check yet - start the lesson first")
    with _check_lock:                       # one terraform pipeline at a time
        rep = runner.check(l, target, challenge=challenge and which != "broken",
                           build_name=f"{l.id}{'b' if which == 'broken' else ('c' if challenge else 'l')}")
    data = rep.to_json()
    data["passed_ids"] = sorted(o.req.id for o in rep.outcomes if o.passed)
    return data


def run_update() -> dict:
    """Update the course files. The caller restarts the app when this says so."""
    if not _check_lock.acquire(blocking=False):
        raise ApiError(409, "a check is running - update when it has finished")
    try:
        update.apply()
    except update.UpdateError as exc:
        raise ApiError(409, str(exc)) from exc
    finally:
        _check_lock.release()
    return {"ok": True, "boot": BOOT}


def fmt(l: paths.Lesson, which: str) -> dict:
    target = _target(l, which)
    res = tf.run(["fmt", "-recursive", "-list=true", "-no-color", str(target)], cwd=target)
    changed = [Path(x).resolve().relative_to(target.resolve()).as_posix() for x in res.stdout.split() if x.strip()]
    return {"ok": res.ok, "changed": changed, "output": res.output.strip()}


def start(l: paths.Lesson, from_mine: bool) -> dict:
    from .. import cli
    if l.workspace.exists():
        return {"ok": True}
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.cmd_start(argparse.Namespace(lesson=l.id, from_mine=from_mine, force=False))
    prog = guide.load_progress()
    prog["current"] = l.id
    guide.save_progress(prog)
    return {"ok": code == 0, "output": buf.getvalue()}


def start_broken(l: paths.Lesson) -> dict:
    dest = _target(l, "broken")
    if not dest.exists():
        shutil.copytree(l.sub("broken"), dest, ignore=shutil.ignore_patterns("ANSWER.md", "expect.json", "README.md"))
    return {"ok": True}


def reset(l: paths.Lesson, which: str) -> dict:
    dest = _target(l, which)
    if dest.exists():
        shutil.rmtree(dest)
    if which == "broken":
        return start_broken(l)
    return start(l, False)


def start_over(l: paths.Lesson) -> dict:
    """Fresh starter files and no progress for one lesson. The old files are moved to a backup, never deleted."""
    if not _check_lock.acquire(blocking=False):
        raise ApiError(409, "a check is running - try again when it has finished")
    try:
        dest = BACKUPS / f"{l.dirname}-{time.strftime('%Y%m%d-%H%M%S')}"
        moved = []
        for src in (l.workspace, _target(l, "broken")):
            if src.exists():
                dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest / src.name))
                moved.append(src.name)
        prog = guide.load_progress()
        prog.get("lessons", {}).pop(l.id, None)
        guide.save_progress(prog)
        result = start(l, False)
    finally:
        _check_lock.release()
    backup = dest.relative_to(paths.ROOT).as_posix() if moved else None
    return {**result, "backup": backup}


def clean_builds() -> dict:
    """Delete generated build folders (never the provider cache, your work or progress)."""
    if not _check_lock.acquire(blocking=False):
        raise ApiError(409, "a check is running - try again when it has finished")
    try:
        shutil.rmtree(paths.BUILD, ignore_errors=True)    # Python 3.8+ removes junctions without following them
    finally:
        _check_lock.release()
    return {"ok": True}


def set_progress(l: paths.Lesson, body: dict) -> dict:
    prog = guide.load_progress()
    st = prog.setdefault("lessons", {}).setdefault(l.id, {})
    for k, v in body.items():
        if k in ("lab", "challenge", "broken") and v in ("passed", "skipped", None):
            if v is None:
                st.pop(k, None)
            else:
                st[k] = v
        elif k in ("lab_task", "challenge_task") and isinstance(v, int):
            st[k] = v
        elif k in ("lab_read", "challenge_read") and isinstance(v, int) and not isinstance(v, bool):
            # Steps with nothing to check (reading, reflection questions): marked done once read.
            st[k] = sorted(set(st.get(k, [])) | {v})
    prog["current"] = l.id
    guide.save_progress(prog)
    return {"progress": st}


# --------------------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "CourseApp/1"

    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _static(self, base: Path, rel: str) -> None:
        p = (base / rel).resolve()
        if base.resolve() not in p.parents or not p.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = MIME.get(p.suffix, "application/octet-stream")
        if ctype.startswith("text/") or ctype.endswith("json"):
            ctype += "; charset=utf-8"
        self._send(200, p.read_bytes(), ctype)

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def _route(self, method: str) -> None:
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        try:
            # Only this machine's own address, never a name another website controls (DNS rebinding).
            port = self.server.server_address[1]
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in hosts:
                raise ApiError(403, "unexpected host - open the app at the address printed when it started")
            if method == "POST" and self.headers.get("Origin") not in (None, *(f"http://{h}" for h in hosts)):
                raise ApiError(403, "cross-origin request refused")
            if url.path in ("/", "/index.html"):
                return self._static(STATIC, "index.html")
            if url.path.startswith("/static/"):
                return self._static(STATIC, url.path[len("/static/"):])
            if url.path.startswith("/vendor/"):
                return self._static(vendor.VENDOR, url.path[len("/vendor/"):])
            if not url.path.startswith("/api/"):
                raise ApiError(404, "not found")
            body = self._body() if method == "POST" else {}
            lid = body.get("id") or q.get("id")
            which = body.get("target") or q.get("target") or "workspace"
            route = (method, url.path)
            if route == ("GET", "/api/course"):
                return self._json(course_json())
            if route == ("POST", "/api/clean"):
                return self._json(clean_builds())
            if route == ("POST", "/api/stop"):
                self._json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return None
            if route == ("GET", "/api/update"):
                return self._json(update.status())
            if route == ("POST", "/api/update"):
                self._json(run_update())
                _restart.set()
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return None
            l = _lesson(lid)
            if route == ("GET", "/api/lesson"):
                return self._json(lesson_json(l))
            if route == ("GET", "/api/files"):
                return self._json({"files": _files(_target(l, which))})
            if route == ("GET", "/api/file"):
                p = _safe(_target(l, which), q.get("path", ""))
                if not p.is_file():
                    raise ApiError(404, "no such file")
                return self._json({"path": q["path"], "text": p.read_text(encoding="utf-8", errors="replace")})
            if route == ("POST", "/api/file"):
                p = _safe(_target(l, which), body.get("path", ""))
                if p.suffix not in EDITABLE:
                    raise ApiError(400, f"can't edit {p.suffix} files here")
                if body.get("delete"):
                    p.unlink(missing_ok=True)
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(body.get("text", ""), encoding="utf-8", newline="\n")
                return self._json({"ok": True})
            if route == ("POST", "/api/start"):
                return self._json(start_broken(l) if which == "broken" else start(l, bool(body.get("from_mine"))))
            if route == ("POST", "/api/reset"):
                return self._json(start_over(l) if which == "workspace" else reset(l, which))
            if route == ("POST", "/api/check"):
                return self._json(run_check(l, which, bool(body.get("challenge"))))
            if route == ("POST", "/api/fmt"):
                return self._json(fmt(l, which))
            if route == ("POST", "/api/progress"):
                return self._json(set_progress(l, body.get("progress") or {}))
            if route == ("GET", "/api/answer"):
                return self._json({"html": markdown.render((l.sub("broken") / "ANSWER.md").read_text(encoding="utf-8"))})
            raise ApiError(404, "unknown endpoint")
        except ApiError as exc:
            self._json({"error": str(exc)}, exc.status)
        except Exception as exc:  # keep the app alive; show the error in the UI
            self._json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def serve(port: int = 8024, open_browser: bool = True, lesson: str | None = None) -> int:
    paths.WORKSPACE.mkdir(exist_ok=True)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)     # port busy: pick a free one
    url = f"http://127.0.0.1:{httpd.server_address[1]}/" + (f"?lesson={_lesson(lesson).id}" if lesson else "")
    print(f"Course app running at {url}")
    print("Keep this window open while you work. Files save automatically and progress is saved as you go.")
    print("To quit: click 'Save & quit' in the app, or press Ctrl+C here.")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    if not _restart.is_set():
        print("\nStopped. Your work and progress are saved. Start again with: python course.py")
        return 0
    print("Updated. Restarting the course app...")
    cmd = [sys.executable, str(paths.ROOT / "course.py"), "app", "--port", str(httpd.server_address[1]), "--no-browser"]
    try:
        return subprocess.call(cmd)         # new process: Python code may have changed too
    except KeyboardInterrupt:
        return 0
