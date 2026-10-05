# cross-backend reproducibility Cross-Environment Halo2 Reproducibility

- Hardware label: `local-windows`.
- Verified actual proofs: 10/10.
- Unique proof hashes: 10/10.
- Prove seconds mean±CI95: 1.845185 ± 0.040680.
- Verify seconds mean±CI95: 0.061891 ± 0.009089.
- Peak RSS MiB mean±CI95: 246.213 ± 0.736.

The GitHub Actions matrix repeats a smaller seed set on Windows and Linux runners.
Runner artifacts, rather than fabricated local labels, are the evidence for cross-hardware execution.
EZKL and Halo2 now provide two actual proof backends, but their circuits differ; cost numbers are not treated as a controlled backend head-to-head comparison.