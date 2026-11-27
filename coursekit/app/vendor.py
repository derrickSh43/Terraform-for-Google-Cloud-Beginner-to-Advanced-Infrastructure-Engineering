"""Browser libraries for the course app, cached locally so the app works offline.

- Monaco (the VS Code editor): `min/` into .course/vendor/monaco.
- Mermaid (draws the lessons' diagrams): `dist/mermaid.min.js` into .course/vendor/mermaid.

`python course.py setup` downloads each pinned package once from the npm registry and checks it
against the sha512 hash pinned below (not one the registry reports). Without the cache the page
falls back (a plain editor, diagram source as text): the app never runs code fetched at page load.
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
MERMAID_VERSION = "12.3.0"
MERMAID_INTEGRITY = "sha512-4113TdXeLAsMruJ79OpFL5O8+LTFXhQqZ260rF3tgUmiNAtRm4Uume04I+65PRN6yZ69J4f8rVYWW8zRk65UYw=="
VENDOR = paths.STATE_DIR / "vendor"
MONACO_DIR = VENDOR / "monaco"
MERMAID_DIR = VENDOR / "mermaid"
MERMAID_FILES = ("dist/mermaid.min.js", "LICENSE")


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


def mermaid_url() -> str | None:
    """Where the page should load Mermaid from (None: show diagram source instead)."""
    return f"/vendor/mermaid/dist/mermaid.min.js?v={MERMAID_VERSION}" if (MERMAID_DIR / MERMAID_FILES[0]).is_file() else None


def extract_min(tgz: bytes, dest: Path) -> int:
    """Unpack package/min/** from an npm tarball into dest/min (refusing unsafe paths). Returns files written."""
    return _extract(tgz, dest, lambda rel: rel.startswith("min/"))


def _extract(tgz: bytes, dest: Path, wanted) -> int:
    """Unpack the package/<rel> members for which wanted(rel) is true into dest/<rel>. Returns files written."""
    count = 0
    tmp = dest.with_name(dest.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as tar:
        for m in tar.getmembers():
            if not m.isfile() or not m.name.startswith("package/") or not wanted(m.name[len("package/"):]):
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


def install_mermaid(timeout: int = 120) -> str:
    """Download, verify and unpack Mermaid's single-file bundle. Returns a one-line status."""
    if mermaid_url():
        return f"Mermaid {MERMAID_VERSION} already cached"
    url = f"https://registry.npmjs.org/mermaid/-/mermaid-{MERMAID_VERSION}.tgz"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = r.read()
    if not _verify(data, MERMAID_INTEGRITY):
        raise RuntimeError("mermaid download failed its integrity check - not installed")
    VENDOR.mkdir(parents=True, exist_ok=True)
    _extract(data, MERMAID_DIR, lambda rel: rel in MERMAID_FILES)
    return f"Mermaid {MERMAID_VERSION} cached ({len(data) // 1024} KiB download)"
