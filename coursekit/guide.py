"""Guided mode: `python course.py` walks you through the course in order.

No menus. It remembers where you are (workspace/.progress.json) and moves you along:

    lesson intro -> lab -> challenge -> troubleshooting -> next lesson

At each step you edit files in your editor and press Enter to check. When the check passes, the
next step starts by itself. `s` skips a step, `o` opens the instructions, `q` stops (progress is kept).

    python course.py          continue where you left off
    python course.py 05       jump to lesson 05
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import docs, paths, runner
from .report import c, print_report

Input = Callable[[str], str]
PROGRESS = paths.WORKSPACE / ".progress.json"
STEPS = ("lab", "challenge", "broken")
STEP_NAMES = {"lab": "Lab", "challenge": "Challenge", "broken": "Troubleshooting"}
RULE = "─" * 64


class Stop(Exception):
    pass


# --------------------------------------------------------------------------- progress
def load_progress(path: Path | None = None) -> dict:
    try:
        return json.loads((path or PROGRESS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"current": None, "lessons": {}}


def save_progress(data: dict, path: Path | None = None) -> None:
    path = path or PROGRESS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def steps_for(lesson: paths.Lesson) -> list[str]:
    out = ["lab"]
    if lesson.sub("challenge.md").exists():
        out.append("challenge")
    if (lesson.sub("broken") / "README.md").exists():
        out.append("broken")
    return out


def next_step(lesson: paths.Lesson, progress: dict) -> str | None:
    """First step of the lesson not yet passed or skipped; None = lesson finished."""
    state = progress.get("lessons", {}).get(lesson.id, {})
    return next((s for s in steps_for(lesson) if state.get(s) not in ("passed", "skipped")), None)


def current_lesson(progress: dict, ready: list[paths.Lesson]) -> paths.Lesson | None:
    """The lesson in progress; once it's finished, the next unfinished one after it (then any earlier one)."""
    cur = progress.get("current") or ""
    match = [l for l in ready if l.id == cur]
    if match and next_step(match[0], progress):
        return match[0]
    after = [l for l in ready if l.id > cur] + [l for l in ready if l.id <= cur]
    return next((l for l in after if next_step(l, progress)), None)


def mark(progress: dict, lesson: paths.Lesson, step: str, status: str) -> None:
    progress.setdefault("lessons", {}).setdefault(lesson.id, {})[step] = status
    progress["current"] = lesson.id
    save_progress(progress)


# --------------------------------------------------------------------------- text helpers
def intro_text(lesson: paths.Lesson) -> tuple[str, str]:
    """(story, objectives) from the lesson README."""
    text = lesson.sub("README.md").read_text(encoding="utf-8")
    story = "\n".join(l[1:].strip() for l in text.splitlines() if l.startswith(">"))
    sec = docs.find_section(text, "learning objectives")
    bullets = [l.strip() for l in (sec.body if sec else "").splitlines() if l.strip().startswith(("-", "*"))]
    return story, "\n".join(bullets)


