# Week 7 DP-FedAvg Summary

- Initial accuracy: 0.694851
- Final accuracy: 0.838776
- Best accuracy: 0.844201
- Mean round time: 1.2266 sec

Configuration:
- clients: 3
- rounds: 5
- local_epochs: 1
- clip_norm: 1.0
- noise_multiplier: 0.08
- noise_mode: seeded_deterministic

Note:
- This Week 7 baseline now uses seed-based deterministic noise so each client update can be replayed and verified.
- It is useful for trend comparison, but not yet a formal privacy accountant implementation.