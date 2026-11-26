import tempfile
import unittest
from pathlib import Path

from coursekit import checks, runner

TYPO = """Error: Failed to query available provider packages

Could not retrieve the list of available versions for provider
hasicorp/google: provider registry registry.terraform.io does not have a
provider named registry.terraform.io/hasicorp/google
"""

OFFLINE = """Error: Failed to query available provider packages

Could not retrieve the list of available versions for provider hashicorp/google:
could not connect to registry.terraform.io: dial tcp: lookup registry.terraform.io: no such host
"""


DATA_SOURCE = """Error: Error when reading or editing Billing Account Not Found : 000000: googleapi: Error 401: Request had invalid authentication credentials.

  with data.google_billing_account.account,
  on main.tf line 25, in data "google_billing_account" "account":
"""


class PlanHintTest(unittest.TestCase):
    def test_names_the_data_source(self):
        hint = runner._plan_hint(DATA_SOURCE)
        self.assertIn("`data.google_billing_account.account` (main.tf line 25)", hint)

    def test_hint_comes_first(self):
        out = runner._with_hint("long plan output", "the hint")
        self.assertTrue(out.startswith("the hint"))
        self.assertEqual(runner._with_hint(" x ", ""), "x")


class InitHintTest(unittest.TestCase):
    def test_misspelled_source(self):
        hint = runner._init_hint(TYPO)
        self.assertIn('"hasicorp/google"', hint)
        self.assertIn('"hashicorp/google"', hint)
        self.assertNotIn("internet", hint)

    def test_misspelled_source_with_allow_list(self):
        out = ("Could not retrieve the list of available versions for provider\nhasicorp/google: provider "
               "registry.terraform.io/hasicorp/google was not found\nin any of the search locations")
        self.assertIn('Did you mean "hashicorp/google"?', runner._init_hint(out))

    def test_offline(self):
        self.assertIn("internet connection", runner._init_hint(OFFLINE))


UNDECLARED = """tests\\machine_type.tftest.hcl... in progress
  run "small_machine_types_are_allowed"... fail
  run "large_machine_types_are_rejected"... skip
tests\\machine_type.tftest.hcl... tearing down
tests\\machine_type.tftest.hcl... fail

Failure! 0 passed, 1 failed, 1 skipped.


Error: Reference to undeclared resource

  on tests\\machine_type.tftest.hcl line 11, in run "small_machine_types_are_allowed":
  11:     condition     = google_compute_instance.web.machine_type == "e2-small"

A managed resource "google_compute_instance" "web" has not been declared in
the root module.
"""

REQUIRED = """Error: No value for required variable

The module under test for run block "a" has a required variable "must" with
no set value. Use a -var or -var-file command line argument or add this
variable into a "variables" block within the test file or run block.
"""

NOT_DECLARED = """Warning: Value for undeclared variable

The module under test does not declare a variable named "zz", but it is
declared in run block "a".
"""

ACCEPTED = """Error: Missing expected failure

The checkable object, var.zz, was expected to report an error but
did not.
"""


class LessonTestTest(unittest.TestCase):
    def test_names_the_resource_the_test_wants(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "compute.tf").write_text('resource "google_compute_instance" "default" {\n}\n')
            hint = runner._test_hint(UNDECLARED, [Path(d)])
        self.assertIn("`google_compute_instance.web`", hint)
        self.assertIn('Yours: "default".', hint)
        self.assertIn('resource "google_compute_instance" "web"', hint)

    def test_variable_hints(self):
        self.assertIn('"must", and it has no default', runner._test_hint(REQUIRED))
        self.assertNotIn("named differently", runner._test_hint(REQUIRED))
        self.assertIn('"zz", which your code doesn\'t declare', runner._test_hint(NOT_DECLARED + REQUIRED))
        self.assertIn('variable named "zz"', runner._test_hint(NOT_DECLARED + ACCEPTED))
        self.assertIn("var.zz and your code accepted it", runner._test_hint(ACCEPTED))
        self.assertEqual(runner._test_hint("Error: something else"), "")

    def test_results_per_file(self):
        self.assertEqual(runner._test_results(UNDECLARED), {"machine_type.tftest.hcl": False})
        self.assertEqual(runner._test_results("tests/lesson_zones.tftest.hcl... pass\n\nSuccess! 1 passed, 0 failed.\n"),
                         {"zones.tftest.hcl": True})

    def test_requirement_needs_its_lesson_test(self):
        def outcome(test):
            return checks.Outcome(checks.Requirement("C1.1", "t", "", "challenge", lambda plan: None, test), True)

        ok, red, absent, plain = outcome("a.tftest.hcl"), outcome("b.tftest.hcl"), outcome("c.tftest.hcl"), outcome("")
        runner._apply_tests([ok, red, absent, plain], {"a.tftest.hcl": True, "b.tftest.hcl": False})
        self.assertEqual([o.passed for o in (ok, red, absent, plain)], [True, False, False, True])
        self.assertIn("fails", red.message)
        self.assertIn("did not run", absent.message)


if __name__ == "__main__":
    unittest.main()