def broken_story(lesson: paths.Lesson) -> str:
    """The troubleshooting README without its copy/run instructions (the guide does that part)."""
    text = (lesson.sub("broken") / "README.md").read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    keep = [l for l in text.splitlines() if not re.match(r"^\s*(Answer:|Stuck after|#)", l)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip()


def _clear() -> None:
    if sys.stdout.isatty() and os.environ.get("TERM") != "dumb":
        print("\033[2J\033[H", end="", flush=True)


def _open(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
            return
        opener = "open" if sys.platform == "darwin" else shutil.which("xdg-open")
        if opener:
            subprocess.run([opener, str(path)], check=False)
            return
    except OSError:
        pass
    print(path.read_text(encoding="utf-8"))


def _rel(p: Path) -> str:
    return str(p.relative_to(paths.ROOT))


# --------------------------------------------------------------------------- tasks
@dataclass
class Task:
    title: str
    ids: list[str]           # requirement IDs this task is checked by ([] = read-only info)
    body: str
    final: bool = False      # the closing "everything passes" check


_ID = re.compile(r"\b([RC]\d+)\.(\d+)\b(?:\s*[–-]\s*(?:[RC]\d+\.)?(\d+)\b)?")


def requirement_ids(text: str) -> list[str]:
    """'R1.4 – R1.7', 'R2.1, R2.2' -> expanded IDs, in order."""
    out: list[str] = []
    for m in _ID.finditer(text):
        lo = int(m.group(2))
        hi = int(m.group(3)) if m.group(3) else lo
        out += [f"{m.group(1)}.{n}" for n in range(lo, max(lo, hi) + 1)]
    return out


_SKIP_SECTIONS = re.compile(r"^(done\??|next|answer)\b", re.I)


def tasks(lesson: paths.Lesson, step: str) -> list[Task]:
    """Lab: one task per `## ...` section of lab.md (IDs from its heading).
    Challenge: one task per requirement row of challenge.md's table, then its other sections.
    Both end with a final check of everything (guard rails included)."""
    out: list[Task] = []
    if step == "lab":
        text = lesson.sub("lab.md").read_text(encoding="utf-8")
        first_h2 = re.search(r"^## ", text, re.M)
        preamble = text[: first_h2.start() if first_h2 else 0].split("\n", 1)[-1]
        preamble = re.sub(r"```.*?```", "", preamble, flags=re.S).replace("---", "").strip()
        if docs.words(preamble) >= 20:
            out.append(Task("Before you start", [], preamble))
        for s in docs.sections(text):
            if s.level != 2 or _SKIP_SECTIONS.match(s.title):
                continue
            title = re.sub(r"\s*\((?:[RC]\d+\.\d+[^)]*)\)\s*$", "", s.title).strip()
            out.append(Task(title, requirement_ids(s.title), s.body.strip()))
        final = "Everything in the lab must pass, including the guard rails that protect what's already deployed."
    else:
        text = lesson.sub("challenge.md").read_text(encoding="utf-8")
        for line in text.splitlines():
            m = re.match(r"^\|\s*([RC]\d+\.\d+)\s*\|(.*)\|\s*$", line)
            if m:
                body = m.group(2).replace("\\|", "|").strip()
                head = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", body)
                title = head.group(1).rstrip(".") if head else m.group(1)
                out.append(Task(f"{m.group(1)} {title}" if head else m.group(1), [m.group(1)], head.group(2) if head else body))
        for s in docs.sections(text):
            if s.level == 2 and not _SKIP_SECTIONS.match(s.title):
                out.append(Task(s.title, [], s.body.strip()))
        final = "Lab and challenge requirements together, one last time."
    out.append(Task("Final check", [], final, final=True))
    return out


def render(md: str) -> str:
    """Markdown -> readable terminal text: code blocks indented and coloured, emphasis and links simplified."""
    lines, in_code = [], False
    for line in md.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            lines.append(c("    " + line, "33"))
            continue
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: m.group(1) if m.group(2).endswith(".md") or m.group(2).startswith(("#", "../")) else f"{m.group(1)} ({m.group(2)})", line)
        line = re.sub(r"\*\*(.+?)\*\*", lambda m: c(m.group(1), "1"), line)
        line = re.sub(r"`([^`]+)`", lambda m: c(m.group(1), "36"), line)
        line = re.sub(r"^#{3,}\s*(.*)$", lambda m: c(m.group(1), "1"), line)
        if re.match(r"^\s*\|?\s*:?-{3,}", line):
            continue
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# --------------------------------------------------------------------------- the guide
@dataclass
class Guide:
    inp: Input = input
    progress: dict | None = None

    def ask(self, prompt: str) -> str:
        try:
            return self.inp(c(prompt, "36")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            raise Stop

    def header(self, lesson: paths.Lesson, step: str | None) -> None:
        _clear()
        steps = steps_for(lesson)
        state = self.progress.get("lessons", {}).get(lesson.id, {})
        trail = []
        for s in steps:
            done = state.get(s)
            icon = "✓" if done == "passed" else ("–" if done == "skipped" else ("●" if s == step else "○"))
            col = "32" if done == "passed" else ("36;1" if s == step else "90")
            trail.append(c(f"{icon} {STEP_NAMES[s]}", col))
        print(c(f"Lesson {lesson.id} · {lesson.title}", "1"))
        print("   ".join(trail))
        print(c(RULE, "90"))

    # ---- whole course
    def run(self, start_at: str | None = None) -> int:
        self.progress = self.progress or load_progress()
        ready = [l for l in paths.load_lessons() if l.status == "ready"]
        try:
            if start_at:
                lesson = paths.find_lesson(start_at)
                if lesson.status != "ready":
                    print(f"Lesson {lesson.id} isn't published yet.")
                    return 1
                if next_step(lesson, self.progress) is None:
                    if self.ask(f"You've finished lesson {lesson.id}. Do it again? [y/N] ") not in ("y", "yes"):
                        return 0
                    self.progress.setdefault("lessons", {}).pop(lesson.id, None)
                self.progress["current"] = lesson.id
                save_progress(self.progress)
            while True:
                lesson = current_lesson(self.progress, ready)
                if lesson is None:
                    _clear()
                    print(c("You've finished every lesson. Congratulations!", "32;1"))
                    print("Run `python course.py 24` (or any number) to revisit a lesson.")
                    return 0
                self.lesson(lesson)
                later = [l for l in ready if l.id > lesson.id]
                if not later:
                    continue
                print()
                print(c(f"Lesson {lesson.id} complete. ", "32;1") + f"Next up: lesson {later[0].id}, {later[0].title}.")
                if self.ask("Press Enter to continue, or q to stop here: ") == "q":
                    return 0
                self.progress["current"] = later[0].id
                save_progress(self.progress)
        except Stop:
            print(c("Progress saved. Run `python course.py` to pick up where you left off.", "90"))
            return 0

    # ---- one lesson
    def lesson(self, lesson: paths.Lesson) -> None:
        if not lesson.workspace.exists():
            self.intro(lesson)
        while (step := next_step(lesson, self.progress)) is not None:
            if step == "broken":
                self.troubleshoot(lesson)
            else:
                self.work(lesson, step)

    def intro(self, lesson: paths.Lesson) -> None:
        self.header(lesson, None)
        story, objectives = intro_text(lesson)
        if story:
            print(c(story, "3"))
            print()
        if objectives:
            print(c("You'll learn to:", "1"))
            print(objectives)
            print()
        prev = paths.previous_lesson(lesson)
        from_mine = False
        if prev and prev.workspace.exists() and lesson.project:
            ans = self.ask(f"Continue from your own lesson {prev.id} work? [Y/n] ")
            from_mine = ans not in ("n", "no")
        else:
            self.ask("Press Enter to set up your workspace... ")
        from . import cli
        import argparse
        with redirect_stdout(io.StringIO()):
            cli.cmd_start(argparse.Namespace(lesson=lesson.id, from_mine=from_mine, force=False))
        self.progress["current"] = lesson.id
        save_progress(self.progress)

    def work(self, lesson: paths.Lesson, step: str) -> None:
        """The lab or challenge, one task at a time: show it, Enter checks it, a pass moves on."""
        challenge = step == "challenge"
        doc = lesson.sub("challenge.md" if challenge else "lab.md")
        task_list = tasks(lesson, step)
        state = self.progress.setdefault("lessons", {}).setdefault(lesson.id, {})
        key_i = f"{step}_task"
        while True:
            i = min(state.get(key_i, 0), len(task_list) - 1)
            t = task_list[i]
            self.header(lesson, step)
            print(c(f"{STEP_NAMES[step]} · task {i + 1} of {len(task_list)}: {t.title}", "1"))
            print(c(f"Your files: {_rel(lesson.workspace)}", "90"))
            print()
            print(render(t.body))
            info = not t.ids and not t.final
            prompt = ("\nEnter = continue" if info else "\nEnter = check") + f" · o = open {doc.name} · s = skip task · q = quit: "
            while True:
                key = self.ask(prompt)
                if key == "q":
                    raise Stop
                if key == "o":
                    _open(doc)
                    continue
                break
            if key == "s":
                if t.final:
                    if self.ask(f"Skip the rest of the {STEP_NAMES[step].lower()}? [y/N] ") in ("y", "yes"):
                        mark(self.progress, lesson, step, "skipped")
                        return
                    continue
                self.advance(state, key_i, i + 1)
                continue
            if info:
                self.advance(state, key_i, i + 1)
                continue
            result = self.check_task(lesson, step, task_list, i, state, key_i, doc)
            if result == "complete":
                return
            if result == "skip":
                if t.final:
                    if self.ask(f"Skip the rest of the {STEP_NAMES[step].lower()}? [y/N] ") in ("y", "yes"):
                        mark(self.progress, lesson, step, "skipped")
                        return
                else:
                    self.advance(state, key_i, i + 1)

    def advance(self, state: dict, key: str, to: int) -> None:
        state[key] = to
        save_progress(self.progress)

    def check_task(self, lesson, step, task_list, i, state, key_i, doc) -> str:
        """Check until this task passes: "next" (moved on), "complete" (lab/challenge done) or "skip"."""
        while True:
            result = self._check_once(lesson, step, task_list, i, state, key_i)
            if result:
                return result
            while True:
                key = self.ask(f"\nFix it, save, then Enter = check again · o = open {doc.name} · s = skip task · q = quit: ")
                if key == "q":
                    raise Stop
                if key == "s":
                    return "skip"
                if key == "o":
                    _open(doc)
                    continue
                break

    def _check_once(self, lesson, step, task_list, i, state, key_i) -> str | None:
        t = task_list[i]
        print(c("\nChecking... (terraform fmt, init, validate, plan, then the requirements)", "90"))
        rep = runner.check(lesson, lesson.workspace, challenge=step == "challenge")
        passed = {o.req.id for o in rep.outcomes if o.passed}
        known = {o.req.id for o in rep.outcomes}
        print()
        for s in rep.stages:
            if s.status == runner.FAIL:
                print(c(f"  FAIL  {s.name}: {s.summary}", "31"))
                if s.detail:
                    print("\n".join("        " + l for l in s.detail.strip().splitlines()[:25]))
        if t.final:
            if rep.passed:
                mark(self.progress, lesson, step, "passed")
                self.ask(c(f"\n✓ {STEP_NAMES[step]} complete! Press Enter for the next part... ", "32;1"))
                return "complete"
            for o in rep.outcomes:
                if not o.passed:
                    self.show_outcome(o)
            return None
        for o in rep.outcomes:
            if o.req.id in t.ids:
                self.show_outcome(o)

        def done(task):
            mine = [x for x in task.ids if x in known]
            return bool(mine) and all(x in passed for x in mine)

        if done(t):
            j = i + 1
            while j < len(task_list) and task_list[j].ids and done(task_list[j]):
                j += 1                     # later tasks that already pass
            skipped = j - i - 1
            self.advance(state, key_i, j)
            extra = f" (the next {skipped} already pass{'' if skipped > 1 else 'es'} too)" if skipped else ""
            self.ask(c(f"\n✓ Task done{extra}. Press Enter for the next one... ", "32;1"))
            return "next"
        if not rep.outcomes:
            print(c("  The requirement checks couldn't run yet - fix the failure above first.", "33"))
        return None

    @staticmethod
    def show_outcome(o) -> None:
        if o.passed:
            print(c(f"  PASS  {o.req.id}  {o.req.title}", "32"))
            return
        print(c(f"  FAIL  {o.req.id}  {o.req.title}", "31"))
        if o.message:
            print("\n".join("        " + l for l in o.message.strip().splitlines()[:12]))
        if o.req.hint:
            print(c(f"        hint: {o.req.hint}", "36"))

    def troubleshoot(self, lesson: paths.Lesson) -> None:
        dest = paths.WORKSPACE / f"{lesson.id}-broken"
        if not dest.exists():
            shutil.copytree(lesson.sub("broken"), dest, ignore=shutil.ignore_patterns("ANSWER.md", "expect.json", "README.md"))
        story = broken_story(lesson)
        redraw = True
        while True:
            if redraw:
                self.header(lesson, "broken")
                print(story)
                print()
                print(f"The broken configuration is in:  {_rel(dest)}")
                print("Press Enter to see what fails, then find the fault and fix it there.")
            redraw = False
            key = self.ask("\nEnter = check the fix · a = show the answer · s = skip · q = quit: ")
            if key == "q":
                raise Stop
            if key == "a":
                self.answer(lesson)
                continue
            if key == "s":
                if self.ask("Skip troubleshooting? [y/N] ") in ("y", "yes"):
                    mark(self.progress, lesson, "broken", "skipped")
                    return
                continue
            self.header(lesson, "broken")
            print(c("Checking your fix...", "90"))
            rep = runner.check(lesson, dest, challenge=False, build_name=f"{lesson.id}b")
            self.header(lesson, "broken")
            print_report(rep)
            if rep.passed:
                mark(self.progress, lesson, "broken", "passed")
                print(c("Fixed! Compare your reasoning with the answer:", "32;1"))
                self.answer(lesson, pause=False)
                self.ask("\nPress Enter to finish the lesson... ")
                return
            print(c("Still failing. Fix it in the broken copy, save, and press Enter to check again.", "33"))

    def answer(self, lesson: paths.Lesson, pause: bool = True) -> None:
        print()
        print(c(RULE, "90"))
        print((lesson.sub("broken") / "ANSWER.md").read_text(encoding="utf-8").strip())
        print(c(RULE, "90"))
        if pause:
            self.ask("Press Enter to go back... ")


# --------------------------------------------------------------------------- batch checks (check-all)
def check_many(lessons: list[paths.Lesson], *, challenge: bool, broken: bool = False) -> list[tuple[str, str, runner.Report]]:
    results = []
    for l in lessons:
        jobs = [("lab", l.workspace, False)]
        if challenge and l.sub("challenge.md").exists():
            jobs.append(("challenge", l.workspace, True))
        bdir = paths.WORKSPACE / f"{l.id}-broken"
        if broken and bdir.exists():
            jobs.append(("broken", bdir, False))
        for what, target, ch in jobs:
            print(f"  {l.id} {what:<9} ", end="", flush=True)
            rep = runner.check(l, target, challenge=ch, build_name=f"{l.id}m{what[0]}")
            met, total = sum(o.passed for o in rep.outcomes), len(rep.outcomes)
            if rep.passed:
                print(c("PASS", "32"), c(f"{met}/{total} requirements", "90"))
            else:
                stages = ", ".join(sorted(rep.failed_stages))
                print(c("FAIL", "31"), c(f"stage failed: {stages}" if stages else f"{met}/{total} requirements", "90"))
            results.append((l.id, what, rep))
    return results
