# Troubleshooting 12 — "Just for a minute"

A developer couldn't reach the database from home, so they "temporarily" changed
the postgres module. The PR description reads *"TEMP: will revert after
debugging"*. That was three weeks ago. The database logs show login attempts
from addresses in a dozen countries.

```powershell
Copy-Item -Recurse lessons/12-databases/broken workspace/12-broken
python course.py check 12 --path workspace/12-broken
```

1. Which requirement fails? What exactly is exposed, and to whom?
2. The password is 32 random characters and TLS is required. Why is this still a serious problem? (Think beyond password guessing.)
3. Revert it. Then describe a *safe* way for a developer to reach a private Cloud SQL instance from a laptop.
4. How could this have been blocked before review? (Lesson 19: organization policies.)

Answer: [ANSWER.md](ANSWER.md)
