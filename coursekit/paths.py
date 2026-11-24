"""Well-known locations inside the course repository."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "lessons"
WORKSPACE = ROOT / "workspace"
SHARED_TF = ROOT / "shared" / "terraform"
SHARED_LOCK = SHARED_TF / ".terraform.lock.hcl"
STATE_DIR = ROOT / ".course"          # git-ignored: caches and build dirs
PLUGIN_CACHE = STATE_DIR / "plugin-cache"
BUILD = STATE_DIR / "build"

MIN_TERRAFORM = (1, 9, 0)


@dataclass
class Lesson:
    id: str
    slug: str
    title: str
    phase: int
    status: str            # "ready" | "planned"
    project: bool          # part of the evolving Meridian project?
    path: Path
    roots: dict[str, str] = field(default_factory=lambda: {"main": ""})  # name -> root dir in the tree
    states: dict[str, str] = field(default_factory=dict)                 # root name -> prepared state file
    starter_previous: str = ""   # where the starter keeps the previous lesson's solution
    state_from: str = "previous" # "previous" = state matches the previous solution; "starter" = this starter
    cloud: dict[str, str] = field(default_factory=dict)     # root name -> inventory of hand-made objects (cloudsim)
    expected_drift: list[str] = field(default_factory=list) # state addresses deliberately edited (drift drills)

    @property
    def primary(self) -> str:
        return next(iter(self.roots))

    def state_paths(self) -> dict[str, Path]:
        return {self.roots[name]: self.path / rel for name, rel in self.states.items()}

    def cloud_paths(self) -> dict[str, Path]:
        return {self.roots[name]: self.path / rel for name, rel in self.cloud.items()}

    @property
    def dirname(self) -> str:
        return self.path.name

    @property
    def workspace(self) -> Path:
        return WORKSPACE / self.dirname

    def sub(self, name: str) -> Path:
        return self.path / name


def load_lessons() -> list[Lesson]:
    lessons = []
    for meta in sorted(LESSONS.glob("*/lesson.json")):
        data = json.loads(meta.read_text(encoding="utf-8"))
        lessons.append(
            Lesson(
                id=data["id"],
                slug=data["slug"],
                title=data["title"],
                phase=data["phase"],
                status=data.get("status", "planned"),
                project=data.get("project", True),
                path=meta.parent,
                roots=data.get("roots") or {"main": ""},
                states=data.get("state", {}),
                starter_previous=data.get("starter_previous", ""),
                state_from=data.get("state_from", "previous"),
                cloud=data.get("cloud", {}),
                expected_drift=data.get("expected_drift", []),
            )
        )
    return lessons


def find_lesson(key: str) -> Lesson:
    """Accept '3', '03', '03-compute-vm' or 'compute-vm'."""
    key = key.strip().lower()
    for lesson in load_lessons():
        if key in (lesson.id, lesson.id.lstrip("0"), lesson.dirname, lesson.slug):
            return lesson
    raise SystemExit(f"Unknown lesson '{key}'. Run `python course.py list` to see lessons.")


def previous_lesson(lesson: Lesson) -> Lesson | None:
    ordered = [l for l in load_lessons() if l.project]
    for i, l in enumerate(ordered):
        if l.id == lesson.id:
            return ordered[i - 1] if i > 0 else None
    return None
