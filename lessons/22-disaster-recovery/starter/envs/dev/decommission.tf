# The app tier no longer runs on a single VM. Its data disk holds files the team
# is still copying to the backups bucket: keep the disk, stop managing it here.
# Delete it by hand once the copy is verified (and then remove this block).
removed {
  from = module.app.google_compute_disk.data

  lifecycle {
    destroy = false
  }
}
