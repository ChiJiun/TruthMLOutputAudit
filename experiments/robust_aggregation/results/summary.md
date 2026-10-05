# robust aggregation Bounded-poisoning Robust Aggregation Summary

- CoverType train/test=50000/20000; K=10, R=5, attackers=20%, seeds=[42, 52, 62, 72, 82, 92, 102, 112, 122, 132].
- Non-IID partition=dirichlet_0.5; clipping C=1.0; Gaussian systems noise multiplier=0.03.
- Attackers submit a sign-reversed update rescaled to the full clipping bound. It satisfies clipping, additive-noise, context, and replay checks, so the strengthened VDP gate accepts it.
- Mean, coordinate-wise median, and coordinate-wise trimmed mean are compared with uniform client weighting and aggregator-specific clean controls.
- Client-update decisions simulate the proved contract; this experiment does not generate one actual proof per decision.

| Aggregator | Clean accuracy | Attack accuracy | Paired change | Retention | Attack p | Attacker accepted |
|---|---:|---:|---:|---:|---:|---:|
| mean | 0.6012 ± 0.0096 | 0.2327 ± 0.0269 | -0.3685 ± 0.0249 | 0.3867 ± 0.0430 | 0.0020 | 1.00 |
| coordinate_median | 0.5911 ± 0.0100 | 0.3463 ± 0.0376 | -0.2448 ± 0.0350 | 0.5855 ± 0.0606 | 0.0020 | 1.00 |
| trimmed_mean | 0.5980 ± 0.0103 | 0.3237 ± 0.0309 | -0.2743 ± 0.0275 | 0.5408 ± 0.0480 | 0.0020 | 1.00 |

## Paired robustness gain over mean

| Robust aggregator | Retention gain | Exact sign-flip p |
|---|---:|---:|
| coordinate_median | 0.1988 ± 0.0404 | 0.0020 |
| trimmed_mean | 0.1541 ± 0.0306 | 0.0020 |

## Scope

This significantly mitigates the tested bounded-poisoning attack through an aggregation defense under the explicit assumption that no more than the trimmed fraction of clients are malicious. It does not eliminate the measured utility loss, establish arbitrary Byzantine robustness, or prove that a client followed the prescribed optimizer; those would require a stronger robust-learning analysis or a separate training-provenance circuit.
