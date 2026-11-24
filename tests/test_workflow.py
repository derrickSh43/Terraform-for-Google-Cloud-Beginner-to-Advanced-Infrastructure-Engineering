"""Unit tests for the workflow YAML-subset reader."""

import unittest

from coursekit import workflow

SAMPLE = """\
name: terraform   # comment

on:
  pull_request:
    paths: ["envs/**", "modules/**"]
  push:
    branches:
      - main

permissions:
  contents: read

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Format
        run: terraform fmt -check -recursive
      - name: Validate
        run: |
          for env in envs/dev envs/prod; do
            terraform -chdir=$env init -backend=false
            terraform -chdir=$env validate
          done
  plan:
    needs: checks
    if: github.event_name == 'pull_request'
    permissions:
      contents: read
      id-token: write
    steps:
    - uses: google-github-actions/auth@v2
      with:
        workload_identity_provider: ${{ vars.WIF_PROVIDER }}
        service_account: "meridian-ci-plan@p.iam.gserviceaccount.com"
    - run: >-
        terraform plan
        -lock=false
"""


class Parse(unittest.TestCase):
    def setUp(self):
        self.wf = workflow.load("t.yml", SAMPLE)

    def test_triggers(self):
        self.assertIn("pull_request", self.wf.triggers)
        self.assertEqual(self.wf.triggers["push"]["branches"], ["main"])
        self.assertEqual(self.wf.triggers["pull_request"]["paths"], ["envs/**", "modules/**"])

    def test_jobs_and_steps(self):
        self.assertEqual([j.id for j in self.wf.jobs], ["checks", "plan"])
        checks = self.wf.job("checks")
        self.assertEqual(checks.steps[0].uses, "actions/checkout@v4")
        self.assertIn("terraform fmt -check", checks.runs())
        self.assertIn("validate\ndone", checks.runs())

    def test_unindented_sequence_and_folded_scalar(self):
        plan = self.wf.job("plan")
        self.assertEqual(plan.needs, ["checks"])
        self.assertEqual(plan.permissions["id-token"], "write")
        auth = plan.uses_action("google-github-actions/auth")[0]
        self.assertEqual(auth.with_["service_account"], "meridian-ci-plan@p.iam.gserviceaccount.com")
        self.assertEqual(plan.steps[1].run, "terraform plan -lock=false")
        self.assertIn("pull_request", plan.condition)

    def test_comments_and_flow(self):
        self.assertEqual(self.wf.data["name"], "terraform")
        self.assertEqual(workflow.scalar("{}"), {})
        self.assertEqual(workflow.scalar("[a, 'b, c']"), ["a", "b, c"])


if __name__ == "__main__":
    unittest.main()
