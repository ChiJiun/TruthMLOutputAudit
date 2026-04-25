# Week 17 Proof-Gated Round Summary

- Tampered client: 1
- Accepted proofs: 2/3
- Rejected proofs: 1/3
- Tampered client accepted: False
- Accepted aggregate vector length: 10

Accepted clients:
- client 0 (honest_profile): verified=True, clip_ok=True, relation_ok=True
- client 2 (honest_profile): verified=True, clip_ok=True, relation_ok=True

Rejected clients:
- client 1 (tampered_noisy_profile): verified=True, clip_ok=True, relation_ok=False

Interpretation:
- This experiment runs actual EZKL-backed client checks before aggregation.
- The server only aggregates q_noisy vectors from clients whose proofs verify and whose recommended-profile checks pass.
- This is closer to a true proof-gated FL+VDP round than the earlier single-artifact smoke test.