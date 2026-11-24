# Lesson 24 Challenge — Ready for the reviewer

```powershell
python course.py check 24 --challenge
```

| ID | Requirement |
|---|---|
| C24.1 | **Self-assessment.** `docs/self-assessment.md` with a table `\| Criterion \| Score (1-4) \| Evidence \|`, one row per criterion in [rubric.json](rubric.json) (Design, Build, Secure, Automate, Monitor, Scale, Document, Test). Evidence cites files that exist in your repository. A claim without evidence scores nothing in a real review either. |
| C24.2 | **Region loss.** Add a table to `docs/failure-analysis.md`: `\| Data store \| RPO target (minutes) \| RPO if us-central1 is lost (minutes) \| Meets target \|` with rows `database`, `backups` and `images`. Targets come from `recovery_objectives`. The RPOs are what the configuration can actually deliver (lesson 22's rules). |
| C24.3 | **Drift detection.** A `schedule` trigger (cron) and a job that only runs on it, running `terraform plan -detailed-exitcode` for dev, prod, hub and platform with the read-only plan identity. Exit code 2 means drift, and the job fails. |
| C24.4 | **Apply what was reviewed.** A `plan-prod` job (on main, after dev and shared) runs `plan -out=tfplan` and uploads it with `actions/upload-artifact`. `apply-prod` needs it, downloads it with `actions/download-artifact` and runs `terraform -chdir=envs/prod apply tfplan`: no new plan, no `-auto-approve`. |

## Think about it

- Your self-assessment gives "Monitor" a 3. What evidence would make it a 4?
- The assets bucket is regional and isn't in the region-loss table. Is that a gap in the analysis,
  or a decision? If it's a decision, where should it be written down?
- Drift detection found a firewall rule someone added in the console during an incident. Do you
  delete it (re-apply), or import it? Who decides?
- A saved plan goes stale if prod changes between plan and apply. What does Terraform do when you
  apply a stale plan file?
