# Troubleshooting 19 — "Since the encryption change, every backup fails"

The CMEK PR merged on Tuesday. From that night on, the app's backup job logs:

```
403 Permission denied on Cloud KMS key projects/.../cryptoKeys/storage
(or it may not exist).
```

The key exists, rotation is configured, and the bucket shows the key as its default.
The audit log bucket has stopped receiving logs too.

```powershell
Copy-Item -Recurse lessons/19-advanced-security/broken workspace/19-broken
python course.py check 19 --path workspace/19-broken
```

1. Which requirement fails? Whose permission is the error actually about?
2. Why doesn't granting `meridian-app` access to the key fix it?
3. Fix it. Then explain why the module's output has a `depends_on`, and what happens on a fresh environment without it.
4. Why is this outage silent for objects written *before* Tuesday?

Answer: [ANSWER.md](ANSWER.md)
