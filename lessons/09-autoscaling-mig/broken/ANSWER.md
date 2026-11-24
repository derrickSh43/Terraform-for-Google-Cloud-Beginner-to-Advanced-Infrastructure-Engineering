# Answer — Troubleshooting 09

**Symptom:** R9.4: `initial_delay_sec = 10: shorter than boot + apt-get + NGINX start`.

**Root cause:** `autoheal_initial_delay_sec` defaults to **10** seconds in
`modules/mig-service/variables.tf`. A new VM needs roughly 30–60 s to boot and
another 30–90 s for `apt-get update && apt-get install nginx`. Ten seconds after
creation, the autohealing check probes port 80, finds nothing, and once the
unhealthy threshold is reached the MIG **recreates** the VM. The replacement
starts the same race and loses the same way. The MIG never has a healthy instance,
so the load balancer has nothing to send traffic to.

**Fix:** set the grace period comfortably above the worst-case startup time:

```hcl
default = 180
```

Better still, bake NGINX into a custom image (Packer, lesson 16 CI) so startup
takes seconds, then lower the delay.

**Which check reacts faster?** The **load balancer** check: removing a VM from
rotation is cheap and instantly reversible. **Autohealing** should be slower and
more tolerant (higher interval and threshold, generous initial delay), because
its remedy is to destroy the VM.
