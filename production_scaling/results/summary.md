# production-oriented scaling Production-oriented Scaling Summary

- CoverType train/test=50000/20000, non-IID dirichlet_0.5, seeds=[42, 52, 62, 72, 82].
- FL trajectories are actual CPU training. `vdp_cbd` uses clipping plus centered-binomial systems-stress noise.
- EZKL rows are actual proofs of the full update-vector clipping/relation constraint dimensions.
- Full local training is not inside EZKL; all-update proof totals below are explicit extrapolations, not executed end-to-end runs.

| Profile | Mode | Params | K x R | Accuracy mean ± CI95 | Training sec mean ± CI95 | Estimated serial proof h | Estimated proofs MiB |
|---|---|---:|---:|---:|---:|---:|---:|
| linear_k10_r3 | clean | 385 | 10 x 3 | 0.5658 ± 0.0591 | 3.58 ± 0.83 | 0.004 | 0.35 |
| linear_k10_r3 | vdp_cbd | 385 | 10 x 3 | 0.5521 ± 0.0635 | 3.15 ± 0.95 | 0.004 | 0.35 |
| linear_k25_r10 | clean | 385 | 25 x 10 | 0.6260 ± 0.0107 | 7.84 ± 0.68 | 0.037 | 2.92 |
| linear_k25_r10 | vdp_cbd | 385 | 25 x 10 | 0.6243 ± 0.0092 | 7.75 ± 0.43 | 0.037 | 2.92 |
| linear_k50_r20 | clean | 385 | 50 x 20 | 0.6384 ± 0.0075 | 28.35 ± 5.34 | 0.147 | 11.70 |
| linear_k50_r20 | vdp_cbd | 385 | 50 x 20 | 0.6352 ± 0.0108 | 26.94 ± 7.78 | 0.147 | 11.70 |
| mlp16_k25_r10 | clean | 999 | 25 x 10 | 0.6007 ± 0.0301 | 13.25 ± 1.96 | 0.106 | 2.93 |
| mlp16_k25_r10 | vdp_cbd | 999 | 25 x 10 | 0.6004 ± 0.0291 | 14.59 ± 0.91 | 0.106 | 2.93 |

## Actual EZKL single-proof measurements

| Model | Dimension | Seeds | Prove sec mean ± CI95 | Verify sec mean ± CI95 | Proof bytes mean | Peak RSS MiB mean |
|---|---:|---:|---:|---:|---:|---:|
| linear | 385 | 3 | 0.530 ± 0.136 | 0.046 ± 0.012 | 12268 | 419.1 |
| mlp_16 | 999 | 3 | 1.524 ± 0.249 | 0.054 ± 0.005 | 12286 | 439.4 |
| mlp_32 | 1991 | 3 | 1.658 ± 0.431 | 0.050 ± 0.016 | 12282 | 471.3 |