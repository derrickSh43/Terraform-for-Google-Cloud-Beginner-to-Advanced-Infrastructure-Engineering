import base64
import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from coursekit import paths
from coursekit.app import markdown, server, vendor


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
