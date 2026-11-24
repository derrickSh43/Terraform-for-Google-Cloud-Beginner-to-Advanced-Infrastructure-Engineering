# Troubleshooting 11 — "Every apply detaches the data disk"

The disk PR was applied on Monday. Since then, every `terraform plan` shows:

```
# module.app.google_compute_instance.this will be updated in-place
  - attached_disk {
      - device_name = "data"
      ...
    }
```

Tuesday's unrelated firewall change was applied with that diff included. The
data disk was detached from the running app VM, and the next apply re-attached it.
The API went down twice.

```powershell
Copy-Item -Recurse lessons/11-storage-persistent-data/broken workspace/11-broken
python course.py check 11 --path workspace/11-broken
```

1. Which requirement fails? Find the two resources that both claim the disk attachment.
2. Why does today's (first) plan look fine, when every plan *after* the first apply shows the diff?
3. Fix it with one block. What exactly does that block tell Terraform?
4. Name another resource pair with the same pattern. (Hint: `google_compute_instance_group` membership, security policies...)

Answer: [ANSWER.md](ANSWER.md)
