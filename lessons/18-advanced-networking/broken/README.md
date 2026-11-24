# Troubleshooting 18 — "BGP is up, but dev can't reach the stores"

The network team reports success: both tunnels are `ESTABLISHED`, all four BGP
sessions are `UP`, and the hub's routes table lists `192.168.10.0/24` via the VPN.
Yet from a dev VM, `ping 192.168.10.20` times out, and dev's effective routes show
no route to on-prem at all.

```powershell
Copy-Item -Recurse lessons/18-advanced-networking/broken workspace/18-broken
python course.py check 18 --path workspace/18-broken
```

1. Which requirement fails? Which network *knows* the on-prem route, and which doesn't?
2. Draw the path a packet from dev would take. Where does route propagation stop?
3. Fix it. Why does the fix need settings on **both** halves of the peering?
4. Once dev has the route, can on-prem reply? (Hint: R18.5.)

Answer: [ANSWER.md](ANSWER.md)
