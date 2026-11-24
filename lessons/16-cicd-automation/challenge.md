# Lesson 16 Challenge — A pipeline you can trust

```powershell
python course.py check 16 --challenge
```

| ID | Requirement |
|---|---|
| C16.1 | **Pin every action to a full commit SHA** (`actions/checkout@11bd719… # v4`). A tag like `@v4` can be moved to different code by whoever controls the action's repository. A SHA can't. |
| C16.2 | **Never run two applies at once, never cancel one.** Add a `concurrency` group per ref with `cancel-in-progress: false`. A cancelled apply leaves resources half-created and the state lock held. |
| C16.3 | **Lint in CI.** Run `tflint --recursive` (via `terraform-linters/setup-tflint`), or checkov, trivy or conftest, in the checks job. |
| C16.4 | **Show reviewers the plan.** Save `terraform show -no-color tfplan` to a file and publish it with `actions/upload-artifact`, or post it as a PR comment. |

## Think about it

- Dependabot can update SHA-pinned actions and keep the `# v4` comment in sync. Why is that better than pinning to tags?
- The uploaded plan may contain sensitive values. Who can read workflow artifacts in your repository, and for how long?
