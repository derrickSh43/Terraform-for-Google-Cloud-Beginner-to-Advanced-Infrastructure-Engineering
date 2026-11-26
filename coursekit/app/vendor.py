"""Monaco (the VS Code editor) for the course app, cached locally so the app works offline.

`python course.py setup` downloads the pinned monaco-editor package once from the npm registry,
checks it against the sha512 hash pinned below (not one the registry reports), and unpacks only `min/`
into .course/vendor/monaco. Without the cache the page uses a plain editor: the app never runs editor
code fetched at page load.
"""

from __future__ import annotations

import base64
import hashlib
import io
import shutil
import tarfile
import urllib.request
from pathlib import Path

from .. import paths

MONACO_VERSION = "0.52.2"
MONACO_INTEGRITY = "sha512-GEQWEZmfkOGLdd3XK8ryrfWz3AIP8YymVXiPHEdewrUq7mh0qrKrfHLNCXcbB6sTnMLnOZ3ztSiKcciFUkIJwQ=="
VENDOR = paths.STATE_DIR / "vendor"
MONACO_DIR = VENDOR / "monaco"


def monaco_url() -> dict:
    """Where the page should load Monaco from."""
    if (MONACO_DIR / "min" / "vs" / "loader.js").is_file():
        return {"vs": "/vendor/monaco/min/vs", "source": "local"}
    return {"vs": None, "source": "none"}


def _verify(data: bytes, integrity: str) -> bool:
    algo, _, digest = integrity.partition("-")
    if algo != "sha512":
        return False
    return base64.b64encode(hashlib.sha512(data).digest()).decode() == digest


def extract_min(tgz: bytes, dest: Path) -> int:
    """Unpack package/min/** from an npm tarball into dest/min (refusing unsafe paths). Returns files written."""
    count = 0
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or not m.name.startswith("package/min/"):
                continue
            rel = Path(m.name[len("package/"):])
            if ".." in rel.parts or rel.is_absolute():
                continue
            out = tmp / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            src = tar.extractfile(m)
            if src is not None:
                out.write_bytes(src.read())
                count += 1
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    return count


def install_monaco(timeout: int = 60) -> str:
    """Download, verify and unpack Monaco. Returns a one-line status."""
    if monaco_url()["source"] == "local":
        return f"Monaco {MONACO_VERSION} already cached"
    url = f"https://registry.npmjs.org/monaco-editor/-/monaco-editor-{MONACO_VERSION}.tgz"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = r.read()
    if not _verify(data, MONACO_INTEGRITY):
        raise RuntimeError("monaco-editor download failed its integrity check - not installed")
    VENDOR.mkdir(parents=True, exist_ok=True)
    n = extract_min(data, MONACO_DIR)
    return f"Monaco {MONACO_VERSION} cached ({n} files, {len(data) // 1024} KiB download)"
