# Context-Bound Hidden-Randomness Reference Protocol

This module turns the randomness and replay gaps identified by the Gaussian
privacy audit and multi-round threat matrix into an executable protocol
contract.

Implemented:

- immutable setup-time client randomness commitment
- commit-before-challenge state transition
- one fresh challenge per committed client update
- hidden seed derivation bound to client, round, model, nonce and update commitment
- deterministic integer centered-binomial reference sampler
- clipping, exact noise generation and additive relation checks
- challenge consumption and replay cache
- ten honest/adversarial reference cases

Run:

```powershell
python experiments/context_bound_randomness_protocol/run_reference_threats.py
python -m unittest discover -s experiments/context_bound_randomness_protocol -p "test*.py" -v
```

Important: this is a host-side evaluator for the intended circuit relation, not an actual ZK proof or finite-epsilon DP construction. See `protocol_spec.md` for the exact claim boundary.
