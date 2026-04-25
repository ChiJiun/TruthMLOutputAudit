"""
Week 12 - Slack policy sweep for canonical quantized witnesses.
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


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
os.chdir(BASE_DIR)


def tamper_clipped_state(state: dict[str, torch.Tensor], delta: int) -> dict[str, torch.Tensor]:
    tampered = clone_state(state)
    best_key: str | None = None
    best_index = 0
    best_abs = -1

    for key, tensor in tampered.items():
        flat = tensor.view(-1)
        if flat.numel() == 0:
            continue
        abs_vals = torch.abs(flat)
        local_abs, local_idx = torch.max(abs_vals, dim=0)
        if int(local_abs.item()) > best_abs:
            best_abs = int(local_abs.item())
            best_key = key
            best_index = int(local_idx.item())

    if best_key is None:
        return tampered

    tampered[best_key] = tampered[best_key].clone()
    flat = tampered[best_key].view(-1)
    sign = 1 if int(flat[best_index].item()) >= 0 else -1
    flat[best_index] += sign * delta
    return tampered


def enforce_target_excess(
    state: dict[str, torch.Tensor],
    clip_rhs: int,
    base_delta: int,
    target_excess_ppm: int,
) -> tuple[dict[str, torch.Tensor], int]:
    target_excess_abs = max(1, int(round((clip_rhs * target_excess_ppm) / 1_000_000)))
    current = clone_state(state)
    applied_delta = 0

    for _ in range(1000):
        clip_lhs = sum_squared_int_state(current)
        if clip_lhs - clip_rhs >= target_excess_abs:
            return current, applied_delta
        current = tamper_clipped_state(current, base_delta)
        applied_delta += base_delta

    return current, applied_delta


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
    slack_ppms: list[int],
    tamper_delta_multiplier: int,
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

        q_clipped = quantize_state(clipped_update, scale)
        q_noise = quantize_state(noise_state, scale)

        tamper_step = max(1, tamper_delta_multiplier * scale // 100)
        clip_rhs = int(round((clip_norm * scale) ** 2))
        q_clipped_tampered, tamper_delta = enforce_target_excess(
            q_clipped,
            clip_rhs=clip_rhs,
            base_delta=tamper_step,
            target_excess_ppm=tamper_target_excess_ppm,
        )

        cases = [
            ("honest_clip", "pass", q_clipped),
            ("tampered_clip", "fail", q_clipped_tampered),
        ]

        for case_name, expected_result, q_clipped_case in cases:
            q_noisy_case = add_int_states(q_clipped_case, q_noise)
            clip_lhs = sum_squared_int_state(q_clipped_case)
            clip_excess = max(0, clip_lhs - clip_rhs)
            relation_exact = True

            for slack_ppm in slack_ppms:
                slack_abs = slack_threshold_from_ppm(clip_rhs, slack_ppm)
                clip_ok = clip_excess <= slack_abs
                rows.append(
                    {
                        "scale": scale,
                        "client_id": client_id,
                        "case_name": case_name,
                        "expected_result": expected_result,
                        "slack_ppm": slack_ppm,
                        "slack_abs": slack_abs,
                        "clip_bound_ok": clip_ok,
                        "clip_lhs_sum_sq": clip_lhs,
                        "clip_rhs_bound_sq": clip_rhs,
                        "clip_bound_excess": clip_excess,
                        "clip_bound_excess_ppm": round((clip_excess / max(1, clip_rhs)) * 1_000_000, 3),
                        "relation_exact": relation_exact,
                        "tamper_delta": tamper_delta if expected_result == "fail" else 0,
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
        "slack_ppm",
        "slack_abs",
        "clip_bound_ok",
        "clip_lhs_sum_sq",
        "clip_rhs_bound_sq",
        "clip_bound_excess",
        "clip_bound_excess_ppm",
        "relation_exact",
        "tamper_delta",
        "param_count",
        "local_loss",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path) -> None:
    honest_all = [row for row in rows if row["expected_result"] == "pass"]
    tampered_all = [row for row in rows if row["expected_result"] == "fail"]
    global_max_honest_excess = max(float(row["clip_bound_excess_ppm"]) for row in honest_all)
    global_min_tampered_excess = min(float(row["clip_bound_excess_ppm"]) for row in tampered_all)
    recommended_slack_ppm = int(global_max_honest_excess) + 1

    slack_lines: list[str] = []
    for slack_ppm in sorted({int(row["slack_ppm"]) for row in rows}):
        slack_rows = [row for row in rows if int(row["slack_ppm"]) == slack_ppm]
        honest_rows = [row for row in slack_rows if row["expected_result"] == "pass"]
        tampered_rows = [row for row in slack_rows if row["expected_result"] == "fail"]
        honest_accept = sum(1 for row in honest_rows if bool(row["clip_bound_ok"]))
        tampered_reject = sum(1 for row in tampered_rows if not bool(row["clip_bound_ok"]))
        max_honest_excess = max(float(row["clip_bound_excess_ppm"]) for row in honest_rows)
        min_tampered_excess = min(float(row["clip_bound_excess_ppm"]) for row in tampered_rows)
        slack_lines.append(
            f"- slack_ppm={slack_ppm}: honest_accept={honest_accept}/{len(honest_rows)}, tampered_reject={tampered_reject}/{len(tampered_rows)}, max_honest_excess_ppm={max_honest_excess}, min_tampered_excess_ppm={min_tampered_excess}"
        )

    lines = [
        "# Week 12 Slack Policy Sweep Summary",
        "",
        f"- Max honest excess observed (ppm): {global_max_honest_excess}",
        f"- Min tampered excess observed (ppm): {global_min_tampered_excess}",
        f"- Feasible slack interval (ppm): ({global_max_honest_excess}, {global_min_tampered_excess})",
        f"- Simple candidate slack (ppm): {recommended_slack_ppm}",
        "",
        "Policy comparison:",
        *slack_lines,
        "",
        "Interpretation:",
        "- A usable slack policy should accept all honest clipped witnesses while still rejecting intentionally enlarged clipped updates.",
        "- If the gap between max honest excess and min tampered excess is wide enough, the future circuit can encode a fixed slack threshold with low ambiguity.",
        "- In this run, a slack slightly above the max honest excess is enough to preserve honest cases while keeping a large margin from the tampered cases.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 12 slack policy sweep")
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--scales", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--slack-ppms", type=int, nargs="+", default=[0, 100, 500, 1000, 5000, 20000])
    parser.add_argument("--tamper-delta-multiplier", type=int, default=5)
    parser.add_argument("--tamper-target-excess-ppm", type=int, default=10000)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 12 - Slack Policy Sweep")
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
                slack_ppms=args.slack_ppms,
                tamper_delta_multiplier=args.tamper_delta_multiplier,
                tamper_target_excess_ppm=args.tamper_target_excess_ppm,
            )
        )

    write_csv(rows, RESULTS_DIR / "slack_policy_sweep.csv")
    write_summary(rows, RESULTS_DIR / "slack_policy_summary.md")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
