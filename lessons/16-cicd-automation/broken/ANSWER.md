# Answer — Troubleshooting 16

**Symptom:** R16.7: `apply has no 'if:' restricting it to main - every pull request would apply to dev`.

**Root cause:** the apply job lost its condition

```yaml
if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

so it runs for every event the workflow triggers on, including `pull_request`, with the
PR's unreviewed code.

**Would it have succeeded?** With this course's IAM, **no**. `meridian-ci-apply` is bound only to
`principalSet://…/attribute.ref/refs/heads/main`. A pull-request run's token carries
`ref = refs/pull/123/merge`, so the token exchange is refused and the job fails at
authentication. The incident in the story could only happen with a repository-wide binding
or a key in a secret. That's exactly why the identity binding exists.

**Fix:** restore the `if:`. The controls between a PR and dev are now:

1. the job condition (`push` on `refs/heads/main`);
2. the `dev` environment (required reviewers, deployment branch rules);
3. the branch-scoped workloadIdentityUser binding, enforced by Google, not by the workflow;
4. branch protection on `main` (reviews and passing checks before merge).

**Why not rely on the workflow file:** anyone who can open a PR can edit the workflow in
that PR. Only controls that live **outside** the repository (IAM bindings, environment
protection rules, branch protection) hold against a malicious or careless change.
