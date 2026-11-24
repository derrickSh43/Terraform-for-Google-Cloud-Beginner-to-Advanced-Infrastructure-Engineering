output "connection_name" {
  description = "Instance connection name (project:region:instance) for the Cloud SQL connectors."
  value       = google_sql_database_instance.this.connection_name
}

output "private_ip" {
  description = "Private IP of the instance inside the reserved range."
  value       = google_sql_database_instance.this.private_ip_address
}

output "password_secret_id" {
  description = "Secret Manager secret holding the app user's password. The password itself is never an output."
  value       = google_secret_manager_secret.db_password.secret_id
}

output "instance_name" {
  description = "Cloud SQL instance name (for monitoring filters)."
  value       = google_sql_database_instance.this.name
}

output "replica_name" {
  description = "Name of the cross-region replica (null without dr_region)."
  value       = one(google_sql_database_instance.replica[*].name)
}
