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
      day          = 7 # Sunday
      hour         = 4
      update_track = "stable"
    }

    # IAM database authentication + slow-query logging.
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }


    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
      record_client_address   = false
    }
  }
}

# Passwordless: the app's service account logs in with an IAM token.
resource "google_sql_user" "iam" {
  for_each = toset(var.iam_service_accounts)

  name     = trimsuffix(each.value, ".gserviceaccount.com")
  instance = google_sql_database_instance.this.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
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

  # Data residency: the secret's payload is stored only in these regions.
  replication {
    user_managed {
      replicas {
        location = "us-central1"
      }
      replicas {
        location = "us-east1"
      }
    }
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
