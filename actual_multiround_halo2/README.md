# Actual multi-round Halo2 experiment

This closes the gap between a fixed-vector standalone proof and an actual proof
for every update in a small, explicitly bounded FL trajectory.

## Protocol and predeclared experiment

- Five seeds: 42, 52, 62, 72, 82; three clients; ten synchronous rounds.
- Public synthetic binary data: 64 records/client and 512 test records. Three
  features and one bias give exactly four coordinates. Client feature shifts
  introduce heterogeneity, not a natural-client benchmark.
- Two full-batch local logistic steps, learning rate 0.5. Update divided by 0.1,
  rounded and clipped coordinatewise to {-1,0,1}, satisfying C²=4. This is a
  deliberately restricted quantizer, not full-precision FedAvg.
- Setup-time OS-random secret per client; fresh OS-random salt/challenge per
  update. Update commitment precedes challenge generation. Context binds client,
  round, canonical model digest, nonce, challenge and update commitment.
- One key setup per trajectory. Every update gets an actual IPA proof and
  verification; only accepted updates enter uniform aggregation.
- Control A trains without noise on the same data/initialization. Control B
  aggregates exactly the same noisy vectors without the gate. Control B is an
  arithmetic equivalence check, not independently timed training or an attack trial.
- Seven probes/update: duplicate, client/round/model substitution, noisy-vector
  tamper, corrupted proof and retry after failure. Duplicate uses the consumed
  live ticket. Other probes use isolated ticket copies, not seven independently
  poisoned training trajectories. No claim of adaptive attack defense.
- Every proof and public statement is saved. A separate invocation regenerates
  the verification key from the witness-free circuit, verifies all saved proofs,
  checks setup commitments/model context, and reconstructs the model chain.
  Three negative saved-artifact tests must fail.

## Run

Use a new output directory. The runner refuses overwrites and partial restarts.
Fresh secrets mean new proofs and noisy accuracy on repeated runs: seeds determine
data, not keys. Resume requires identical source hashes/configuration and complete
seed artifacts.

```powershell
python -m unittest discover -s actual_multiround_halo2 -p "test*.py" -v
python actual_multiround_halo2/run_experiment.py --output-dir actual_multiround_halo2/my-run
python actual_multiround_halo2/privacy_boundary.py --output-dir actual_multiround_halo2/my-privacy
python actual_multiround_halo2/build_report.py --results-dir actual_multiround_halo2/my-run
```

Standalone disk verification (repository root):

```powershell
cargo run --release --manifest-path halo2_verifiable_randomness/Cargo.toml -- --verify-federated actual_multiround_halo2/my-run/seed_42/run.json
```

CI runs a 2-client/2-round instance on Windows and Linux. A configured workflow
is not successful execution evidence until its actual run completes.

## Privacy interpretation

`privacy_boundary.py` evaluates ideal independent binomial mechanisms, using
exact rational support mismatch and conservative scalar basic composition. It
enumerates both allowed scalar shifts, with 70-digit Decimal evaluation and a
positive margin; this is not a verified interval-arithmetic numerical library.

The earlier PLD epsilon=28.840669 is retained as the existing accountant's
fixed-profile result. Basic composition is a looser bound, not increased measured
leakage or a replacement assertion about that PLD calculation. Justifying its
tight bound for adaptive training needs a reviewed dominating-pair argument.

Timing, clean-control accuracy and commitments are research diagnostics. This
experiment does not certify DP for their complete joint transcript. That requires
review of commitment hiding, PRF/ZK simulation and advantage accounting,
adaptivity, finite-field bias transfer and timing side channels. Local-training
provenance, selective-abort and collusion guarantees are absent.

The hypothetical 385/1,991-dimensional extensions retain coordinate range +/-1
and k=16 with independent noise. Their support floors are not privacy budgets
for production_scaling models, which use different ranges/noise units.

Composition reference: Dwork and Roth, *The Algorithmic Foundations of
Differential Privacy*, §3.5 and Appendix B:
https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf

## Results and failure history

`results/seed_42` is the initial pilot: 30 live proofs passed, but disk model-chain
reconstruction initially failed because default JSON float parsing changed one
ULP. It is excluded from the successful matrix. After enabling serde_json
`float_roundtrip`, all 30 pilot proofs and the model chain independently passed.
`results_roundtrip` is a fresh five-seed matrix after that fix. The regression
checks bit-for-bit serialization; no approximate model-hash tolerance was added.

Evidence includes proofs, run.json, disk-verification logs, negative-check logs,
seed-level metrics, hardware/binary/source hashes and a plot. CIs use complete
seeded trajectories as independent units. Five-seed accuracy is descriptive and
does not establish population utility or production readiness.
