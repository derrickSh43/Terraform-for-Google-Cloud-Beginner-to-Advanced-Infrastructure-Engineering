# Lesson 12 Lab — A private PostgreSQL for the app tier

```powershell
python course.py start 12
python course.py check 12
```

The starter is the lesson 11 solution plus two empty modules,
`modules/private-services` and `modules/postgres`, and `state/dev.tfstate`
(dev after lesson 11). R12.9 is a guard rail: additions only.

---

## Part A — APIs and Private Service Access (R12.1, R12.2)

1. Add `servicenetworking.googleapis.com`, `sqladmin.googleapis.com` and
   `secretmanager.googleapis.com` to the foundation module's `apis` default.
2. In `modules/private-services`:
   - `google_compute_global_address`: `purpose = "VPC_PEERING"`, `address_type = "INTERNAL"`,
     `address = var.range_address`, `prefix_length = 20`, `network = var.network_id`
   - `google_service_networking_connection`: `network = var.network_id`,
     `service = "servicenetworking.googleapis.com"`, `reserved_peering_ranges = [<the address>.name]`
   - output `network_id = google_service_networking_connection.this.network`. Passing the network
     *through the connection* makes anything that uses it wait for the peering.
3. Call it from both environments: `range_address = var.psa_range_address`
   (dev `10.10.16.0`, prod `10.20.16.0`).

## Part B — The instance (R12.3 – R12.5)

In `modules/postgres`, a `google_sql_database_instance`:

- `database_version = "POSTGRES_16"`, `region`, `deletion_protection = true`
- `settings`:
  - `tier = var.tier`, `availability_type = var.availability_type`, `deletion_protection_enabled = true`, `user_labels`
  - `ip_configuration { ipv4_enabled = false  private_network = var.network_id  ssl_mode = "ENCRYPTED_ONLY" }`
  - `backup_configuration { enabled = true  start_time = "02:00"  point_in_time_recovery_enabled = true
    transaction_log_retention_days = 7  backup_retention_settings { retained_backups = var.retained_backups } }`
  - a `maintenance_window` (Sunday 04:00)

Plus a `google_sql_database` named `meridian`.

Call it from both environments as `module "db"`, with `network_id = module.private_services.network_id` and
the sizes from new variables `db_tier`, `db_availability_type` and `db_retained_backups`:

| | tier | availability | backups |
|---|---|---|---|
| dev | `db-g1-small` | `ZONAL` | 7 |
| prod | `db-custom-2-7680` | `REGIONAL` | 14 |

## Part C — Credentials (R12.6, R12.7)

1. `random_password` (32 characters; `override_special = "-_.~"` keeps it URL-safe).
2. `google_sql_user` `meridian_app` with `password = random_password.app.result`.
3. `google_secret_manager_secret` (`secret_id = "${var.name_prefix}-db-password"`, `replication { auto {} }`)
   and a `google_secret_manager_secret_version` with the same password.
4. `google_secret_manager_secret_iam_member` for each of `var.secret_readers`, with
   `roles/secretmanager.secretAccessor`, **on the secret**.
5. Outputs: `connection_name`, `private_ip`, `password_secret_id`. **Not the password.**

In both environments, add to `module "db"`:
`secret_readers = ["serviceAccount:${module.app.service_account_email}"]`.

## Part D — Let the app connect (R12.8, R12.10)

- The app's service account needs `roles/cloudsql.client`. Pass a `roles` list to
  `module "app"` with the two workload roles plus `roles/cloudsql.client`.
- R12.10 compares the database sizes you set in Part B: prod is highly available, dev stays small.

## Review

The dev plan should be **13 to add, 0 to change, 0 to destroy**. Run with `-v`
and find `random_password`. What does the plan show for its value, and why?

## Reflection questions

1. The app VM has no external IP and the database has no public IP. Trace the packet path from the app to PostgreSQL.
2. The password is in Terraform state. List everyone who can read the state bucket. Is that acceptable? What would you change?
3. You delete `module "db"` from the code by accident and run `apply`. What stops disaster, and in which order?
4. Why output `password_secret_id` instead of the password, even as a sensitive output?
