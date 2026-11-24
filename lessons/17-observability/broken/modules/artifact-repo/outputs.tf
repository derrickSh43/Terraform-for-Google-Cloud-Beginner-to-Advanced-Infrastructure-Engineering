output "repository_url" {
  description = "Image path prefix: <region>-docker.pkg.dev/<project>/<repository>."
  value       = "${google_artifact_registry_repository.this.location}-docker.pkg.dev/${google_artifact_registry_repository.this.project}/${google_artifact_registry_repository.this.repository_id}"
}
