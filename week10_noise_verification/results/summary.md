# Week 10 Noise Verification Summary

- Clip norm: 1.0
- Noise multiplier: 0.08
- Honest cases accepted: 3/3
- Tampered cases rejected: 6/6

Interpretation:
- Honest cases satisfy both the seed-to-noise mapping and the noisy-update relation.
- Tampered cases can break either the generated noise itself or the final noisy update relation.

Current status:
- This prototype uses deterministic seed-based noise so the process can be verified.
- Week 7 baseline has been aligned to the same seed-based noise direction, but the project still needs formal DP accounting and ZK circuit mapping.