# Week 11 Quantized Constraint Summary

- Scales tested: [100, 1000, 10000]
- Honest integer clipping bounds exact: 5/9
- Honest quantized noise relations exact: 0/9
- Tampered quantized relations rejected: 9/9
- Max float-vs-quantized relation gap: 1
- Max clipping-bound excess after quantization: 10941
- Max clipping-bound excess after quantization (ppm): 4200.0

Per-scale view:
- scale=100: exact_clip=1/3, max_excess=42, max_excess_ppm=4200.0
- scale=1000: exact_clip=2/3, max_excess=447, max_excess_ppm=447.0
- scale=10000: exact_clip=2/3, max_excess=10941, max_excess_ppm=109.41

Interpretation:
- A direct integer sum-of-squares bound is close to the float clipping rule, but borderline clipped updates can cross the bound after rounding.
- The noisy-update relation may lose exact equality after independent rounding of clipped update and noise.
- If either gap is non-zero, the future circuit design must define a canonical quantization rule and possibly an explicit slack policy.