# Troubleshooting 04 — The address that looks right

A junior engineer swears the subnet range is fine: "it's in 10.10.1.x, just like the docs".
Validate and plan both pass. The check fails, and on real GCP the subnet
create call would be rejected.

```powershell
Copy-Item -Recurse lessons/04-vpc-fundamentals/broken workspace/04-broken
python course.py check 04 --path workspace/04-broken
```

1. Which value is wrong, and *what exactly* is wrong with it?
2. Work out the network address, broadcast address and usable host range of the correct subnet by hand.
3. How many IPs does Google Cloud reserve in every subnet? Which ones?
4. Make it impossible to repeat: add a `validation` to the variable. (`cidrhost` and `cidrnetmask` may help.)

Answer: [ANSWER.md](ANSWER.md)
