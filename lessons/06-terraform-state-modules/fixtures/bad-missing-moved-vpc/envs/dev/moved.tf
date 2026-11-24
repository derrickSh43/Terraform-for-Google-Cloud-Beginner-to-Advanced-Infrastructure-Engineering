# Lesson 05 deployed every resource at the root of one configuration. These
# blocks tell Terraform that each object now lives at a new address inside a
# module, so the refactor changes addresses in state without destroying anything.
# Keep them until every environment's state has been migrated, then delete them.

moved {
  from = google_project_service.apis
  to   = module.foundation.google_project_service.apis
}

moved {
  from = google_storage_bucket.assets
  to   = module.foundation.google_storage_bucket.assets
}


moved {
  from = google_compute_subnetwork.web
  to   = module.network.google_compute_subnetwork.this["web"]
}

moved {
  from = google_compute_subnetwork.app
  to   = module.network.google_compute_subnetwork.this["app"]
}

moved {
  from = google_compute_firewall.allow_http
  to   = module.firewall.google_compute_firewall.this["allow-http"]
}

moved {
  from = google_compute_firewall.allow_iap_ssh
  to   = module.firewall.google_compute_firewall.this["allow-iap-ssh"]
}

moved {
  from = google_compute_firewall.allow_web_to_app
  to   = module.firewall.google_compute_firewall.this["allow-web-to-app"]
}

moved {
  from = google_service_account.web
  to   = module.web.google_service_account.this
}

moved {
  from = google_project_iam_member.web
  to   = module.web.google_project_iam_member.this
}

moved {
  from = google_compute_instance.web
  to   = module.web.google_compute_instance.this
}

moved {
  from = google_service_account.app
  to   = module.app.google_service_account.this
}

moved {
  from = google_project_iam_member.app
  to   = module.app.google_project_iam_member.this
}

moved {
  from = google_compute_instance.app
  to   = module.app.google_compute_instance.this
}
