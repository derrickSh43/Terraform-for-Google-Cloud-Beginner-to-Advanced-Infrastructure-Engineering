import unittest

from coursekit import runner

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

    def test_offline(self):
        self.assertIn("internet connection", runner._init_hint(OFFLINE))


if __name__ == "__main__":
    unittest.main()
