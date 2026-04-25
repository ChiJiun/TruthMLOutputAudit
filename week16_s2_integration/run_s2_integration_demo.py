"""
Week 16 - End-to-end S2 integration demo using the recommended constraint profile.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ARTIFACTS_DIR = ROOT_DIR / "week14_constraint_artifacts" / "results" / "artifacts"
RESULTS_DIR = BASE_DIR / "results"
os.chdir(BASE_DIR)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_round_rows(scale: int, tampered_client: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    base_dir = ARTIFACTS_DIR / f"scale_{scale}"

    for client_id in range(3):
        if client_id == tampered_client:
            selected_case = "tampered_noisy_profile"
        else:
            selected_case = "honest_profile"

        artifact = load_json(base_dir / f"client_{client_id}_{selected_case}.json")
        checks = artifact["checks"]
        accepted = bool(checks["clip_ok"] and checks["relation_ok"])

        rows.append(
            {
                "client_id": client_id,
                "selected_case": selected_case,
                "accepted_by_s2": accepted,
                "clip_ok": checks["clip_ok"],
                "relation_ok": checks["relation_ok"],
                "clip_bound_excess": checks["clip_bound_excess"],
                "relation_linf_gap": checks["relation_linf_gap"],
            }
        )
    return rows


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "client_id",
        "selected_case",
        "accepted_by_s2",
        "clip_ok",
        "relation_ok",
        "clip_bound_excess",
        "relation_linf_gap",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path, scale: int, tampered_client: int) -> None:
    accepted = sum(1 for row in rows if row["accepted_by_s2"])
    rejected = len(rows) - accepted
    tampered_row = next(row for row in rows if row["client_id"] == tampered_client)
    lines = [
        "# Week 16 S2 Integration Summary",
        "",
        f"- Scale: {scale}",
        f"- Tampered client: {tampered_client}",
        f"- Accepted updates under S2 profile: {accepted}/{len(rows)}",
        f"- Rejected updates under S2 profile: {rejected}/{len(rows)}",
        f"- Tampered client accepted: {tampered_row['accepted_by_s2']}",
        "",
        "Interpretation:",
        "- In this demo round, honest clients remain admissible under the recommended constraint profile.",
        "- The tampered client is rejected before aggregation because its recommended-profile checks fail.",
        "- This is an S2 integration prototype using circuit-facing artifacts, not a real proof system yet.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 16 S2 integration demo")
    parser.add_argument("--scale", type=int, default=10000)
    parser.add_argument("--tampered-client", type=int, default=1)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 16 - S2 Integration Demo")
    print("=" * 60)

    rows = build_round_rows(scale=args.scale, tampered_client=args.tampered_client)
    write_csv(rows, RESULTS_DIR / "s2_round_decisions.csv")
    write_summary(rows, RESULTS_DIR / "summary.md", scale=args.scale, tampered_client=args.tampered_client)
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
