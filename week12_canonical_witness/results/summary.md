# Week 12 Canonical Witness Summary

- Honest canonical relations exact: 9/9
- Tampered canonical relations rejected: 9/9
- Honest clipping checks exact without slack: 5/9
- Honest clipping checks covered with observed slack: 9/9
- Max clipping slack needed: 10941
- Max clipping slack needed (ppm): 4200.0
- Max gap between canonical integer witness and float-then-quantize witness: 1

Per-scale view:
- scale=100: clip_without_slack=1/3, max_slack=42, max_slack_ppm=4200.0, canonical_float_gap=1
- scale=1000: clip_without_slack=2/3, max_slack=447, max_slack_ppm=447.0, canonical_float_gap=1
- scale=10000: clip_without_slack=2/3, max_slack=10941, max_slack_ppm=109.41, canonical_float_gap=1

Interpretation:
- Canonical quantized witnesses make the additive noise relation exact by construction.
- Tampered integer witnesses are still easy to reject with a single-coordinate perturbation.
- Clipping still needs a small explicit slack for borderline cases, but the observed relative slack shrinks as scale increases.