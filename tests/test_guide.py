import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from coursekit import guide, paths


def ready():
    return [l for l in paths.load_lessons() if l.status == "ready"]


def lesson(lid):
    return next(l for l in ready() if l.id == lid)


def finished(*ids):
    return {"current": ids[-1] if ids else None,
            "lessons": {i: {s: "passed" for s in guide.steps_for(lesson(i))} for i in ids}}


class ProgressTest(unittest.TestCase):
    def test_steps_in_order(self):
        self.assertEqual(guide.steps_for(lesson("02")), ["lab", "challenge", "broken"])
        p = {"lessons": {"02": {"lab": "passed"}}}
        self.assertEqual(guide.next_step(lesson("02"), p), "challenge")
        p["lessons"]["02"]["challenge"] = "skipped"
        self.assertEqual(guide.next_step(lesson("02"), p), "broken")
        p["lessons"]["02"]["broken"] = "passed"
        self.assertIsNone(guide.next_step(lesson("02"), p))

    def test_fresh_start_is_lesson_01(self):
        self.assertEqual(guide.current_lesson({"current": None, "lessons": {}}, ready()).id, "01")

    def test_after_finishing_moves_forward_not_back(self):
        p = finished("02")                      # 01 never done, 02 finished: next is 03, not 01
        self.assertEqual(guide.current_lesson(p, ready()).id, "03")

    def test_resume_unfinished_current(self):
        p = {"current": "05", "lessons": {"05": {"lab": "passed"}}}
        self.assertEqual(guide.current_lesson(p, ready()).id, "05")

    def test_everything_done(self):
        self.assertIsNone(guide.current_lesson(finished(*[l.id for l in ready()]), ready()))

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.json"
            self.assertEqual(guide.load_progress(f), {"current": None, "lessons": {}})
            guide.save_progress({"current": "03", "lessons": {}}, f)
            self.assertEqual(guide.load_progress(f)["current"], "03")


class TaskTest(unittest.TestCase):
    def test_requirement_id_ranges(self):
        self.assertEqual(guide.requirement_ids("Step 3 — The bucket (R1.4 – R1.7)"), ["R1.4", "R1.5", "R1.6", "R1.7"])
        self.assertEqual(guide.requirement_ids("(R23.1, R23.8, R23.9)"), ["R23.1", "R23.8", "R23.9"])
        self.assertEqual(guide.requirement_ids("Reflection questions"), [])

    def test_lab_tasks_follow_lab_md(self):
        ts = guide.tasks(lesson("01"), "lab")
        self.assertEqual(ts[0].title, "Before you start")      # lab.md's opening notes
        self.assertEqual(ts[1].ids, ["R1.1"])
        self.assertTrue(ts[1].title.startswith("Step 1"))
        self.assertTrue(ts[-1].final)
        self.assertIn("R1.9", [i for t in ts for i in t.ids])

    def test_every_lab_requirement_belongs_to_a_task_or_the_final_check(self):
        for l in ready():
            ts = guide.tasks(l, "lab")
            self.assertTrue(ts[-1].final, l.id)
            self.assertTrue(any(t.ids for t in ts), f"lesson {l.id}: no task carries requirement IDs")

    def test_challenge_tasks_one_per_requirement(self):
        ts = guide.tasks(lesson("23"), "challenge")
        self.assertEqual([t.ids for t in ts[:4]], [["C23.1"], ["C23.2"], ["C23.3"], ["C23.4"]])
        self.assertEqual(ts[0].title, "C23.1 Essential contacts")

    def test_render_strips_markdown(self):
        out = guide.render("Use **bold** and `code`.\n\n```hcl\nx = 1\n```\n[lab](lab.md)")
        self.assertNotIn("**", out)
        self.assertNotIn("```", out)
        self.assertIn("x = 1", out)


class TextTest(unittest.TestCase):
    def test_intro_has_story_and_objectives(self):
        story, objectives = guide.intro_text(lesson("24"))
        self.assertIn("board", story)
        self.assertTrue(objectives.startswith("- "))

    def test_broken_story_drops_commands(self):
        text = guide.broken_story(lesson("24"))
        self.assertNotIn("Copy-Item", text)
        self.assertNotIn("Answer:", text)
        self.assertIn("FinOps", text)

    def test_quit_saves_and_exits(self):
        with tempfile.TemporaryDirectory() as d:
            old = guide.PROGRESS
            guide.PROGRESS = Path(d) / "p.json"
            try:
                g = guide.Guide(inp=lambda prompt="": (_ for _ in ()).throw(EOFError), progress={"current": "01", "lessons": {"01": {"lab": "passed", "challenge": "passed", "broken": "passed"}}})
                with redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(g.run("01"), 0)    # finished lesson: "do it again?" -> EOF -> stop
                self.assertIn("Progress saved", out.getvalue())
            finally:
                guide.PROGRESS = old


if __name__ == "__main__":
    unittest.main()
