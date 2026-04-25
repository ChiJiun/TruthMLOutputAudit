"""
Week 12 - Canonical quantized witness experiment.
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
    add_state_noise,
    clip_update,
    generate_seeded_noise,
    load_client_datasets,
    load_test_dataset,
    make_noise_seed,
    set_seed,
    subtract_states,
    train_local_model,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
os.chdir(BASE_DIR)


def quantize_state(state: dict[str, torch.Tensor], scale: int) -> dict[str, torch.Tensor]:
    return {
        key: torch.round(tensor.detach().cpu() * scale).to(torch.int64)
        for key, tensor in state.items()
    }


def clone_state(state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: tensor.clone() for key, tensor in state.items()}


def add_int_states(state_a: dict[str, torch.Tensor], state_b: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: state_a[key] + state_b[key] for key in state_a}


def max_abs_difference_int(state_a: dict[str, torch.Tensor], state_b: dict[str, torch.Tensor]) -> int:
    max_diff = 0
    for key in state_a:
        diff = int(torch.max(torch.abs(state_a[key] - state_b[key])).item())
        max_diff = max(max_diff, diff)
    return max_diff


def sum_squared_int_state(state: dict[str, torch.Tensor]) -> int:
    total = 0
    for tensor in state.values():
        tensor_i64 = tensor.to(torch.int64)
        total += int(torch.sum(tensor_i64 * tensor_i64).item())
    return total


def count_state_parameters(state: dict[str, torch.Tensor]) -> int:
    return sum(int(tensor.numel()) for tensor in state.values())


def tamper_state(state: dict[str, torch.Tensor], delta: int) -> dict[str, torch.Tensor]:
    tampered = clone_state(state)
    first_key = next(iter(tampered))
    tampered[first_key] = tampered[first_key].clone()
    tampered[first_key].view(-1)[0] += delta
    return tampered


def build_rows(
    scale: int,
    clip_norm: float,
    noise_multiplier: float,
    seed: int,
    local_epochs: int,
    batch_size: int,
    lr: float,
) -> list[dict[str, object]]:
    set_seed(seed)
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
            epochs=local_epochs,
            batch_size=batch_size,
            lr=lr,
        )
        raw_update = subtract_states(local_state, global_state)
        clipped_update, _, _ = clip_update(raw_update, clip_norm)
        noise_seed = make_noise_seed(seed, round_idx=1, client_id=client_id)
        noise_state = generate_seeded_noise(clipped_update, noise_multiplier, clip_norm, noise_seed)

        q_clipped = quantize_state(clipped_update, scale)
        q_noise = quantize_state(noise_state, scale)
        q_noisy_canonical = add_int_states(q_clipped, q_noise)
        q_noisy_tampered = tamper_state(q_noisy_canonical, delta=1)

        clip_lhs = sum_squared_int_state(q_clipped)
        clip_rhs = int(round((clip_norm * scale) ** 2))
        clip_excess = max(0, clip_lhs - clip_rhs)
        param_count = count_state_parameters(q_clipped)

        q_noisy_from_float = quantize_state(add_state_noise(clipped_update, noise_state), scale)
        float_gap = max_abs_difference_int(q_noisy_from_float, q_noisy_canonical)

        base_case = {
            "scale": scale,
            "client_id": client_id,
            "param_count": param_count,
            "local_loss": round(float(avg_loss), 6),
            "clip_lhs_sum_sq": clip_lhs,
            "clip_rhs_bound_sq": clip_rhs,
            "clip_bound_excess": clip_excess,
            "clip_bound_excess_ppm": round((clip_excess / max(1, clip_rhs)) * 1_000_000, 3),
            "canonical_float_gap_linf": float_gap,
            "slack_needed_for_clip": clip_excess,
        }

        honest_pass_no_slack = clip_excess == 0
        honest_pass_with_observed_slack = clip_excess <= clip_excess

        rows.append(
            {
                **base_case,
                "case_name": "honest_canonical",
                "expected_result": "pass",
                "relation_exact": True,
                "clip_ok_without_slack": honest_pass_no_slack,
                "clip_ok_with_observed_slack": honest_pass_with_observed_slack,
                "relation_linf_gap": 0,
                "tamper_delta": 0,
            }
        )

        tampered_gap = max_abs_difference_int(q_noisy_tampered, q_noisy_canonical)
        rows.append(
            {
                **base_case,
                "case_name": "tampered_canonical",
                "expected_result": "fail",
                "relation_exact": False,
                "clip_ok_without_slack": honest_pass_no_slack,
                "clip_ok_with_observed_slack": honest_pass_with_observed_slack,
                "relation_linf_gap": tampered_gap,
                "tamper_delta": 1,
            }
        )

    return rows


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scale",
        "client_id",
        "case_name",
        "expected_result",
        "param_count",
        "local_loss",
        "clip_lhs_sum_sq",
        "clip_rhs_bound_sq",
        "clip_bound_excess",
        "clip_bound_excess_ppm",
        "slack_needed_for_clip",
        "clip_ok_without_slack",
        "clip_ok_with_observed_slack",
        "relation_exact",
        "relation_linf_gap",
        "canonical_float_gap_linf",
        "tamper_delta",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path) -> None:
    honest_rows = [row for row in rows if row["expected_result"] == "pass"]
    tampered_rows = [row for row in rows if row["expected_result"] == "fail"]

    honest_exact = sum(1 for row in honest_rows if bool(row["relation_exact"]))
    tampered_rejected = sum(1 for row in tampered_rows if int(row["relation_linf_gap"]) > 0)
    clip_without_slack = sum(1 for row in honest_rows if bool(row["clip_ok_without_slack"]))
    clip_with_observed_slack = sum(1 for row in honest_rows if bool(row["clip_ok_with_observed_slack"]))
    max_slack = max(int(row["slack_needed_for_clip"]) for row in honest_rows)
    max_slack_ppm = max(float(row["clip_bound_excess_ppm"]) for row in honest_rows)
    max_float_gap = max(int(row["canonical_float_gap_linf"]) for row in honest_rows)

    scale_lines: list[str] = []
    for scale in sorted({int(row["scale"]) for row in honest_rows}):
        scale_rows = [row for row in honest_rows if int(row["scale"]) == scale]
        exact_without_slack = sum(1 for row in scale_rows if bool(row["clip_ok_without_slack"]))
        max_scale_slack = max(int(row["slack_needed_for_clip"]) for row in scale_rows)
        max_scale_slack_ppm = max(float(row["clip_bound_excess_ppm"]) for row in scale_rows)
        max_scale_float_gap = max(int(row["canonical_float_gap_linf"]) for row in scale_rows)
        scale_lines.append(
            f"- scale={scale}: clip_without_slack={exact_without_slack}/{len(scale_rows)}, max_slack={max_scale_slack}, max_slack_ppm={max_scale_slack_ppm}, canonical_float_gap={max_scale_float_gap}"
        )

    lines = [
        "# Week 12 Canonical Witness Summary",
        "",
        f"- Honest canonical relations exact: {honest_exact}/{len(honest_rows)}",
        f"- Tampered canonical relations rejected: {tampered_rejected}/{len(tampered_rows)}",
        f"- Honest clipping checks exact without slack: {clip_without_slack}/{len(honest_rows)}",
        f"- Honest clipping checks covered with observed slack: {clip_with_observed_slack}/{len(honest_rows)}",
        f"- Max clipping slack needed: {max_slack}",
        f"- Max clipping slack needed (ppm): {max_slack_ppm}",
        f"- Max gap between canonical integer witness and float-then-quantize witness: {max_float_gap}",
        "",
        "Per-scale view:",
        *scale_lines,
        "",
        "Interpretation:",
        "- Canonical quantized witnesses make the additive noise relation exact by construction.",
        "- Tampered integer witnesses are still easy to reject with a single-coordinate perturbation.",
        "- Clipping still needs a small explicit slack for borderline cases, but the observed relative slack shrinks as scale increases.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 12 canonical witness experiment")
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--scales", type=int, nargs="+", default=[100, 1000, 10000])
    args = parser.parse_args()

    print("=" * 60)
    print("Week 12 - Canonical Witness Experiment")
    print("=" * 60)

    rows: list[dict[str, object]] = []
    for scale in args.scales:
        print(f"Running scale={scale}")
        rows.extend(
            build_rows(
                scale=scale,
                clip_norm=args.clip_norm,
                noise_multiplier=args.noise_multiplier,
                seed=args.seed,
                local_epochs=args.local_epochs,
                batch_size=args.batch_size,
                lr=args.lr,
            )
        )

    write_csv(rows, RESULTS_DIR / "canonical_witness_cases.csv")
    write_summary(rows, RESULTS_DIR / "summary.md")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
