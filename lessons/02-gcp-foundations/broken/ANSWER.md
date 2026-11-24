# Answer — Troubleshooting 02

**Symptom:** `validate` fails with `Error: Cycle: google_service_account.web, google_project_iam_member.web`.

**Root cause:** the IAM member's `member` argument references
`google_service_account.web.email`, an implicit edge from the member to the
account. The teammate added `depends_on = [google_project_iam_member.web]` to
the account, an explicit edge back the other way. Each now waits for the other.

**Fix:** remove `google_project_iam_member.web` from the service account's
`depends_on`. The account must exist before roles can be granted *to* it. To
make a *VM* wait for its roles, put the `depends_on` on the VM (lesson 3), not
on the account.

**Lesson:** `depends_on` is a last resort for hidden dependencies Terraform can't
see. Every reference is already an edge, so check the existing references before
adding one.
