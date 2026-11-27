"""Command-line interface: `python course.py <command>`."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import paths, runner, selftest
from . import terraform as tf
from .report import c, print_report

PLATFORMS = ["windows_amd64", "linux_amd64", "linux_arm64", "darwin_amd64", "darwin_arm64"]


# --------------------------------------------------------------------------- setup
def cmd_setup(args: argparse.Namespace) -> int:
    ok = True
    print(c("Checking your tools", "1"))
    py = sys.version_info
    print(f"  python     {py.major}.{py.minor}.{py.micro}  " + (c("ok", "32") if py >= (3, 10) else c("need 3.10+", "31")))
    ok &= py >= (3, 10)

    ver = tf.version()
    if not ver:
        print("  terraform  " + c("not found", "31"))
        print("             Install: https://developer.hashicorp.com/terraform/install")
        print("             Windows: winget install Hashicorp.Terraform")
        print("             macOS:   brew tap hashicorp/tap && brew install hashicorp/tap/terraform")
        return 1
    good = ver >= paths.MIN_TERRAFORM
    print(f"  terraform  {'.'.join(map(str, ver))}  " + (c("ok", "32") if good else c("need 1.9+", "31")))
    ok &= good
    print("  tflint     " + (c("found", "32") if shutil.which("tflint") else c("not installed (optional)", "90")))
    print("  gcloud     " + c("not needed - this course never contacts Google Cloud", "90"))

    print()
    print(c("Downloading pinned providers from the Terraform Registry", "1"))
    print(c(f"  cache: {paths.PLUGIN_CACHE}", "90"))
    res = tf.run(["init", "-backend=false", "-input=false", "-no-color"], cwd=paths.SHARED_TF)
    for line in res.output.splitlines():
        if "Installed" in line or "Reusing" in line or "Using" in line or "Error" in line:
            print("  " + line.strip("- "))
    if not res.ok:
        print(c("  Provider download failed. Are you online? Behind a proxy, set HTTPS_PROXY.", "31"))
        print("  For air-gapped machines see docs/SETUP.md (python course.py mirror).")
        return 1
    print(c("  Providers cached - every lesson now initializes from the local cache.", "32"))

    print()
    print(c("Caching the code editor for the course app (Monaco, the editor inside VS Code)", "1"))
    try:
        from .app import vendor
        print("  " + vendor.install_monaco())
    except Exception as exc:  # optional: the app falls back to a plain editor
        print(c(f"  Skipped ({exc}). The app uses a plain editor until setup succeeds.", "33"))
    print(c("Caching the diagram renderer for the lesson pages (Mermaid)", "1"))
    try:
        from .app import vendor
        print("  " + vendor.install_mermaid())
    except Exception as exc:  # optional: diagrams show as source text
        print(c(f"  Skipped ({exc}). Diagrams show as source text until setup succeeds.", "33"))

    paths.WORKSPACE.mkdir(exist_ok=True)
    print()
    print(c("Ready." if ok else "Setup finished with warnings.", "32;1" if ok else "33;1"), "Next:  python course.py   (opens the course app)")
    return 0 if ok else 1


def cmd_mirror(args: argparse.Namespace) -> int:
    dest = Path(args.dir).resolve()
    plats = [f"-platform={p}" for p in (args.platform or PLATFORMS)]
    print(c(f"Mirroring pinned providers into {dest}", "1"))
    res = tf.run(["providers", "mirror", *plats, str(dest)], cwd=paths.SHARED_TF, timeout=1800)
    print(res.output)
    if not res.ok:
        return 1
    print(c("\nOn the offline machine add this to your Terraform CLI config", "1"))
    print("(Windows: %APPDATA%\\terraform.rc   macOS/Linux: ~/.terraformrc):\n")
    print('provider_installation {\n  filesystem_mirror {\n    path    = "' + dest.as_posix() + '"\n    include = ["registry.terraform.io/hashicorp/*"]\n  }\n}')
    return 0


# --------------------------------------------------------------------------- lessons
def cmd_list(args: argparse.Namespace) -> int:
    phase = None
    names = {1: "Terraform and GCP Foundations", 2: "Core Infrastructure Engineering", 3: "Modern Cloud Applications and Automation", 4: "Advanced Engineering, Security, and System Design"}
    for l in paths.load_lessons():
        if l.phase != phase:
            phase = l.phase
            print(c(f"\nPhase {phase} - {names.get(phase, '')}", "1"))
        status = c("ready  ", "32") if l.status == "ready" else c("planned", "90")
        started = c(" (started)", "36") if l.workspace.exists() else ""
        print(f"  {l.id}  {status}  {l.title}{started}")
    print()
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    lesson = paths.find_lesson(args.lesson)
    if lesson.status != "ready":
        print(f"Lesson {lesson.id} is planned but not published yet. See {lesson.sub('README.md')}")
        return 1
    dest = lesson.workspace
    if dest.exists() and not args.force:
        print(f"{dest} already exists. Use --force to replace it (your files will be overwritten).")
        return 1
    if dest.exists():
        shutil.rmtree(dest)
    ignore = shutil.ignore_patterns(".terraform", "terraform.tfstate*", "course.tfstate", ".terraform.lock.hcl")

    if args.from_mine:
        prev = paths.previous_lesson(lesson)
        if not prev or not prev.workspace.exists():
            print("No previous workspace to continue from; starting from the official starter instead.")
            shutil.copytree(lesson.sub("starter"), dest, ignore=ignore)
        else:
            sub = lesson.starter_previous          # e.g. "legacy" when the lesson restructures the tree
            shutil.copytree(prev.workspace, dest / sub if sub else dest, ignore=ignore)
            prev_solution = prev.sub("solution")
            for f in lesson.sub("starter").rglob("*"):   # bring in files that are new in this lesson
                rel = f.relative_to(lesson.sub("starter"))
                if sub and rel.parts and rel.parts[0] == sub:
                    continue
                if f.is_file() and (sub or not (prev_solution / rel).exists()) and not (dest / rel).exists():
                    (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, dest / rel)
            print(c(f"Continuing from your lesson {prev.id} work.", "36"))
    else:
        shutil.copytree(lesson.sub("starter"), dest, ignore=ignore)

    rel = dest.relative_to(paths.ROOT)
    print(c(f"Lesson {lesson.id}: {lesson.title}", "1"))
    print(f"  Your files:   {rel}")
    print(f"  Read:         {lesson.sub('README.md').relative_to(paths.ROOT)} then lab.md")
    print(f"  Check work:   python course.py check {lesson.id}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    lesson = paths.find_lesson(args.lesson)
    target = Path(args.path).resolve() if args.path else lesson.workspace
    rep = runner.check(lesson, target, challenge=args.challenge)
    if args.json:
        print(json.dumps(rep.to_json(), indent=2))
    else:
        print_report(rep, verbose=args.verbose)
        if rep.passed and not args.challenge and lesson.sub("challenge.md").exists():
            print(c(f"Ready for more? Read challenge.md, then: python course.py check {lesson.id} --challenge", "36"))
            print()
    return 0 if rep.passed else 1


def cmd_solution(args: argparse.Namespace) -> int:
    lesson = paths.find_lesson(args.lesson)
    sol = lesson.sub("solution-challenge" if args.challenge else "solution")
    print(c("Reference solution (one valid answer - yours may differ and still pass):", "1"))
    print(f"  {sol.relative_to(paths.ROOT)}")
    for f in sorted(sol.rglob("*")):
        if f.is_file():
            print(f"    {f.relative_to(sol)}")
    if lesson.workspace.exists():
        print(c("\nCompare with your work:", "1"))
        print(f"  git diff --no-index {lesson.workspace.relative_to(paths.ROOT)} {sol.relative_to(paths.ROOT)}")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    return 0 if selftest.run(args.lessons or None, workers=args.workers) else 1


def cmd_check_all(args: argparse.Namespace) -> int:
    from . import guide
    lessons = [l for l in paths.load_lessons() if l.status == "ready" and l.workspace.exists()]
    if args.lessons:
        keys = {k.lstrip("0") for k in args.lessons}
        lessons = [l for l in lessons if l.id.lstrip("0") in keys]
    if not lessons:
        print("No started lessons to check. Start one with: python course.py start 01")
        return 1
    print(c(f"Checking {len(lessons)} lesson(s)" + (" with challenges" if args.challenge else ""), "1"))
    results = guide.check_many(lessons, challenge=args.challenge, broken=args.broken)
    passed = sum(r.passed for _, _, r in results)
    print()
    print(c(f"{passed} of {len(results)} checks passed.", "32;1" if passed == len(results) else "33;1"))
    if passed != len(results):
        print("Details: python course.py check <lesson>  (add --challenge for challenge results)")
    return 0 if passed == len(results) else 1


def cmd_app(args: argparse.Namespace) -> int:
    from .app import server
    return server.serve(port=getattr(args, "port", 8024), open_browser=not getattr(args, "no_browser", False),
                        lesson=getattr(args, "lesson", None))


def cmd_guide(args: argparse.Namespace) -> int:
    from . import guide
    return guide.Guide().run(getattr(args, "lesson", None))


def cmd_clean(args: argparse.Namespace) -> int:
    shutil.rmtree(paths.BUILD, ignore_errors=True)
    print("Removed build directories (provider cache kept).")
    return 0


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="course", description="Terraform for Google Cloud - offline course tools")
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("app", help="the course app in your browser: lesson, editor and checks in one window (the default)")
    a.add_argument("lesson", nargs="?", help="open this lesson")
    a.add_argument("--port", type=int, default=8024)
    a.add_argument("--no-browser", action="store_true", help="don't open a browser window")
    a.set_defaults(fn=cmd_app)

    g = sub.add_parser("guide", help="guided mode in the terminal, lesson by lesson")
    g.add_argument("lesson", nargs="?", help="jump to this lesson")
    g.set_defaults(fn=cmd_guide)

    sub.add_parser("setup", help="check tools and download pinned providers from the Terraform Registry").set_defaults(fn=cmd_setup)

    m = sub.add_parser("mirror", help="copy providers to a folder for air-gapped machines")
    m.add_argument("dir")
    m.add_argument("--platform", action="append", help=f"repeatable; default: {', '.join(PLATFORMS)}")
    m.set_defaults(fn=cmd_mirror)

    sub.add_parser("list", help="list lessons").set_defaults(fn=cmd_list)

    s = sub.add_parser("start", help="copy a lesson's starter into workspace/")
    s.add_argument("lesson")
    s.add_argument("--from-mine", action="store_true", help="continue from your own previous-lesson workspace")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_start)

    ch = sub.add_parser("check", help="validate your work for a lesson")
    ch.add_argument("lesson")
    ch.add_argument("--challenge", action="store_true", help="also run challenge requirements")
    ch.add_argument("--path", help="check a different folder instead of workspace/<lesson>")
    ch.add_argument("--json", action="store_true")
    ch.add_argument("-v", "--verbose", action="store_true")
    ch.set_defaults(fn=cmd_check)

    so = sub.add_parser("solution", help="show where the reference solution is")
    so.add_argument("lesson")
    so.add_argument("--challenge", action="store_true")
    so.set_defaults(fn=cmd_solution)

    st = sub.add_parser("selftest", help="(instructors) prove validators accept solutions and reject bad fixtures")
    st.add_argument("lessons", nargs="*")
    st.add_argument("--workers", type=int, default=4)
    st.set_defaults(fn=cmd_selftest)

    ca = sub.add_parser("check-all", help="check every started lesson in one go and print a summary")
    ca.add_argument("lessons", nargs="*", help="only these lessons (default: all started ones)")
    ca.add_argument("--challenge", action="store_true", help="also run challenge requirements")
    ca.add_argument("--broken", action="store_true", help="also run each lesson's troubleshooting repo")
    ca.set_defaults(fn=cmd_check_all)

    sub.add_parser("clean", help="delete build directories").set_defaults(fn=cmd_clean)

    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0].isdigit():          # `python course.py 05` = the app at lesson 05
        argv = ["app", *argv]
    args = p.parse_args(argv)
    if args.cmd is None:
        return cmd_app(args)
    return args.fn(args)
