"""
Week 11 - Quantized constraint checks for clipping and seed-based noise.
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


def tamper_quantized_state(state: dict[str, torch.Tensor], delta: int) -> dict[str, torch.Tensor]:
    tampered = {key: tensor.clone() for key, tensor in state.items()}
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
        noisy_update = add_state_noise(clipped_update, noise_state)

        q_clipped = quantize_state(clipped_update, scale)
        q_noise = quantize_state(noise_state, scale)
        q_noisy_direct = quantize_state(noisy_update, scale)
        q_noisy_composed = add_state_noise(q_clipped, q_noise)
        q_noisy_tampered = tamper_quantized_state(q_noisy_composed, delta=1)

        clip_lhs = sum_squared_int_state(q_clipped)
        clip_rhs = int(round((clip_norm * scale) ** 2))
        clip_excess = max(0, clip_lhs - clip_rhs)
        relation_gap = max_abs_difference_int(q_noisy_direct, q_noisy_composed)
        tampered_gap = max_abs_difference_int(q_noisy_tampered, q_noisy_composed)
        param_count = count_state_parameters(q_clipped)

        cases = [
            ("honest_quantized_relation", "pass", q_noisy_composed, relation_gap),
            ("tampered_quantized_relation", "fail", q_noisy_tampered, tampered_gap),
        ]

        for case_name, expected_result, claimed_noisy_quantized, relation_gap_value in cases:
            rows.append(
                {
                    "scale": scale,
                    "client_id": client_id,
                    "case_name": case_name,
                    "expected_result": expected_result,
                    "clip_bound_ok": clip_lhs <= clip_rhs,
                    "clip_lhs_sum_sq": clip_lhs,
                    "clip_rhs_bound_sq": clip_rhs,
                    "clip_bound_excess": clip_excess,
                    "clip_bound_excess_ppm": round((clip_excess / max(1, clip_rhs)) * 1_000_000, 3),
                    "quantized_relation_ok": relation_gap_value == 0,
                    "relation_linf_gap": relation_gap_value,
                    "float_vs_quantized_gap": relation_gap,
                    "param_count": param_count,
                    "q_clipped_linf": int(torch.max(torch.abs(torch.cat([t.view(-1) for t in q_clipped.values()]))).item()),
                    "q_noise_linf": int(torch.max(torch.abs(torch.cat([t.view(-1) for t in q_noise.values()]))).item()),
                    "q_noisy_linf": int(torch.max(torch.abs(torch.cat([t.view(-1) for t in claimed_noisy_quantized.values()]))).item()),
                    "local_loss": round(float(avg_loss), 6),
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
        "clip_bound_ok",
        "clip_lhs_sum_sq",
        "clip_rhs_bound_sq",
        "clip_bound_excess",
        "clip_bound_excess_ppm",
        "quantized_relation_ok",
        "relation_linf_gap",
        "float_vs_quantized_gap",
        "param_count",
        "q_clipped_linf",
        "q_noise_linf",
        "q_noisy_linf",
        "local_loss",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path) -> None:
    honest_rows = [row for row in rows if row["expected_result"] == "pass"]
    tampered_rows = [row for row in rows if row["expected_result"] == "fail"]

    clip_ok_count = sum(1 for row in honest_rows if bool(row["clip_bound_ok"]))
    honest_exact = sum(1 for row in honest_rows if bool(row["quantized_relation_ok"]))
    tampered_rejected = sum(1 for row in tampered_rows if not bool(row["quantized_relation_ok"]))
    max_float_gap = max(int(row["float_vs_quantized_gap"]) for row in honest_rows)
    max_clip_excess = max(int(row["clip_bound_excess"]) for row in honest_rows)
    max_clip_excess_ppm = max(float(row["clip_bound_excess_ppm"]) for row in honest_rows)

    scale_lines: list[str] = []
    for scale in sorted({int(row["scale"]) for row in honest_rows}):
        scale_rows = [row for row in honest_rows if int(row["scale"]) == scale]
        exact_clip = sum(1 for row in scale_rows if bool(row["clip_bound_ok"]))
        max_excess = max(int(row["clip_bound_excess"]) for row in scale_rows)
        max_excess_ppm = max(float(row["clip_bound_excess_ppm"]) for row in scale_rows)
        scale_lines.append(
            f"- scale={scale}: exact_clip={exact_clip}/{len(scale_rows)}, max_excess={max_excess}, max_excess_ppm={max_excess_ppm}"
        )

    lines = [
        "# Week 11 Quantized Constraint Summary",
        "",
        f"- Scales tested: {sorted({int(row['scale']) for row in rows})}",
        f"- Honest integer clipping bounds exact: {clip_ok_count}/{len(honest_rows)}",
        f"- Honest quantized noise relations exact: {honest_exact}/{len(honest_rows)}",
        f"- Tampered quantized relations rejected: {tampered_rejected}/{len(tampered_rows)}",
        f"- Max float-vs-quantized relation gap: {max_float_gap}",
        f"- Max clipping-bound excess after quantization: {max_clip_excess}",
        f"- Max clipping-bound excess after quantization (ppm): {max_clip_excess_ppm}",
        "",
        "Per-scale view:",
        *scale_lines,
        "",
        "Interpretation:",
        "- A direct integer sum-of-squares bound is close to the float clipping rule, but borderline clipped updates can cross the bound after rounding.",
        "- The noisy-update relation may lose exact equality after independent rounding of clipped update and noise.",
        "- If either gap is non-zero, the future circuit design must define a canonical quantization rule and possibly an explicit slack policy.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 11 quantized constraint checks")
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--scales", type=int, nargs="+", default=[100, 1000, 10000])
    args = parser.parse_args()

    print("=" * 60)
    print("Week 11 - Quantized Constraint Checks")
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

    write_csv(rows, RESULTS_DIR / "quantized_constraint_cases.csv")
    write_summary(rows, RESULTS_DIR / "summary.md")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
