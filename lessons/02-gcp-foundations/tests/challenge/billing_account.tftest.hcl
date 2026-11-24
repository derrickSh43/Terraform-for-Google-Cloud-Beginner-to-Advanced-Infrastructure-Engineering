# Native Terraform test, run by `course check 02 --challenge`.
# mock_provider means no credentials and no API calls - Terraform fakes the provider.
mock_provider "google" {}

run "valid_billing_account_is_accepted" {
  command = plan

  variables {
    billing_account = "01A2B3-C4D5E6-F7A8B9"
  }
}

run "malformed_billing_account_is_rejected" {
  command = plan

  variables {
    billing_account = "my-billing-account"
  }

  expect_failures = [var.billing_account]
}
