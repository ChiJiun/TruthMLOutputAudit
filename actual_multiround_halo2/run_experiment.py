"""Run every proof, verify saved proofs, and summarize at the seed level."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cross_backend_reproducibility.run_halo2_seed_benchmark import (
    build_binary, confidence_interval, hardware_manifest, run_with_peak_rss,
)


def save(path, content):
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")


def audit_report(report):
    clients, rounds = report["clients"], report["rounds"]
    records = report["updates"]
    expected = {(r, c) for r in range(rounds) for c in range(clients)}
    assert len(records) == len(expected)
    assert {(r["round"], r["client"]) for r in records} == expected
    assert all(r["gate"] == "accepted" for r in records)
    assert len({r["proof_sha256"] for r in records}) == len(records)
    attacks = {"duplicate_submission", "client_swap", "round_swap", "model_swap",
               "noisy_update_tamper", "corrupt_proof", "retry_after_failure"}
    assert len(report["probes"]) == len(expected) * len(attacks)
    assert {(p["round"], p["client"], p["attack"]) for p in report["probes"]} == {
        (r, c, a) for r, c in expected for a in attacks
    }
    for p in report["probes"]:
        assert p["gate"] != "accepted"
        assert p["cryptographic_verified"] == (p["attack"] in {"duplicate_submission", "retry_after_failure"})
    assert len(report["trajectory"]) == rounds
    assert all(r["same_noisy_updates_without_gate_max_abs_difference"] == 0 for r in report["trajectory"])


def negative_disk_checks(binary, run_path):
    """A saved verifier must reject altered state and altered proof bytes."""
    original = json.loads(run_path.read_text())
    results = []
    for case in ("model_chain", "noisy_value", "proof_bytes"):
        changed = json.loads(json.dumps(original))
        if case == "model_chain":
            changed["trajectory"][0]["model_after"][0] += 1.0
        elif case == "noisy_value":
            changed["updates"][0]["q_noisy"][0] += 1
        else:
            first = changed["updates"][0]
            data = bytearray((run_path.parent / first["proof_file"]).read_bytes())
            data[0] ^= 1
            corrupt = run_path.parent / "audit_corrupt.bin"
            corrupt.write_bytes(data)
            first["proof_file"] = corrupt.name
            # Recompute hash so this test reaches actual cryptographic verification.
            first["proof_sha256"] = hashlib.sha256(data).hexdigest()
        candidate = run_path.parent / f"audit_invalid_{case}.json"
        save(candidate, changed)
        completed = subprocess.run([str(binary), "--verify-federated", str(candidate)], capture_output=True, text=True)
        assert completed.returncode != 0, f"Verifier accepted {case} tampering"
        results.append({"case": case, "rejected": True, "returncode": completed.returncode,
                        "output": completed.stdout + completed.stderr})
    return results


def summarize(rows, reports):
    fields = ("prove_mean_seconds", "verify_mean_seconds", "wall_seconds", "peak_rss_mib",
              "keygen_seconds", "proof_gated_final_accuracy", "quantized_no_noise_final_accuracy")
    metrics = {}
    for field in fields:
        values = [r[field] for r in rows]
        metrics[field] = {"mean": statistics.fmean(values), "ci95_half_width": confidence_interval(values)}
    updates = [u for r in reports for u in r["updates"]]
    probes = [p for r in reports for p in r["probes"]]
    return {"seed_count": len(rows), "actual_proofs": len(updates),
            "unique_proof_hashes": len({u["proof_sha256"] for u in updates}),
            "proof_bytes_total": sum(u["proof_bytes"] for u in updates),
            "disk_reverified_proofs": len(updates), "negative_probes": len(probes),
            "negative_probes_rejected": sum(p["gate"] != "accepted" for p in probes),
            "metrics": metrics, "ci_unit": "one complete seeded trajectory (not individual proofs)",
            "scope": "fixed four-dimensional synthetic logistic FL; real proofs per update; no local training provenance or full-transcript DP certification"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "results_roundtrip")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 52, 62, 72, 82])
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    assert len(set(args.seeds)) == len(args.seeds)
    output = args.output_dir.resolve()
    config = {"seeds": args.seeds, "clients": args.clients, "rounds": args.rounds,
              "quantization_unit": 0.1, "dimension": 4, "k": 16,
              "data": "public synthetic, 64/client, 512 test, seeded client feature shift",
              "negative_probes": "isolated ticket copies except duplicate live submissions; no poisoning trajectory",
              "predeclared_use": "integration and cost, descriptive accuracy only; no seed selection"}
    source_paths = [ROOT / "halo2_verifiable_randomness/src/main.rs", ROOT / "halo2_verifiable_randomness/src/federated.rs",
                    ROOT / "halo2_verifiable_randomness/Cargo.lock", ROOT / "halo2_verifiable_randomness/Cargo.toml", Path(__file__)]
    config["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    if output.exists():
        if not args.resume or not (output / "config.json").exists():
            raise FileExistsError("Choose a new output-dir; --resume only accepts matching complete seed runs")
        assert json.loads((output / "config.json").read_text()) == config, "resume configuration/source mismatch"
    else:
        output.mkdir(parents=True)
        save(output / "config.json", config)
    binary = build_binary()
    manifest = hardware_manifest("actual-multiround-local")
    manifest["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest["git_status_at_start"] = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)
    manifest["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
    save(output / "hardware_manifest.json", manifest)
    rows, reports = [], []
    for seed in args.seeds:
        destination = output / f"seed_{seed}"
        if destination.exists():
            assert args.resume and (destination / "measurement.json").exists(), "incomplete seed: choose a new output-dir"
            measurement = json.loads((destination / "measurement.json").read_text())
        else:
            wall, rss, stdout = run_with_peak_rss([str(binary), "--federated", str(destination), str(seed), str(args.clients), str(args.rounds)])
            measurement = {"wall_seconds": wall, "peak_rss_mib": rss, "stdout": stdout}
            save(destination / "measurement.json", measurement)
        path = destination / "run.json"
        report = json.loads(path.read_text())
        assert (report["seed"], report["clients"], report["rounds"]) == (seed, args.clients, args.rounds)
        audit_report(report)
        verify_start = time.perf_counter()
        disk = subprocess.run([str(binary), "--verify-federated", str(path)], check=True, capture_output=True, text=True)
        save(destination / "disk_verification.json", {"passed": True, "stdout": disk.stdout, "wall_seconds": time.perf_counter() - verify_start})
        if seed == args.seeds[0]:
            save(destination / "negative_disk_checks.json", negative_disk_checks(binary, path))
        final = report["trajectory"][-1]
        rows.append({"seed": seed, **measurement,
                     "prove_mean_seconds": statistics.fmean(u["prove_seconds"] for u in report["updates"]),
                     "verify_mean_seconds": statistics.fmean(u["verify_seconds"] for u in report["updates"]),
                     "keygen_seconds": report["keygen_seconds"],
                     "proof_gated_final_accuracy": final["proof_gated_accuracy"],
                     "quantized_no_noise_final_accuracy": final["quantized_no_noise_accuracy"]})
        reports.append(report)
        save(output / "seed_measurements.json", rows)
        print(f"seed={seed} actual={len(report['updates'])} disk_verified=true peak_rss={measurement['peak_rss_mib']:.1f} MiB", flush=True)
    summary = summarize(rows, reports)
    assert summary["actual_proofs"] == summary["unique_proof_hashes"]
    save(output / "summary.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
