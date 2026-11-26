import base64
import hashlib
import io
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from coursekit import paths
from coursekit.app import markdown, server, update, vendor


class MarkdownTest(unittest.TestCase):
    def test_blocks(self):
        h = markdown.render("# Title\n\nSome **bold** and `code`.\n\n```hcl\nx = \"<y>\"\n```\n\n> quote\n")
        self.assertIn("<h1>Title</h1>", h)
        self.assertIn("<strong>bold</strong>", h)
        self.assertIn("<code>code</code>", h)
        self.assertIn('<code class="lang-hcl">x = &quot;&lt;y&gt;&quot;</code>', h)
        self.assertIn("<blockquote><p>quote</p></blockquote>", h)

    def test_nested_list(self):
        h = markdown.render("- a\n  - b\n- c\n")
        self.assertEqual(h, "<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>")

    def test_table_and_escaping(self):
        h = markdown.render("| A | B |\n|---|---|\n| `x \\| y` | <script> |\n")
        self.assertIn("<th>A</th>", h)
        self.assertIn("&lt;script&gt;", h)
        self.assertNotIn("<script>", h)

    def test_every_lesson_renders(self):
        for l in paths.load_lessons():
            for name in ("README.md", "lab.md", "challenge.md"):
                if l.sub(name).exists():
                    self.assertTrue(markdown.render(l.sub(name).read_text(encoding="utf-8")).strip(), f"{l.id} {name}")


@unittest.skipUnless(shutil.which("git"), "needs git")
class UpdateTest(unittest.TestCase):
    """Against a local 'GitHub' repository: no network."""

    def git(self, cwd, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false", *args],
                       cwd=cwd, check=True, capture_output=True)

    def publish(self, text, message):
        (self.origin / "lab.md").write_text(text)
        self.git(self.origin, "add", "-A")
        self.git(self.origin, "commit", "-m", message)

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        top = Path(tmp.name).resolve()
        self.origin, self.clone = top / "origin", top / "clone"
        self.origin.mkdir()
        self.git(self.origin, "init", "-b", "main")
        (self.origin / ".gitignore").write_text("workspace/\n")
        self.publish("one\n", "first")
        self.git(top, "clone", str(self.origin), str(self.clone))
        (self.clone / "workspace").mkdir()
        (self.clone / "workspace" / "main.tf").write_text("my work")
        p = mock.patch.object(paths, "ROOT", self.clone)
        p.start()
        self.addCleanup(p.stop)

    def test_update_keeps_workspace(self):
        self.assertEqual(update.status()["count"], 0)
        self.publish("two\n", "Fix lesson 03")
        st = update.status()
        self.assertEqual((st["supported"], st["count"], st["changes"]), (True, 1, ["Fix lesson 03"]))
        update.apply()
        self.assertEqual((self.clone / "lab.md").read_text(), "two\n")
        self.assertEqual((self.clone / "workspace" / "main.tf").read_text(), "my work")
        self.assertEqual(update.status()["count"], 0)

    def test_never_overwrites_local_changes(self):
        (self.clone / "lab.md").write_text("mine\n")
        self.publish("two\n", "Fix")
        update.status()
        with self.assertRaisesRegex(update.UpdateError, "you changed course files.*lab.md"):
            update.apply()
        self.assertEqual((self.clone / "lab.md").read_text(), "mine\n")

    def test_local_commits_are_not_merged(self):
        (self.clone / "other.md").write_text("mine\n")
        self.git(self.clone, "add", "-A")
        self.git(self.clone, "commit", "-m", "mine")
        self.publish("two\n", "Fix")
        update.status()
        with self.assertRaisesRegex(update.UpdateError, "commits of its own"):
            update.apply()

    def test_hidden_when_not_a_tracking_clone(self):
        self.git(self.clone, "switch", "-c", "local-branch")
        self.assertFalse(update.status()["supported"])
        (self.clone / "sub").mkdir()
        with mock.patch.object(paths, "ROOT", self.clone / "sub"):      # the course copied into another repository
            self.assertFalse(update.status()["supported"])

    def test_offline_is_reported_not_raised(self):
        self.git(self.clone, "remote", "set-url", "origin", str(self.origin) + "-gone")
        st = update.status()
        self.assertIn("internet", st["error"])
        self.assertEqual(st["count"], 0)

    def test_not_during_a_check(self):
        with server._check_lock, self.assertRaises(server.ApiError):
            server.run_update()


