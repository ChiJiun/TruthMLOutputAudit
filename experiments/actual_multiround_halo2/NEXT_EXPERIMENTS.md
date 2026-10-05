# Follow-up experiments ranked by the evidence gap

1. **Mixed accepted/rejected live training rounds.** Current five-seed integration
   has honest actual-proof trajectories and isolated negative probes. Add one
   malicious submission per round, enforce failed-ticket consumption, then measure
   accepted cohort size, exact aggregation, utility and availability. Keep fixed
   participation accounting separate from data-dependent dropouts/rejections.
2. **A real-data four-coordinate experiment.** Predeclare a public feature subset
   and quantization, compare no-noise / noisy-no-proof / actual-proof training with
   identical data/splits, then measure utility without changing the circuit profile.
   Keep test and preprocessing data leakage checks explicit. Synthetic data in the
   current run only establishes integration, not dataset generality.
3. **Reviewed full-transcript privacy and adaptive composition.** Audit commitments,
   PRF inputs, zero-knowledge simulation, secret reuse, field-bit bias transfer,
   numerical error bounds and timing; prove how the accountant relates to the
   complete released view. The new basic-composition diagnostic does not certify
   that view or invalidate the earlier fixed-profile PLD result.
4. **Controlled key reuse / concurrency comparison.** Hold circuit, input profile,
   host and seed matrix fixed. Compare cold keygen, warm keys and parallel proving;
   separately measure end-to-end latency and peak RSS under concurrency. Current
   run reuses keys but does not establish a causal speedup against a matched cold run.
5. **Higher-dimensional actual sampler circuit only after calibration.** Define
   adjacency, allowed update set, noise unit and target budget first. The simple
   coordinatewise extension with k=16 can fail the delta floor; changing k in an
   accountant is not implementing/testing the corresponding larger circuit.

Before increasing seeds, fix the above question and protocol. Preserve negative
results and count seeded trajectories, not correlated proofs, as statistical units.
