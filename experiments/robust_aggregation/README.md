# robust aggregation — Robust Aggregation against Bounded Poisoning

The context-bound randomness circuit proves how noise is derived and attached,
but it does not prove that the clipped update came from honest local training.
This experiment closes that explicitly bounded threat branch with a system-level
defense: coordinate median and coordinate trimmed mean.

Ten paired seeds compare clean and 20%-attacker trajectories on non-IID
CoverType (50,000 training records, 10 clients, 5 rounds). Attackers submit a
sign-reversed vector at the full clipping bound while retaining a valid noise
relation and context, so the strengthened VDP gate accepts every malicious
update. Robust aggregators are compared against uniform mean with their own
clean controls and exact paired sign-flip randomization tests.

This is bounded-poisoning mitigation, not a proof of local training provenance
and not an arbitrary-Byzantine guarantee.

Run:

```powershell
python -m unittest discover -s experiments/robust_aggregation -p "test*.py" -v
python experiments/robust_aggregation/run_robust_aggregation.py
```
