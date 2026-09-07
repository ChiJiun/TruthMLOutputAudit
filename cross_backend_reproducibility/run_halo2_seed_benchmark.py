"""Run actual Halo2 proofs across independent experiment seeds."""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

import psutil
from scipy.stats import t as student_t


ROOT = Path(__file__).resolve().parents[1]
CRATE = ROOT / "halo2_verifiable_randomness"
DEFAULT_RESULTS = Path(__file__).resolve().parent / "results"
DEFAULT_SEEDS = [42, 52, 62, 72, 82, 92, 102, 112, 122, 132]


def command_version(command: list[str]) -> str | None:
    executable = shutil.which(command[0])
    if executable is None:
        return None
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()


def package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def hardware_manifest(label: str) -> dict[str, object]:
    memory = psutil.virtual_memory()
    return {
        "label": label,
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "memory_bytes": memory.total,
        "python": sys.version,
        "rustc": command_version(["rustc", "--version"]),
        "cargo": command_version(["cargo", "--version"]),
        "packages": {
            "psutil": package_version("psutil"),
            "scipy": package_version("scipy"),
        },
        "ci": bool(os.environ.get("CI")),
        "github_runner_os": os.environ.get("RUNNER_OS"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
    }


def build_binary() -> Path:
    subprocess.run(["cargo", "build", "--release"], cwd=CRATE, check=True)
    suffix = ".exe" if os.name == "nt" else ""
    return CRATE / "target" / "release" / f"vdp-halo2-verifiable-randomness{suffix}"


def run_with_peak_rss(command: list[str]) -> tuple[float, float, str]:
    start = time.perf_counter()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    peak = 0
    while process.poll() is None:
        try:
            root = psutil.Process(process.pid)
            usage = root.memory_info().rss
            for child in root.children(recursive=True):
                try:
                    usage += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            peak = max(peak, usage)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        time.sleep(0.01)
    stdout, _ = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"Proof command failed ({process.returncode}):\n{stdout}")
    return time.perf_counter() - start, peak / (1024 * 1024), stdout.strip()


def confidence_interval(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(student_t.ppf(0.975, len(values) - 1)) * statistics.stdev(values) / len(values) ** 0.5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--label", default=os.environ.get("RUNNER_OS", "local-windows"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    proof_dir = args.output_dir / "proof_runs"
    proof_dir.mkdir(exist_ok=True)

    binary = build_binary()
    rows: list[dict[str, object]] = []
    for seed in args.seeds:
        output = proof_dir / f"seed_{seed}.json"
        wall_seconds, peak_rss_mib, stdout = run_with_peak_rss(
            [str(binary), str(output), str(seed)]
        )
        report = json.loads(output.read_text(encoding="utf-8"))
        if not report["proof_verified"]:
            raise AssertionError(f"Seed {seed} proof did not verify")
        rows.append(
            {
                "seed": seed,
                "backend": report["backend"],
                "proof_verified": report["proof_verified"],
                "proof_bytes": report["proof_bytes"],
                "proof_sha256": report["proof_sha256"],
                "keygen_seconds": report["keygen_seconds"],
                "prove_seconds": report["prove_seconds"],
                "verify_seconds": report["verify_seconds"],
                "wall_seconds": round(wall_seconds, 9),
                "peak_rss_mib": round(peak_rss_mib, 3),
                "stdout": stdout,
            }
        )

    with (args.output_dir / "halo2_seed_runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = hardware_manifest(args.label)
    (args.output_dir / "hardware_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    metrics = {}
    for field in ("keygen_seconds", "prove_seconds", "verify_seconds", "peak_rss_mib", "proof_bytes"):
        values = [float(row[field]) for row in rows]
        metrics[field] = {
            "mean": statistics.fmean(values),
            "sd": statistics.stdev(values) if len(values) > 1 else 0.0,
            "ci95_half_width": confidence_interval(values),
            "min": min(values),
            "max": max(values),
        }
    summary = {
        "seeds": args.seeds,
        "runs": len(rows),
        "verified_runs": sum(bool(row["proof_verified"]) for row in rows),
        "unique_proof_hashes": len({row["proof_sha256"] for row in rows}),
        "metrics": metrics,
        "hardware_label": args.label,
        "backend_scope": "Halo2 actual proofs; EZKL evidence is reported separately and is not an identical circuit",
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    lines = [
        "# cross-backend reproducibility Cross-Environment Halo2 Reproducibility",
        "",
        f"- Hardware label: `{args.label}`.",
        f"- Verified actual proofs: {summary['verified_runs']}/{summary['runs']}.",
        f"- Unique proof hashes: {summary['unique_proof_hashes']}/{summary['runs']}.",
        f"- Prove seconds mean±CI95: {metrics['prove_seconds']['mean']:.6f} ± {metrics['prove_seconds']['ci95_half_width']:.6f}.",
        f"- Verify seconds mean±CI95: {metrics['verify_seconds']['mean']:.6f} ± {metrics['verify_seconds']['ci95_half_width']:.6f}.",
        f"- Peak RSS MiB mean±CI95: {metrics['peak_rss_mib']['mean']:.3f} ± {metrics['peak_rss_mib']['ci95_half_width']:.3f}.",
        "",
        "The GitHub Actions matrix repeats a smaller seed set on Windows and Linux runners.",
        "Runner artifacts, rather than fabricated local labels, are the evidence for cross-hardware execution.",
        "EZKL and Halo2 now provide two actual proof backends, but their circuits differ; cost numbers are not treated as a controlled backend head-to-head comparison.",
    ]
    (args.output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Verified {summary['verified_runs']}/{summary['runs']} Halo2 proofs on {args.label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
