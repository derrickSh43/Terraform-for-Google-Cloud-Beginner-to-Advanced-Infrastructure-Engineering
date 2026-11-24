output "storage_key_id" {
  description = "Key for bucket default encryption. Available only after the storage agent may use it."
  value       = google_kms_crypto_key.storage.id
}
