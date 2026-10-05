# production-oriented scaling — Production-oriented Scaling

This experiment separates two questions that are often conflated:

1. actual non-IID CoverType FL training at up to 50 clients and 20 rounds;
2. actual EZKL single-proof cost as audited update dimension grows from 385
   (linear) to 999/1,991 parameters (one-hidden-layer MLPs).

Five independent seeds are used for paired clean versus clipped
centered-binomial-noise trajectories. Three independent seeds are used for
each actual EZKL dimension. The cost of proving every client update is reported
only as a transparent extrapolation from actual single-proof measurements.

The EZKL circuit audits the full update-vector clipping statistic and additive
noise relation. It does **not** prove the local optimizer or training data
provenance. robust aggregation evaluates robust aggregation for that remaining threat.

Run:

```powershell
python experiments/production_scaling/run_production_scaling.py
```
