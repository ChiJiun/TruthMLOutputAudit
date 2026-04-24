"""
Week 10 - Prototype verification for seed-based noise generation and application.
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


def max_abs_difference(state_a: dict[str, torch.Tensor], state_b: dict[str, torch.Tensor]) -> float:
    max_diff = 0.0
    for key in state_a:
        diff = torch.max(torch.abs(state_a[key] - state_b[key])).item()
        max_diff = max(max_diff, float(diff))
    return max_diff


def build_expected_noise_and_update(
    clipped_update: dict[str, torch.Tensor],
    noise_multiplier: float,
    clip_norm: float,
    seed: int,
) -> tuple[dict[str, torch.Tensor], dict[str, torch.Tensor]]:
    expected_noise = generate_seeded_noise(clipped_update, noise_multiplier, clip_norm, seed)
    expected_noisy_update = add_state_noise(clipped_update, expected_noise)
    return expected_noise, expected_noisy_update


def make_noise_tamper_case(noise_state: dict[str, torch.Tensor], clip_norm: float) -> dict[str, torch.Tensor]:
    tampered = clone_state(noise_state)
    first_key = next(iter(tampered))
    tampered[first_key] = tampered[first_key].clone()
    tampered[first_key].view(-1)[0] += 0.05 * clip_norm
    return tampered


def make_noisy_update_tamper_case(noisy_update: dict[str, torch.Tensor], clip_norm: float) -> dict[str, torch.Tensor]:
    tampered = clone_state(noisy_update)
    first_key = next(iter(tampered))
    tampered[first_key] = tampered[first_key].clone()
    tampered[first_key].view(-1)[0] -= 0.04 * clip_norm
    return tampered


def verify_noise_application(
    clipped_update: dict[str, torch.Tensor],
    claimed_noise: dict[str, torch.Tensor],
    claimed_noisy_update: dict[str, torch.Tensor],
    noise_multiplier: float,
    clip_norm: float,
    seed: int,
    tolerance: float,
) -> dict[str, object]:
    expected_noise, expected_noisy_update = build_expected_noise_and_update(
        clipped_update=clipped_update,
        noise_multiplier=noise_multiplier,
        clip_norm=clip_norm,
        seed=seed,
    )

    noise_error = max_abs_difference(expected_noise, claimed_noise)
    update_relation_error = max_abs_difference(add_state_noise(clipped_update, claimed_noise), claimed_noisy_update)
    full_update_error = max_abs_difference(expected_noisy_update, claimed_noisy_update)

    seed_noise_ok = noise_error <= tolerance
    update_relation_ok = update_relation_error <= tolerance
    full_update_ok = full_update_error <= tolerance
    passed = seed_noise_ok and update_relation_ok and full_update_ok

    claimed_noise_norm = state_l2_norm(claimed_noise)
    claimed_noisy_update_norm = state_l2_norm(claimed_noisy_update)
    clipped_update_norm = state_l2_norm(clipped_update)

    return {
        "clipped_update_norm": clipped_update_norm,
        "claimed_noise_norm": claimed_noise_norm,
        "claimed_noisy_update_norm": claimed_noisy_update_norm,
        "seed_noise_ok": seed_noise_ok,
        "update_relation_ok": update_relation_ok,
        "full_update_ok": full_update_ok,
        "noise_max_abs_error": noise_error,
        "update_relation_max_abs_error": update_relation_error,
        "full_update_max_abs_error": full_update_error,
        "passed": passed,
    }


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "client_id",
        "seed",
        "case_name",
        "expected_result",
        "verification_passed",
        "clipped_update_norm",
        "claimed_noise_norm",
        "claimed_noisy_update_norm",
        "noise_multiplier",
        "clip_norm",
        "seed_noise_ok",
        "update_relation_ok",
        "full_update_ok",
        "noise_max_abs_error",
        "update_relation_max_abs_error",
        "full_update_max_abs_error",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(
    rows: list[dict[str, object]],
    output_path: Path,
    clip_norm: float,
    noise_multiplier: float,
) -> None:
    honest_rows = [row for row in rows if row["expected_result"] == "pass"]
    tampered_rows = [row for row in rows if row["expected_result"] == "fail"]

    honest_passes = sum(1 for row in honest_rows if row["verification_passed"])
    tampered_rejected = sum(1 for row in tampered_rows if not row["verification_passed"])

    lines = [
        "# Week 10 Noise Verification Summary",
        "",
        f"- Clip norm: {clip_norm}",
        f"- Noise multiplier: {noise_multiplier}",
        f"- Honest cases accepted: {honest_passes}/{len(honest_rows)}",
        f"- Tampered cases rejected: {tampered_rejected}/{len(tampered_rows)}",
        "",
        "Interpretation:",
        "- Honest cases satisfy both the seed-to-noise mapping and the noisy-update relation.",
        "- Tampered cases can break either the generated noise itself or the final noisy update relation.",
        "",
        "Current status:",
        "- This prototype uses deterministic seed-based noise so the process can be verified.",
        "- Week 7 baseline has been aligned to the same seed-based noise direction, but the project still needs formal DP accounting and ZK circuit mapping.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 10 noise verification prototype")
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tolerance", type=float, default=1e-5)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 10 - Noise Verification Prototype")
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

        case_seed = args.seed + client_id * 100
        honest_noise, honest_noisy_update = build_expected_noise_and_update(
            clipped_update=clipped_update,
            noise_multiplier=args.noise_multiplier,
            clip_norm=args.clip_norm,
            seed=case_seed,
        )

        tampered_noise = make_noise_tamper_case(honest_noise, args.clip_norm)
        tampered_noisy_update = make_noisy_update_tamper_case(honest_noisy_update, args.clip_norm)

        cases = [
            ("honest_noise", "pass", case_seed, honest_noise, honest_noisy_update),
            ("tampered_noise", "fail", case_seed, tampered_noise, add_state_noise(clipped_update, tampered_noise)),
            ("tampered_noisy_update", "fail", case_seed, honest_noise, tampered_noisy_update),
        ]

        print(
            f"Client {client_id}: samples={len(y_client)}, local_loss={avg_loss:.4f}, "
            f"raw_update_norm={raw_norm:.6f}, clipped_norm={state_l2_norm(clipped_update):.6f}"
        )

        for case_name, expected_result, case_seed_value, claimed_noise, claimed_noisy_update in cases:
            verdict = verify_noise_application(
                clipped_update=clipped_update,
                claimed_noise=claimed_noise,
                claimed_noisy_update=claimed_noisy_update,
                noise_multiplier=args.noise_multiplier,
                clip_norm=args.clip_norm,
                seed=case_seed_value,
                tolerance=args.tolerance,
            )
            rows.append(
                {
                    "client_id": client_id,
                    "seed": case_seed_value,
                    "case_name": case_name,
                    "expected_result": expected_result,
                    "verification_passed": verdict["passed"],
                    "clipped_update_norm": round(float(verdict["clipped_update_norm"]), 6),
                    "claimed_noise_norm": round(float(verdict["claimed_noise_norm"]), 6),
                    "claimed_noisy_update_norm": round(float(verdict["claimed_noisy_update_norm"]), 6),
                    "noise_multiplier": args.noise_multiplier,
                    "clip_norm": args.clip_norm,
                    "seed_noise_ok": verdict["seed_noise_ok"],
                    "update_relation_ok": verdict["update_relation_ok"],
                    "full_update_ok": verdict["full_update_ok"],
                    "noise_max_abs_error": round(float(verdict["noise_max_abs_error"]), 8),
                    "update_relation_max_abs_error": round(float(verdict["update_relation_max_abs_error"]), 8),
                    "full_update_max_abs_error": round(float(verdict["full_update_max_abs_error"]), 8),
                }
            )

    write_csv(rows, RESULTS_DIR / "noise_verification_cases.csv")
    write_summary(
        rows,
        RESULTS_DIR / "summary.md",
        clip_norm=args.clip_norm,
        noise_multiplier=args.noise_multiplier,
    )

    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
