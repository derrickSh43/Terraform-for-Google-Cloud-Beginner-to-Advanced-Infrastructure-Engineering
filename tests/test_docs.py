import unittest

from coursekit import baseline, docs

ADR = """# 0001. Use a dual-region bucket for backups

Status: Accepted
Date: 2026-11-23

## Context

Backups must survive the loss of us-central1. Our recovery point objective for backups is fifteen
minutes and the restore must work without anyone copying files by hand during an outage.

## Decision

Store backups in the NAM4 dual-region with turbo replication enabled.

## Alternatives considered

| Option | Why not |
|---|---|
| Regional bucket + nightly copy | RPO of a day |

```hcl
location = "NAM4"
```

## Consequences

Storage costs roughly double.
"""

FAILURE = """# Failure analysis

## Zone loss

| Workload | Zones | Minimum capacity | After losing a zone |
|---|---|---|---|
| `module.web` | 3 | 6 | **4** |
| module.db (primary) | regional | 1 | 1 |
"""


class MarkdownTest(unittest.TestCase):
    def test_headings_and_title(self):
        self.assertEqual(docs.title(ADR), "0001. Use a dual-region bucket for backups")
        self.assertIn((2, "Decision"), docs.headings(ADR))

    def test_heading_inside_fence_is_ignored(self):
        text = "# T\n\n```\n# not a heading\n```\n"
        self.assertEqual(docs.headings(text), [(1, "T")])

    def test_sections_and_words(self):
        dec = docs.find_section(ADR, "decision")
        self.assertEqual(dec.title, "Decision")
        self.assertEqual(dec.words, 10)
        alt = docs.find_section(ADR, "considered options", "alternatives")
        self.assertIsNotNone(alt)
        self.assertNotIn("NAM4", alt.body.split("```")[0])   # code doesn't leak in before the fence

    def test_words_skip_code(self):
        self.assertEqual(docs.words("one two\n```\nthree four five\n```\n"), 2)

    def test_field(self):
        self.assertEqual(docs.field(ADR, "Status"), "Accepted")
        self.assertEqual(docs.field("- **Status:** Proposed", "status"), "Proposed")
        self.assertIsNone(docs.field(ADR, "Owner"))

    def test_tables(self):
        rows, cols = docs.find_table(FAILURE, "workload", "min", "after")
        self.assertEqual(cols, ["workload", "minimum capacity", "after losing a zone"])
        self.assertEqual(rows[0]["workload"], "module.web")
        self.assertEqual(docs.number(rows[0]["after losing a zone"]), 4)
        self.assertIsNone(docs.find_table(FAILURE, "rpo"))

    def test_cells_keep_underscores(self):
        self.assertEqual(docs.clean_cell(" `module.batch_cluster.google_container_cluster.this` "),
                         "module.batch_cluster.google_container_cluster.this")
        self.assertEqual(docs.clean_cell("*yes*"), "yes")

    def test_fenced(self):
        self.assertEqual(docs.fenced(ADR, "hcl"), ['location = "NAM4"'])
        self.assertEqual(docs.fenced(ADR, "mermaid"), [])


class RubricTest(unittest.TestCase):
    SPEC = {"status_values": ["Proposed", "Accepted", "Superseded"],
            "sections": [{"name": "Context", "min_words": 20}, {"name": "Decision", "min_words": 5},
                         {"name": "Alternatives considered", "aliases": ["Options"], "min_words": 3},
                         {"name": "Consequences", "min_words": 3}]}

    def test_good_record(self):
        self.assertEqual(docs.check_record(ADR, self.SPEC), [])

    def test_thin_and_missing(self):
        bad = ADR.replace("Status: Accepted", "Status: Maybe").replace("## Consequences", "## Notes")
        problems = docs.check_record(bad, dict(self.SPEC, sections=self.SPEC["sections"] + [{"name": "Decision", "min_words": 50}]))
        self.assertTrue(any("Maybe" in p for p in problems))
        self.assertTrue(any("Consequences" in p for p in problems))
        self.assertTrue(any("needs at least 50" in p for p in problems))

    def test_topics(self):
        cov = docs.topics_covered([ADR], [{"name": "dr", "any": ["rpo", "recovery point"]}, {"name": "net", "any": ["vpn"]}])
        self.assertEqual(cov, {"dr": True, "net": False})


class BaselineTest(unittest.TestCase):
    def test_maps_ids_to_lessons(self):
        self.assertEqual(baseline.requirement_for("R10.1").id, "R10.1")
        self.assertEqual(baseline.requirement_for("R1.2").id, "R1.2")
        with self.assertRaises(KeyError):
            baseline.requirement_for("R10.99")
        with self.assertRaises(KeyError):
            baseline.requirement_for("nope")


if __name__ == "__main__":
    unittest.main()
