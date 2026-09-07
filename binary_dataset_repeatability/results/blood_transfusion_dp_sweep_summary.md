# Blood Transfusion DP Parameter Sweep Summary

Problem:
- Under the default DP setting, blood_transfusion stayed below the 90% DP/FL retention threshold.

Baseline setting:
- rounds: 5
- clip_norm: 1.0
- noise_multiplier: 0.08
- FL final mean: 0.615556
- DP final mean: 0.535555
- DP/FL retention: 0.870036

Best setting by DP/FL retention:
- rounds: 15
- clip_norm: 1.0
- noise_multiplier: 0.04
- FL final mean: 0.753333
- DP final mean: 0.744445
- DP/FL retention: 0.988201
- effective: True

Interpretation:
- The improvement process checks whether the weaker default result is caused by untuned DP noise and training length.
- If retention recovers after lowering noise or increasing rounds, the dataset is parameter-sensitive rather than incompatible with the DP prototype.