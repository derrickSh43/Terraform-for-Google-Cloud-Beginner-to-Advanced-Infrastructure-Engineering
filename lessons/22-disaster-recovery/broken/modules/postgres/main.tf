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
      ipv4_enabled    = false # no public IP at all
      private_network = var.network_id
      ssl_mode        = "ENCRYPTED_ONLY"
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

# Disaster recovery: an asynchronous read replica in another region. If the
# primary region is lost, promote it (gcloud sql instances promote-replica) and
# point the application at it. RPO: seconds of replication lag.
resource "google_sql_database_instance" "replica" {
  count = var.dr_region == null ? 0 : 1

  name                 = "${var.name_prefix}-pg-${var.dr_region}"
  region               = var.dr_region
  database_version     = google_sql_database_instance.this.database_version
  master_instance_name = "${var.name_prefix}-postgres"
  deletion_protection  = true

  settings {
    tier                        = var.tier
    edition                     = "ENTERPRISE"
    availability_type           = "ZONAL" # make it REGIONAL after promotion
    disk_type                   = "PD_SSD"
    disk_autoresize             = true
    deletion_protection_enabled = true
    user_labels                 = var.labels

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
      ssl_mode        = "ENCRYPTED_ONLY"
    }
  }
}
