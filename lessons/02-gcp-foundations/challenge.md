# Lesson 02 Challenge — Cost controls and your first test

Finance wants an early warning before the cloud bill surprises anyone.

```powershell
python course.py check 02 --challenge
```

| ID | Requirement |
|---|---|
| C2.1 | Add a `google_billing_budget` with a monthly amount from a variable (default 25 USD) and alerts at **50%, 90% and 100%**. |
| C2.2 | Scope the budget to this project only (`budget_filter.projects = ["projects/<project_number>"]`). Take the billing account and project number from variables `billing_account` and `project_number`, and set their values in `terraform.tfvars`. Use fake values, e.g. `01A2B3-C4D5E6-F7A8B9` and `418273645512`. |
| C2.3 | Enable `billingbudgets.googleapis.com`, and make the budget depend on the APIs. |
| C2.4 | Add a `validation` block to `billing_account` that rejects anything not shaped like `XXXXXX-XXXXXX-XXXXXX` (uppercase hex). |

> **Offline tip:** don't look the billing account up with `data "google_billing_account"`.
> Data sources call the GCP API during plan, which fails offline (and with real credentials
> it needs billing permissions most engineers don't have). Pass the ID in as a variable,
> which is also how real platform teams do it.

## Native tests

C2.4 is proven by a **Terraform test** that ships with the lesson,
`tests/challenge/billing_account.tftest.hcl`. The checker copies it next to your
code and runs `terraform test`. Read it:

```hcl
mock_provider "google" {}          # no credentials, no API calls

run "malformed_billing_account_is_rejected" {
  command = plan
  variables { billing_account = "my-billing-account" }
  expect_failures = [var.billing_account]
}
```

`expect_failures` *passes* when your validation correctly rejects the bad value.
If your rule is missing, the `tests` stage fails. Lesson 16 has you write your
own tests.
