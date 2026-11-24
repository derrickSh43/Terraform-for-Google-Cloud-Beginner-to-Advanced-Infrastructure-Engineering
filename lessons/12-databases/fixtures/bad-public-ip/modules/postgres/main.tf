# A private PostgreSQL instance with generated credentials kept in Secret Manager.

resource "random_password" "app" {
  length           = 32
  special          = true
  override_special = "-_.~" # safe in connection strings
}

resource "google_sql_database_instance" "this" {
  name             = "${var.name_prefix}-pg"
  region           = var.region
  database_version = "POSTGRES_16"

  # Terraform refuses to delete it; the API-level flag stops console deletes too.
  deletion_protection = true

  settings {
    tier                        = var.tier
    edition                     = "ENTERPRISE"
    availability_type           = var.availability_type
    disk_type                   = "PD_SSD"
    disk_size                   = 10
    disk_autoresize             = true
    deletion_protection_enabled = true
    user_labels                 = var.labels

    ip_configuration {
      ipv4_enabled    = true # TEMP: so I can connect from home
      private_network = var.network_id
      ssl_mode        = "ENCRYPTED_ONLY"

      authorized_networks {
        name  = "anywhere"
        value = "0.0.0.0/0"
      }
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00" # UTC
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = var.retained_backups
      }
    }

    maintenance_window {
      day  = 7 # Sunday
      hour = 4
    }
  }
}

resource "google_sql_database" "app" {
  name     = "meridian"
  instance = google_sql_database_instance.this.name
}

resource "google_sql_user" "app" {
  name     = "meridian_app"
  instance = google_sql_database_instance.this.name
  password = random_password.app.result
}

# The password lives in Secret Manager; the app reads it at startup with its own identity.
resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.name_prefix}-db-password"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.app.result
}

# Secret-level IAM: these accounts can read this one secret, nothing else.
resource "google_secret_manager_secret_iam_member" "readers" {
  for_each = toset(var.secret_readers)

  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value
}
