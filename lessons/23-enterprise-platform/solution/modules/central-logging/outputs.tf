output "sink_writer_identity" {
  description = "Identity the folder sink writes as."
  value       = google_logging_folder_sink.central.writer_identity
}
