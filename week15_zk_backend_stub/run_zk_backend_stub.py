"""
Week 15 - Backend-ready bundle export for the recommended constraint profile.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
SOURCE_ARTIFACTS_DIR = ROOT_DIR / "week14_constraint_artifacts" / "results" / "artifacts"
RESULTS_DIR = BASE_DIR / "results"
BUNDLES_DIR = RESULTS_DIR / "bundles"
os.chdir(BASE_DIR)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def export_bundle(source_path: Path, output_dir: Path) -> dict[str, object]:
    artifact = load_json(source_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    public_inputs = artifact["public_inputs"]
    witness = artifact["witness"]
    checks = artifact["checks"]
    meta = artifact["meta"]

    io_bundle = {
        "input_shapes": meta["shapes"],
        "public_inputs": public_inputs,
        "witness_vectors": witness,
    }
    verification_hint = {
        "expected_clip_ok": checks["clip_ok"],
        "expected_relation_ok": checks["relation_ok"],
        "expected_clip_bound_excess": checks["clip_bound_excess"],
        "expected_relation_linf_gap": checks["relation_linf_gap"],
    }
    backend_note = {
        "status": "stub_only",
        "reason": "ezkl backend not available in current environment",
        "next_step": "map q_clipped/q_noise/q_noisy vectors into real circuit inputs and witness generation",
    }

    (output_dir / "io_bundle.json").write_text(json.dumps(io_bundle, indent=2), encoding="utf-8")
    (output_dir / "verification_hint.json").write_text(json.dumps(verification_hint, indent=2), encoding="utf-8")
    (output_dir / "backend_note.json").write_text(json.dumps(backend_note, indent=2), encoding="utf-8")

    return {
        "source_artifact": str(source_path.relative_to(ROOT_DIR)),
        "bundle_dir": str(output_dir.relative_to(ROOT_DIR)),
        "case_name": meta["case_name"],
        "client_id": meta["client_id"],
        "scale": meta["scale"],
        "clip_ok": checks["clip_ok"],
        "relation_ok": checks["relation_ok"],
    }


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_artifact",
        "bundle_dir",
        "case_name",
        "client_id",
        "scale",
        "clip_ok",
        "relation_ok",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path) -> None:
    total = len(rows)
    honest = sum(1 for row in rows if row["case_name"] == "honest_profile")
    tampered = total - honest
    lines = [
        "# Week 15 ZK Backend Stub Summary",
        "",
        f"- Bundles exported: {total}",
        f"- Honest bundles: {honest}",
        f"- Tampered bundles: {tampered}",
        "",
        "Interpretation:",
        "- These bundles separate public inputs, witness vectors, and verification expectations.",
        "- They are intended as the handoff format for a future real ZK backend integration.",
        "- No real proof was generated in this environment because EZKL is unavailable.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export backend-ready bundles from Week 14 artifacts")
    parser.add_argument("--scale", type=int, default=10000)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 15 - ZK Backend Stub")
    print("=" * 60)

    source_dir = SOURCE_ARTIFACTS_DIR / f"scale_{args.scale}"
    rows: list[dict[str, object]] = []

    for source_path in sorted(source_dir.glob("*.json")):
        output_dir = BUNDLES_DIR / f"scale_{args.scale}" / source_path.stem
        rows.append(export_bundle(source_path, output_dir))

    write_csv(rows, RESULTS_DIR / "bundle_index.csv")
    write_summary(rows, RESULTS_DIR / "summary.md")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
