# Week 16 Actual EZKL Constraint Demo Summary

- honest_profile: verified=True, clip_ok=True, relation_ok=True, clip_sum_sq=98890816.0, relation_sum_sq=0.0
- tampered_noisy_profile: verified=True, clip_ok=True, relation_ok=False, clip_sum_sq=98890816.0, relation_sum_sq=1.0

Interpretation:
- This demo uses the real EZKL Python API on a small ONNX check model derived from the recommended constraint profile.
- A successful verify means the backend can prove the arithmetic check model for the supplied artifact.
- The artifact is still separate from a full FL training circuit, but this moves S2 from stub-only to actual proof/verify on constraint-style data.