class StartOverTest(unittest.TestCase):
    def setUp(self):
        paths.STATE_DIR.mkdir(exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=paths.STATE_DIR)       # inside the repo, like the real workspace/
        self.addCleanup(tmp.cleanup)
        ws = Path(tmp.name) / "workspace"
        ws.mkdir()
        for p in (mock.patch.object(paths, "WORKSPACE", ws), mock.patch.object(server, "BACKUPS", ws / ".backups"),
                  mock.patch.object(server.guide, "PROGRESS", ws / ".progress.json")):
            p.start()
            self.addCleanup(p.stop)
        self.ws = ws

    def test_backs_up_resets_and_clears_progress(self):
        l = server._lesson("03")
        with mock.patch.object(type(l), "workspace", property(lambda s: self.ws / s.dirname)):
            server.start(l, False)
            (l.workspace / "compute.tf").write_text("my work")
            server.set_progress(l, {"lab": "passed", "lab_task": 3})
            server.set_progress(server._lesson("02"), {"lab": "passed"})
            r = server.start_over(l)
            self.assertTrue(r["ok"])
            backup = self.ws / ".backups" / Path(r["backup"]).name / l.dirname
            self.assertEqual((backup / "compute.tf").read_text(), "my work")
            self.assertNotEqual((l.workspace / "compute.tf").read_text(), "my work")
            lessons = server.guide.load_progress()["lessons"]
            self.assertNotIn("03", lessons)
            self.assertEqual(lessons["02"], {"lab": "passed"})

    def test_waits_for_a_running_check(self):
        with server._check_lock, self.assertRaises(server.ApiError):
            server.start_over(server._lesson("03"))
        with server._check_lock, self.assertRaises(server.ApiError):
            server.clean_builds()


class ServerHelpersTest(unittest.TestCase):
    def test_safe_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "ws"
            root.mkdir()
            self.assertEqual(server._safe(root, "main.tf"), (root / "main.tf").resolve())
            for bad in ("../x.tf", "../../etc/passwd", "a/../../x.tf"):
                with self.assertRaises(server.ApiError):
                    server._safe(root, bad)

    def test_file_listing_skips_state_and_terraform(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for f in ("main.tf", "modules/web/main.tf", "state/dev.tfstate", ".terraform/x.tf", "notes.bin", "docs/adr/0001-x.md"):
                (root / f).parent.mkdir(parents=True, exist_ok=True)
                (root / f).write_text("x")
            self.assertEqual(server._files(root), ["main.tf", "docs/adr/0001-x.md", "modules/web/main.tf"])

    def test_lesson_and_course_json(self):
        data = server.lesson_json(server._lesson("24"))
        self.assertEqual(data["steps"], ["lab", "challenge", "broken"])
        self.assertTrue(data["tasks"]["lab"][-1]["final"])
        self.assertIn("<h1>", data["readme"])
        self.assertEqual(len(server.course_json()["lessons"]), 24)
        with self.assertRaises(server.ApiError):
            server._lesson("99")


class VendorTest(unittest.TestCase):
    def _tgz(self, files):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return buf.getvalue()

    def test_extracts_only_min_and_refuses_traversal(self):
        tgz = self._tgz({"package/min/vs/loader.js": b"ok", "package/esm/big.js": b"no",
                         "package/min/../../evil.js": b"no", "package/README.md": b"no"})
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "monaco"
            self.assertEqual(vendor.extract_min(tgz, dest), 1)
            self.assertEqual((dest / "min/vs/loader.js").read_bytes(), b"ok")
            self.assertFalse((Path(d) / "evil.js").exists())

    def test_integrity(self):
        data = b"monaco"
        good = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
        self.assertTrue(vendor._verify(data, good))
        self.assertFalse(vendor._verify(b"tampered", good))
        self.assertFalse(vendor._verify(data, "sha1-abc"))


if __name__ == "__main__":
    unittest.main()
