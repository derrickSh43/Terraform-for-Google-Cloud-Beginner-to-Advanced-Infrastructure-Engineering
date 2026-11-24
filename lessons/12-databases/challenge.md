# Lesson 12 Challenge — Production-grade PostgreSQL

```powershell
python course.py check 12 --challenge
```

| ID | Requirement |
|---|---|
| C12.1 | **See slow queries.** Add the database flag `log_min_duration_statement = "500"` (milliseconds) and enable Query Insights (`insights_config { query_insights_enabled = true }`). |
| C12.2 | **Passwordless app login.** Turn on `cloudsql.iam_authentication` and add a `google_sql_user` of type `CLOUD_IAM_SERVICE_ACCOUNT` for the app's service account, via a module variable `iam_service_accounts`. The name is the email without `.gserviceaccount.com` (`trimsuffix`). |
| C12.3 | **Data residency.** The secret's payload must be stored only in `us-central1` and `us-east1`: replace `replication { auto {} }` with `user_managed` replicas. |
| C12.4 | **No HA on shared-core.** In the postgres module, reject `availability_type = "REGIONAL"` with a shared-core tier (a validation that references `var.tier`), and accept only ZONAL/REGIONAL. `tests/challenge/postgres_module.tftest.hcl` must pass. It mocks **both** the google and random providers. |

## Think about it

- With IAM authentication (C12.2), what happens to the password user? Could you delete it, and what would break first?
- `user_managed` replication is **ForceNew** on a secret. What would happen to the deployed secret and its version, and why is it safe here?
