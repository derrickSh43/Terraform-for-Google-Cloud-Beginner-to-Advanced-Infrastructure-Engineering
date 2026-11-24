output "storage_key_id" {
  description = "Key for bucket default encryption. Available only after the storage agent may use it."
  value       = google_kms_crypto_key.storage.id

  # Buckets that read this output wait for the grant - otherwise the first write fails.
  depends_on = [google_kms_crypto_key_iam_member.storage_agent]
}
