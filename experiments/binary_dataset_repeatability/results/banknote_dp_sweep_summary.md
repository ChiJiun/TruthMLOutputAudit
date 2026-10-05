# Banknote DP Parameter Sweep Summary

Goal:
- Check whether the weak default DP result on banknote-authentication is caused by untuned DP parameters.

Best setting by DP/FL retention:
- rounds: 10
- clip_norm: 1.0
- noise_multiplier: 0.04
- FL final mean: 0.800000
- DP final mean: 0.797576
- DP/FL retention: 0.996970
- effective: True

Interpretation:
- If lower noise or more rounds restores the retention ratio, the earlier failure is a parameter sensitivity issue rather than a hard dataset failure.