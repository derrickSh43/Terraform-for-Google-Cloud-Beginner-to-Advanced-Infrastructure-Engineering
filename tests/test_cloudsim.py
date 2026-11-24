import json
import tempfile
import unittest
from pathlib import Path

from coursekit import cloudsim

INVENTORY = [
    {"type": "google_storage_bucket", "id": "b-archive", "aliases": ["p/b-archive"], "schema_version": 3,
     "attributes": {"id": "b-archive", "name": "b-archive"}},
    {"type": "google_storage_bucket", "id": "b-export-q1", "aliases": [], "schema_version": 3,
     "attributes": {"id": "b-export-q1", "name": "b-export-q1"}},
]


class CloudsimTest(unittest.TestCase):
    def root(self, text, state=None):
        d = Path(tempfile.mkdtemp())
        (d / "imports.tf").write_text(text, encoding="utf-8")
        if state is not None:
            (d / "course.tfstate").write_text(json.dumps(state), encoding="utf-8")
        return d

    def state(self, d):
        return json.loads((d / "course.tfstate").read_text(encoding="utf-8"))

    def test_literal_import_into_module(self):
        d = self.root('import {\n  to = module.r.google_storage_bucket.archive\n  id = "b-archive"\n}\n')
        done = cloudsim.apply(d, INVENTORY)
        self.assertEqual([i.address for i in done], ["module.r.google_storage_bucket.archive"])
        res = self.state(d)["resources"][0]
        self.assertEqual((res["module"], res["type"], res["name"]), ("module.r", "google_storage_bucket", "archive"))
        self.assertEqual(res["instances"][0]["schema_version"], 3)

    def test_alias_id(self):
        d = self.root('import {\n  to = google_storage_bucket.a\n  id = "p/b-archive"\n}\n')
        self.assertEqual(len(cloudsim.apply(d, INVENTORY)), 1)

    def test_for_each_with_local(self):
        d = self.root('locals {\n  qs = ["q1"]\n}\n\nimport {\n  for_each = toset(local.qs)\n'
                      '  to       = google_storage_bucket.e[each.key]\n  id       = "b-export-${each.key}"\n}\n')
        done = cloudsim.apply(d, INVENTORY)
        self.assertEqual([i.address for i in done], ['google_storage_bucket.e["q1"]'])
        self.assertEqual(self.state(d)["resources"][0]["instances"][0]["index_key"], "q1")

    def test_unknown_id_fails(self):
        d = self.root('import {\n  to = google_storage_bucket.a\n  id = "nope"\n}\n')
        with self.assertRaises(cloudsim.ImportFailed):
            cloudsim.apply(d, INVENTORY)

    def test_type_mismatch_fails(self):
        d = self.root('import {\n  to = google_service_account.a\n  id = "b-archive"\n}\n')
        with self.assertRaises(cloudsim.ImportFailed):
            cloudsim.apply(d, INVENTORY)

    def test_address_already_in_state_is_skipped(self):
        state = {"version": 4, "serial": 3, "resources": [{"mode": "managed", "type": "google_storage_bucket", "name": "a",
                                                           "instances": [{"attributes": {"id": "x"}}]}]}
        d = self.root('import {\n  to = google_storage_bucket.a\n  id = "nope"\n}\n', state)
        self.assertEqual(cloudsim.apply(d, INVENTORY), [])

    def test_commented_import_ignored(self):
        d = self.root('# import {\n#   to = google_storage_bucket.a\n#   id = "nope"\n# }\n')
        self.assertEqual(cloudsim.apply(d, INVENTORY), [])

    def test_variable_for_each_is_explained(self):
        d = self.root('import {\n  for_each = toset(var.qs)\n  to = google_storage_bucket.e[each.key]\n  id = each.value\n}\n')
        with self.assertRaisesRegex(cloudsim.ImportFailed, "literal"):
            cloudsim.apply(d, INVENTORY)


if __name__ == "__main__":
    unittest.main()
