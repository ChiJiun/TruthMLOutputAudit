"""
Week 14 - Export circuit-friendly artifacts for the recommended constraint profile.
"""
from __future__ import annotations

import argparse
import csv
import json
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
    quantize_state,
    sum_squared_int_state,
)
from week12_canonical_witness.run_slack_policy_sweep import enforce_target_excess
from week13_recommended_constraints.run_recommended_constraint_profile import (
    max_abs_difference_int,
    slack_threshold_from_ppm,
    tamper_noisy_state,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
ARTIFACTS_DIR = RESULTS_DIR / "artifacts"
os.chdir(BASE_DIR)


def flatten_state(state: dict[str, torch.Tensor]) -> list[int]:
    flat: list[int] = []
    for key in state:
        flat.extend(int(v) for v in state[key].view(-1).tolist())
    return flat


def state_shapes(state: dict[str, torch.Tensor]) -> dict[str, list[int]]:
    return {key: list(tensor.shape) for key, tensor in state.items()}


def export_artifact(
    output_path: Path,
    *,
    scale: int,
    client_id: int,
    case_name: str,
    clip_norm: float,
    noise_multiplier: float,
    noise_seed: int,
    slack_ppm: int,
    q_clipped: dict[str, torch.Tensor],
    q_noise: dict[str, torch.Tensor],
    q_noisy: dict[str, torch.Tensor],
) -> dict[str, object]:
    clip_rhs = int(round((clip_norm * scale) ** 2))
    slack_abs = slack_threshold_from_ppm(clip_rhs, slack_ppm)
    clip_lhs = sum_squared_int_state(q_clipped)
    clip_excess = max(0, clip_lhs - clip_rhs)
    expected_noisy = add_int_states(q_clipped, q_noise)
    relation_gap = max_abs_difference_int(q_noisy, expected_noisy)

    artifact = {
        "meta": {
            "scale": scale,
            "client_id": client_id,
            "case_name": case_name,
            "clip_norm": clip_norm,
            "noise_multiplier": noise_multiplier,
            "noise_seed": noise_seed,
            "slack_ppm": slack_ppm,
            "slack_abs": slack_abs,
            "shapes": state_shapes(q_clipped),
        },
        "public_inputs": {
            "clip_rhs_bound_sq": clip_rhs,
            "slack_abs": slack_abs,
            "noise_seed": noise_seed,
            "scale": scale,
        },
        "witness": {
            "q_clipped": flatten_state(q_clipped),
            "q_noise": flatten_state(q_noise),
            "q_noisy": flatten_state(q_noisy),
        },
        "checks": {
            "clip_lhs_sum_sq": clip_lhs,
            "clip_bound_excess": clip_excess,
            "relation_linf_gap": relation_gap,
            "clip_ok": clip_excess <= slack_abs,
            "relation_ok": relation_gap == 0,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact["checks"]


def build_rows(
    scale: int,
    clip_norm: float,
    noise_multiplier: float,
    seed: int,
    local_epochs: int,
    batch_size: int,
    lr: float,
    slack_ppm: int,
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
        q_clipped_tampered, _ = enforce_target_excess(
            q_clipped_honest,
            clip_rhs=clip_rhs,
            base_delta=max(1, scale // 20),
            target_excess_ppm=tamper_target_excess_ppm,
        )
        q_noisy_tampered = tamper_noisy_state(q_noisy_honest, delta=1)

        cases = [
            ("honest_profile", "pass", q_clipped_honest, q_noise, q_noisy_honest),
            ("tampered_clip_profile", "fail", q_clipped_tampered, q_noise, add_int_states(q_clipped_tampered, q_noise)),
            ("tampered_noisy_profile", "fail", q_clipped_honest, q_noise, q_noisy_tampered),
        ]

        for case_name, expected_result, q_clipped_case, q_noise_case, q_noisy_case in cases:
            checks = export_artifact(
                ARTIFACTS_DIR / f"scale_{scale}" / f"client_{client_id}_{case_name}.json",
                scale=scale,
                client_id=client_id,
                case_name=case_name,
                clip_norm=clip_norm,
                noise_multiplier=noise_multiplier,
                noise_seed=noise_seed,
                slack_ppm=slack_ppm,
                q_clipped=q_clipped_case,
                q_noise=q_noise_case,
                q_noisy=q_noisy_case,
            )
            rows.append(
                {
                    "scale": scale,
                    "client_id": client_id,
                    "case_name": case_name,
                    "expected_result": expected_result,
                    "clip_ok": checks["clip_ok"],
                    "relation_ok": checks["relation_ok"],
                    "clip_bound_excess": checks["clip_bound_excess"],
                    "relation_linf_gap": checks["relation_linf_gap"],
                    "artifact_path": str((ARTIFACTS_DIR / f"scale_{scale}" / f"client_{client_id}_{case_name}.json").relative_to(BASE_DIR)),
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
        "clip_ok",
        "relation_ok",
        "clip_bound_excess",
        "relation_linf_gap",
        "artifact_path",
        "local_loss",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path, scale: int, slack_ppm: int) -> None:
    honest_rows = [row for row in rows if row["expected_result"] == "pass"]
    tampered_rows = [row for row in rows if row["expected_result"] == "fail"]
    honest_pass = sum(1 for row in honest_rows if row["clip_ok"] and row["relation_ok"])
    tampered_reject = sum(1 for row in tampered_rows if not (row["clip_ok"] and row["relation_ok"]))
    lines = [
        "# Week 14 Constraint Artifact Export Summary",
        "",
        f"- Export scale: {scale}",
        f"- Slack ppm: {slack_ppm}",
        f"- Honest artifacts passing checks: {honest_pass}/{len(honest_rows)}",
        f"- Tampered artifacts rejected: {tampered_reject}/{len(tampered_rows)}",
        "",
        "Interpretation:",
        "- These JSON artifacts fix the public inputs and witness layout for the recommended constraint profile.",
        "- They are intended as circuit-facing inputs for a future ZK implementation step.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export circuit-friendly artifacts")
    parser.add_argument("--scale", type=int, default=10000)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--slack-ppm", type=int, default=4201)
    parser.add_argument("--tamper-target-excess-ppm", type=int, default=10000)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 14 - Constraint Artifact Export")
    print("=" * 60)

    rows = build_rows(
        scale=args.scale,
        clip_norm=args.clip_norm,
        noise_multiplier=args.noise_multiplier,
        seed=args.seed,
        local_epochs=args.local_epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        slack_ppm=args.slack_ppm,
        tamper_target_excess_ppm=args.tamper_target_excess_ppm,
    )
    write_csv(rows, RESULTS_DIR / "artifact_index.csv")
    write_summary(rows, RESULTS_DIR / "summary.md", args.scale, args.slack_ppm)
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
