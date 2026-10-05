# cross-backend reproducibility — Cross-backend and cross-environment reproducibility

This experiment strengthens proof reproducibility in three ways:

1. ten independent local seeds each generate and verify a real Halo2 proof;
2. the repository now has actual EZKL and Zcash Halo2 IPA evidence;
3. GitHub Actions repeats Halo2 and accountant tests on Windows and Linux
   hosted runners and uploads hardware manifests and proof-run artifacts.

The EZKL and Halo2 circuits are not identical, so their raw timing is not
presented as an apples-to-apples backend comparison. They establish backend
coverage and portability. Controlled backend comparison requires a shared
intermediate relation and matched hardware.

Run locally:

```powershell
python experiments/cross_backend_reproducibility/run_halo2_seed_benchmark.py
```
