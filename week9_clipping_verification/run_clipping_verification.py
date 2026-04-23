"""
Week 9 - Prototype verification for the DP clipping constraint.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from week7_dp_updater.dp_fedavg_core import (
    SimpleLinearModel,
    clip_update,
    load_client_datasets,
    load_test_dataset,
    set_seed,
    state_l2_norm,
    subtract_states,
    train_local_model,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
os.chdir(BASE_DIR)


def clone_state(state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: tensor.clone() for key, tensor in state.items()}


def scale_state(state: dict[str, torch.Tensor], factor: float) -> dict[str, torch.Tensor]:
    return {key: tensor * factor for key, tensor in state.items()}


def max_abs_difference(state_a: dict[str, torch.Tensor], state_b: dict[str, torch.Tensor]) -> float:
    max_diff = 0.0
    for key in state_a:
        diff = torch.max(torch.abs(state_a[key] - state_b[key])).item()
        max_diff = max(max_diff, float(diff))
    return max_diff


def build_expected_clipped_state(
    raw_update: dict[str, torch.Tensor],
    clip_norm: float,
    tolerance: float,
) -> tuple[dict[str, torch.Tensor], float]:
    raw_norm = state_l2_norm(raw_update)
    if raw_norm <= clip_norm + tolerance or raw_norm == 0.0:
        return clone_state(raw_update), raw_norm

    scale = clip_norm / raw_norm
    return scale_state(raw_update, scale), raw_norm


def make_bound_fail_case(clipped_update: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return scale_state(clipped_update, 1.25)


def make_relation_fail_case(clipped_update: dict[str, torch.Tensor], clip_norm: float) -> dict[str, torch.Tensor]:
    tampered = clone_state(clipped_update)
    first_key = next(iter(tampered))
    tampered[first_key] = tampered[first_key].clone()
    tampered[first_key].view(-1)[0] += 0.05

    tampered_norm = state_l2_norm(tampered)
    if tampered_norm > clip_norm and tampered_norm > 0.0:
        tampered = scale_state(tampered, (clip_norm * 0.95) / tampered_norm)
    return tampered


def verify_clipped_update(
    raw_update: dict[str, torch.Tensor],
    claimed_clipped_update: dict[str, torch.Tensor],
    clip_norm: float,
    tolerance: float,
) -> dict[str, object]:
    expected_state, raw_norm = build_expected_clipped_state(raw_update, clip_norm, tolerance)
    claimed_norm = state_l2_norm(claimed_clipped_update)
    relation_max_abs_error = max_abs_difference(expected_state, claimed_clipped_update)

    bound_ok = claimed_norm <= clip_norm + tolerance
    relation_ok = relation_max_abs_error <= tolerance
    passed = bound_ok and relation_ok

    return {
        "raw_update_norm": raw_norm,
        "claimed_update_norm": claimed_norm,
        "bound_ok": bound_ok,
        "relation_ok": relation_ok,
        "relation_max_abs_error": relation_max_abs_error,
        "passed": passed,
    }


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "client_id",
        "case_name",
        "expected_result",
        "verification_passed",
        "raw_update_norm",
        "claimed_update_norm",
        "clip_norm",
        "bound_ok",
        "relation_ok",
        "relation_max_abs_error",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path, clip_norm: float) -> None:
    honest_rows = [row for row in rows if row["expected_result"] == "pass"]
    tampered_rows = [row for row in rows if row["expected_result"] == "fail"]

    honest_passes = sum(1 for row in honest_rows if row["verification_passed"])
    tampered_rejected = sum(1 for row in tampered_rows if not row["verification_passed"])

    lines = [
        "# Week 9 Clipping Verification Summary",
        "",
        f"- Clip norm: {clip_norm}",
        f"- Honest cases accepted: {honest_passes}/{len(honest_rows)}",
        f"- Tampered cases rejected: {tampered_rejected}/{len(tampered_rows)}",
        "",
        "Interpretation:",
        "- Honest clipped updates should satisfy both the norm bound and the clipping relation.",
        "- Tampered updates may either exceed the bound or stay within the bound while violating the clipping relation.",
        "",
        "Note:",
        "- This is a pre-ZK prototype implemented as direct Python verification.",
        "- The next stage is to map the same logic into a zero-knowledge-verifiable constraint system.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 9 clipping verification prototype")
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tolerance", type=float, default=1e-5)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 9 - Clipping Verification Prototype")
    print("=" * 60)

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    clients = load_client_datasets()
    x_test, _ = load_test_dataset()
    global_model = SimpleLinearModel(input_dim=x_test.shape[1]).to(device)
    global_state = {key: tensor.detach().cpu().clone() for key, tensor in global_model.state_dict().items()}

    rows: list[dict[str, object]] = []

    for client_id, (x_client, y_client) in enumerate(clients):
        local_state, avg_loss = train_local_model(
            global_model=global_model,
            x_client=x_client,
            y_client=y_client,
            device=device,
            epochs=args.local_epochs,
            batch_size=args.batch_size,
            lr=args.lr,
        )
        raw_update = subtract_states(local_state, global_state)
        clipped_update, raw_norm, _ = clip_update(raw_update, args.clip_norm)

        cases = [
            ("honest_clipped", "pass", clipped_update),
            ("tampered_bound_fail", "fail", make_bound_fail_case(clipped_update)),
            ("tampered_relation_fail", "fail", make_relation_fail_case(clipped_update, args.clip_norm)),
        ]

        print(f"Client {client_id}: samples={len(y_client)}, local_loss={avg_loss:.4f}, raw_update_norm={raw_norm:.6f}")

        for case_name, expected_result, claimed_update in cases:
            verdict = verify_clipped_update(
                raw_update=raw_update,
                claimed_clipped_update=claimed_update,
                clip_norm=args.clip_norm,
                tolerance=args.tolerance,
            )
            rows.append(
                {
                    "client_id": client_id,
                    "case_name": case_name,
                    "expected_result": expected_result,
                    "verification_passed": verdict["passed"],
                    "raw_update_norm": round(float(verdict["raw_update_norm"]), 6),
                    "claimed_update_norm": round(float(verdict["claimed_update_norm"]), 6),
                    "clip_norm": args.clip_norm,
                    "bound_ok": verdict["bound_ok"],
                    "relation_ok": verdict["relation_ok"],
                    "relation_max_abs_error": round(float(verdict["relation_max_abs_error"]), 8),
                }
            )

    write_csv(rows, RESULTS_DIR / "clipping_verification_cases.csv")
    write_summary(rows, RESULTS_DIR / "summary.md", args.clip_norm)

    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
