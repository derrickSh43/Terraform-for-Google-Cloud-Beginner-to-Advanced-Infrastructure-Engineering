# Customer-managed encryption keys (CMEK). Google still encrypts everything by
# default; CMEK adds control: you can rotate, audit every use, and revoke access
# (crypto-shredding) by disabling the key.

resource "google_project_service" "kms" {
  service            = "cloudkms.googleapis.com"
  disable_on_destroy = false
}

resource "google_kms_key_ring" "this" {
  name     = "meridian-${var.environment}"
  location = lower(coalesce(var.location, var.region)) # must match the location of the buckets it encrypts

  depends_on = [google_project_service.kms]
}

resource "google_kms_crypto_key" "storage" {
  name            = "storage"
  key_ring        = google_kms_key_ring.this.id
  purpose         = "ENCRYPT_DECRYPT"
  rotation_period = "${var.rotation_days * 86400}s"
  labels          = var.labels

  # Destroying a key destroys every piece of data encrypted with it.
  lifecycle {
    prevent_destroy = true
  }
}

# Only Cloud Storage's service agent may use the key - on the key, not the project.
resource "google_kms_crypto_key_iam_member" "storage_agent" {
  crypto_key_id = google_kms_crypto_key.storage.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${var.project_number}@gs-project-accounts.iam.gserviceaccount.com"
}
