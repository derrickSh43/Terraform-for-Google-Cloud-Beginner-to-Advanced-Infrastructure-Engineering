# Answer — Troubleshooting 24

**Fault:** `envs/prod/terraform.tfvars` sets `web_min_replicas = 3`, but `docs/failure-analysis.md`
still says 6 → 4.

1. **R24.4** fails through **R21.6** (lesson 21): "prod keeps enough capacity after losing any zone
   (web 4, app 2 at minimum scale)". **R24.9** fails as well: the table no longer matches the plan.
2. The table says minimum 6, 4 left. With `EVEN` distribution over 3 zones a zone holds `ceil(3/3) = 1`
   VM, so **3 → 2 left**. Two VMs at 150 req/s each is 300 req/s, against a 500 req/s peak.
3. The plan was a harmless-looking in-place update: nothing destroyed or replaced, so the lesson 7–19
   "safe change" habits didn't flag it. Capacity isn't a property of one resource. It's arithmetic
   across the MIG, the autoscaler and the zones. Two places would have caught it:
   - **the baselines** (R21.6 inside R24.4), if `course check` or an equivalent policy check ran in the PR plan job;
   - **the docs check** (R24.9). Docs that are compared with the plan go stale loudly, not silently.

   A third option is a Terraform `check` block or a variable `validation` in `envs/prod`:
   `web_min_replicas - ceil(web_min_replicas / length(web_zones)) >= 4`.
4. Either set `web_min_replicas = 6` again, or keep 3 and **change the promise**. In that case,
   update the table, write an ADR that records the decision (lower cost against reduced capacity
   during a zone outage, accepted by the business), update the R21.6 target, and change the alerting
   so that a zone loss pages someone to scale up by hand. Changing only the number in the table
   would hide the risk.
