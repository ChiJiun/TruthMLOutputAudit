"""
Week 13 - Recommended constraint profile experiment.
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
    generate_seeded_noise,
    load_client_datasets,
    load_test_dataset,
    make_noise_seed,
    set_seed,
    subtract_states,
    train_local_model,
)
from week12_canonical_witness.run_canonical_witness_experiment import (
    add_int_states,
    clone_state,
    count_state_parameters,
    quantize_state,
    sum_squared_int_state,
)
from week12_canonical_witness.run_slack_policy_sweep import enforce_target_excess


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
os.chdir(BASE_DIR)


def tamper_noisy_state(state: dict[str, torch.Tensor], delta: int) -> dict[str, torch.Tensor]:
    tampered = clone_state(state)
    first_key = next(iter(tampered))
    tampered[first_key] = tampered[first_key].clone()
    tampered[first_key].view(-1)[0] += delta
    return tampered


def max_abs_difference_int(state_a: dict[str, torch.Tensor], state_b: dict[str, torch.Tensor]) -> int:
    max_diff = 0
    for key in state_a:
        diff = int(torch.max(torch.abs(state_a[key] - state_b[key])).item())
        max_diff = max(max_diff, diff)
    return max_diff


def slack_threshold_from_ppm(clip_rhs: int, slack_ppm: int) -> int:
    return int(round((clip_rhs * slack_ppm) / 1_000_000))


def build_rows(
    scale: int,
    clip_norm: float,
    noise_multiplier: float,
    seed: int,
    local_epochs: int,
    batch_size: int,
    lr: float,
    recommended_slack_ppm: int,
    tamper_target_excess_ppm: int,
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

        q_clipped_honest = quantize_state(clipped_update, scale)
        q_noise = quantize_state(noise_state, scale)
        q_noisy_honest = add_int_states(q_clipped_honest, q_noise)

        clip_rhs = int(round((clip_norm * scale) ** 2))
        slack_abs = slack_threshold_from_ppm(clip_rhs, recommended_slack_ppm)

        base_tamper_step = max(1, scale // 20)
        q_clipped_tampered, _ = enforce_target_excess(
            q_clipped_honest,
            clip_rhs=clip_rhs,
            base_delta=base_tamper_step,
            target_excess_ppm=tamper_target_excess_ppm,
        )
        q_noisy_tampered = tamper_noisy_state(q_noisy_honest, delta=1)

        cases = [
            ("honest_profile", "pass", q_clipped_honest, q_noisy_honest, q_noise),
            ("tampered_clip_profile", "fail", q_clipped_tampered, add_int_states(q_clipped_tampered, q_noise), q_noise),
            ("tampered_noisy_profile", "fail", q_clipped_honest, q_noisy_tampered, q_noise),
        ]

        for case_name, expected_result, q_clipped_case, q_noisy_case, q_noise_case in cases:
            expected_noisy = add_int_states(q_clipped_case, q_noise_case)
            relation_gap = max_abs_difference_int(q_noisy_case, expected_noisy)
            clip_lhs = sum_squared_int_state(q_clipped_case)
            clip_excess = max(0, clip_lhs - clip_rhs)
            clip_ok = clip_excess <= slack_abs
            relation_ok = relation_gap == 0
            overall_pass = clip_ok and relation_ok

            rows.append(
                {
                    "scale": scale,
                    "client_id": client_id,
                    "case_name": case_name,
                    "expected_result": expected_result,
                    "overall_pass": overall_pass,
                    "clip_ok": clip_ok,
                    "relation_ok": relation_ok,
                    "clip_lhs_sum_sq": clip_lhs,
                    "clip_rhs_bound_sq": clip_rhs,
                    "clip_bound_excess": clip_excess,
                    "clip_bound_excess_ppm": round((clip_excess / max(1, clip_rhs)) * 1_000_000, 3),
                    "slack_ppm": recommended_slack_ppm,
                    "slack_abs": slack_abs,
                    "relation_linf_gap": relation_gap,
                    "param_count": count_state_parameters(q_clipped_case),
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
        "overall_pass",
        "clip_ok",
        "relation_ok",
        "clip_lhs_sum_sq",
        "clip_rhs_bound_sq",
        "clip_bound_excess",
        "clip_bound_excess_ppm",
        "slack_ppm",
        "slack_abs",
        "relation_linf_gap",
        "param_count",
        "local_loss",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path, recommended_slack_ppm: int) -> None:
    honest_rows = [row for row in rows if row["expected_result"] == "pass"]
    tampered_rows = [row for row in rows if row["expected_result"] == "fail"]

    honest_accept = sum(1 for row in honest_rows if bool(row["overall_pass"]))
    tampered_reject = sum(1 for row in tampered_rows if not bool(row["overall_pass"]))
    max_honest_excess = max(float(row["clip_bound_excess_ppm"]) for row in honest_rows)
    min_tampered_excess = min(float(row["clip_bound_excess_ppm"]) for row in tampered_rows if "clip_profile" in str(row["case_name"]))
    max_relation_gap = max(int(row["relation_linf_gap"]) for row in tampered_rows)

    lines = [
        "# Week 13 Recommended Constraint Profile Summary",
        "",
        f"- Recommended slack (ppm): {recommended_slack_ppm}",
        f"- Honest profiles accepted: {honest_accept}/{len(honest_rows)}",
        f"- Tampered profiles rejected: {tampered_reject}/{len(tampered_rows)}",
        f"- Max honest clipping excess (ppm): {max_honest_excess}",
        f"- Min tampered clipping excess (ppm): {min_tampered_excess}",
        f"- Max tampered relation gap: {max_relation_gap}",
        "",
        "Interpretation:",
        "- The recommended profile combines canonical quantized witnesses with a fixed clipping slack.",
        "- Honest cases should pass both clipping and additive-noise consistency checks.",
        "- Tampered clipping witnesses and tampered noisy updates should both be rejected under the same profile.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 13 recommended constraint profile")
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--scales", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--recommended-slack-ppm", type=int, default=4201)
    parser.add_argument("--tamper-target-excess-ppm", type=int, default=10000)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 13 - Recommended Constraint Profile")
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
                recommended_slack_ppm=args.recommended_slack_ppm,
                tamper_target_excess_ppm=args.tamper_target_excess_ppm,
            )
        )

    write_csv(rows, RESULTS_DIR / "recommended_constraint_cases.csv")
    write_summary(rows, RESULTS_DIR / "summary.md", args.recommended_slack_ppm)
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
