"""multi-round threat matrix - Multi-round proof-gated threat matrix on non-IID CoverType."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from covertype_large_dataset_scaling.run_covertype_scaling import (
    MulticlassLinearModel,
    clip_update,
    evaluate,
    seeded_noise,
    set_seed,
    state_l2_norm,
    train_local,
    weighted_average,
)
from noniid_client_scaling.run_noniid_client_scaling import prepare_data


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
ATTACKS = ["relation_tamper", "clip_bypass", "replay", "zero_noise", "bounded_sign_flip"]
POLICIES = ["ungated", "current_vdp_gate", "strengthened_vdp_gate"]


def clone_state(state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: value.detach().cpu().clone() for key, value in state.items()}


def add_states(left: dict[str, torch.Tensor], right: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: left[key] + right[key] for key in left}


def zeros_like(state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: torch.zeros_like(value) for key, value in state.items()}


def negate_state(state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: -value for key, value in state.items()}


def scale_state(state: dict[str, torch.Tensor], factor: float) -> dict[str, torch.Tensor]:
    return {key: value * factor for key, value in state.items()}


def tamper_first_value(state: dict[str, torch.Tensor], amount: float) -> dict[str, torch.Tensor]:
    output = clone_state(state)
    first_key = next(iter(output))
    flat = output[first_key].reshape(-1)
    flat[0] += amount
    return output


def max_relation_gap(
    clipped: dict[str, torch.Tensor],
    noise: dict[str, torch.Tensor],
    noisy: dict[str, torch.Tensor],
) -> float:
    return max(
        float(torch.max(torch.abs(noisy[key] - clipped[key] - noise[key])).item())
        for key in clipped
    )


def state_digest(state: dict[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for key in sorted(state):
        digest.update(key.encode("utf-8"))
        digest.update(state[key].detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def proof_identifier(artifact: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for field in ("client_id", "round_id", "model_hash"):
        digest.update(str(artifact[field]).encode("utf-8"))
    for state_name in ("q_clipped", "q_noise", "q_noisy"):
        digest.update(state_digest(artifact[state_name]).encode("ascii"))
    return digest.hexdigest()


def build_artifact(
    *,
    raw_update: dict[str, torch.Tensor],
    client_id: int,
    round_id: int,
    model_hash: str,
    seed: int,
    clip_norm: float,
    noise_multiplier: float,
) -> dict[str, Any]:
    clipped = clip_update(raw_update, clip_norm)
    noise = seeded_noise(
        clipped,
        seed=seed,
        clip_norm=clip_norm,
        noise_multiplier=noise_multiplier,
    )
    artifact: dict[str, Any] = {
        "client_id": client_id,
        "round_id": round_id,
        "model_hash": model_hash,
        "noise_seed": seed,
        "seed_visibility": "public_deterministic",
        "q_clipped": clipped,
        "q_noise": noise,
        "q_noisy": add_states(clipped, noise),
        "proof_verified": True,
        "noise_generation_ok": True,
        "training_provenance_ok": True,
        "attack": "honest",
    }
    artifact["proof_id"] = proof_identifier(artifact)
    return artifact


def apply_attack(
    honest: dict[str, Any],
    attack: str,
    previous: dict[str, Any] | None,
    *,
    tamper_amount: float,
    clip_bypass_factor: float,
    clip_norm: float,
) -> dict[str, Any]:
    if attack == "replay" and previous is not None:
        replayed = copy.deepcopy(previous)
        replayed["attack"] = "replay"
        return replayed
    artifact = copy.deepcopy(honest)
    artifact["attack"] = attack
    if attack == "relation_tamper":
        artifact["q_noisy"] = tamper_first_value(artifact["q_noisy"], tamper_amount)
    elif attack == "clip_bypass":
        current_norm = state_l2_norm(artifact["q_clipped"])
        forced_factor = max(
            clip_bypass_factor,
            (1.25 * clip_norm) / max(current_norm, 1e-12),
        )
        artifact["q_clipped"] = scale_state(artifact["q_clipped"], forced_factor)
        artifact["q_noisy"] = add_states(artifact["q_clipped"], artifact["q_noise"])
    elif attack == "zero_noise":
        artifact["q_noise"] = zeros_like(artifact["q_noise"])
        artifact["q_noisy"] = clone_state(artifact["q_clipped"])
        artifact["noise_generation_ok"] = False
    elif attack == "bounded_sign_flip":
        artifact["q_clipped"] = negate_state(artifact["q_clipped"])
        artifact["q_noisy"] = add_states(artifact["q_clipped"], artifact["q_noise"])
        artifact["training_provenance_ok"] = False
    elif attack == "replay":
        # No previous proof exists in round 1, so the client behaves honestly.
        artifact["attack"] = "replay_warmup_honest"
    else:
        raise ValueError(f"Unknown attack: {attack}")
    artifact["proof_id"] = proof_identifier(artifact)
    return artifact


def evaluate_artifact(
    artifact: dict[str, Any],
    *,
    expected_client: int,
    expected_round: int,
    expected_model_hash: str,
    clip_norm: float,
    seen_proofs: set[str],
) -> dict[str, bool | float]:
    clip_value = state_l2_norm(artifact["q_clipped"])
    relation_gap = max_relation_gap(
        artifact["q_clipped"], artifact["q_noise"], artifact["q_noisy"]
    )
    return {
        "proof_ok": bool(artifact["proof_verified"]),
        "clip_ok": clip_value <= clip_norm + 1e-6,
        "relation_ok": relation_gap <= 1e-6,
        "context_ok": (
            int(artifact["client_id"]) == expected_client
            and int(artifact["round_id"]) == expected_round
            and str(artifact["model_hash"]) == expected_model_hash
        ),
        "replay_ok": str(artifact["proof_id"]) not in seen_proofs,
        "noise_generation_ok": bool(artifact["noise_generation_ok"]),
        "training_provenance_ok": bool(artifact["training_provenance_ok"]),
        "clip_norm_actual": clip_value,
        "relation_linf_gap": relation_gap,
    }


def policy_accept(policy: str, checks: dict[str, bool | float]) -> bool:
    if policy == "ungated":
        return True
    current = bool(checks["proof_ok"] and checks["clip_ok"] and checks["relation_ok"])
    if policy == "current_vdp_gate":
        return current
    if policy == "strengthened_vdp_gate":
        return bool(
            current
            and checks["context_ok"]
            and checks["replay_ok"]
            and checks["noise_generation_ok"]
        )
    raise ValueError(f"Unknown policy: {policy}")


def run_trajectory(
    args: argparse.Namespace,
    *,
    seed: int,
    attack: str,
    policy: str,
    prepared: tuple[Any, torch.Tensor, torch.Tensor, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if prepared is None:
        prep_args = argparse.Namespace(**vars(args))
        prep_args.seed = seed
        client_datasets, test_x, test_y, metadata = prepare_data(prep_args)
    else:
        client_datasets, test_x, test_y, metadata = prepared
    attacker_count = max(1, math.ceil(args.clients * args.attacker_fraction))
    attacker_ids = sorted(
        range(args.clients), key=lambda client_id: len(client_datasets[client_id]), reverse=True
    )[:attacker_count]
    set_seed(seed)
    device = torch.device("cpu")
    model = MulticlassLinearModel(54, 7).to(device)
    initial_accuracy = evaluate(model, test_x, test_y, device)
    accuracies = [initial_accuracy]
    decisions: list[dict[str, Any]] = []
    seen_proofs: set[str] = set()
    previous_attacker_artifacts: dict[int, dict[str, Any]] = {}
    start = time.perf_counter()

    for round_id in range(1, args.rounds + 1):
        global_state = clone_state(model.state_dict())
        model_hash = state_digest(global_state)
        accepted_updates: list[dict[str, torch.Tensor]] = []
        accepted_weights: list[int] = []
        round_artifacts: list[dict[str, Any]] = []
        for client_id, dataset in enumerate(client_datasets):
            local_state, _ = train_local(
                model,
                dataset,
                input_dim=54,
                num_classes=7,
                device=device,
                epochs=args.local_epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                shuffle_seed=seed + round_id * 10_000 + client_id * 100,
            )
            raw_update = {key: local_state[key] - global_state[key] for key in global_state}
            honest = build_artifact(
                raw_update=raw_update,
                client_id=client_id,
                round_id=round_id,
                model_hash=model_hash,
                seed=seed + round_id * 10_000 + client_id * 100,
                clip_norm=args.clip_norm,
                noise_multiplier=args.noise_multiplier,
            )
            is_attacker = client_id in attacker_ids and attack != "none"
            submitted = (
                apply_attack(
                    honest,
                    attack,
                    previous_attacker_artifacts.get(client_id),
                    tamper_amount=args.tamper_amount,
                    clip_bypass_factor=args.clip_bypass_factor,
                    clip_norm=args.clip_norm,
                )
                if is_attacker
                else honest
            )
            checks = evaluate_artifact(
                submitted,
                expected_client=client_id,
                expected_round=round_id,
                expected_model_hash=model_hash,
                clip_norm=args.clip_norm,
                seen_proofs=seen_proofs,
            )
            accepted = policy_accept(policy, checks)
            if accepted:
                accepted_updates.append(clone_state(submitted["q_noisy"]))
                accepted_weights.append(len(dataset))
            decisions.append(
                {
                    "seed": seed,
                    "attack": attack,
                    "policy": policy,
                    "round_id": round_id,
                    "client_id": client_id,
                    "is_attacker": is_attacker,
                    "is_malicious_submission": (
                        is_attacker and submitted["attack"] != "replay_warmup_honest"
                    ),
                    "submitted_attack": submitted["attack"],
                    **checks,
                    "accepted": accepted,
                }
            )
            round_artifacts.append(submitted)
            if is_attacker:
                previous_attacker_artifacts[client_id] = copy.deepcopy(honest)

        if not accepted_updates:
            raise RuntimeError(f"No accepted updates for {seed}/{attack}/{policy}/round{round_id}")
        averaged = weighted_average(accepted_updates, accepted_weights)
        model.load_state_dict(add_states(global_state, averaged))
        accuracies.append(evaluate(model, test_x, test_y, device))
        seen_proofs.update(str(artifact["proof_id"]) for artifact in round_artifacts)

    attacker_decisions = [row for row in decisions if row["is_malicious_submission"]]
    result = {
        "seed": seed,
        "attack": attack,
        "policy": policy,
        "clients": args.clients,
        "attackers": attacker_count,
        "attacker_ids": attacker_ids,
        "partition": args.partition,
        "train_size": int(metadata["train_size"]),
        "rounds": args.rounds,
        "initial_accuracy": round(initial_accuracy, 6),
        "final_accuracy": round(accuracies[-1], 6),
        "best_accuracy": round(max(accuracies), 6),
        "round_accuracies": [round(value, 6) for value in accuracies],
        "accepted_updates": sum(bool(row["accepted"]) for row in decisions),
        "total_updates": len(decisions),
        "attacker_updates_accepted": sum(bool(row["accepted"]) for row in attacker_decisions),
        "attacker_updates_total": len(attacker_decisions),
        "attacker_acceptance_rate": round(
            sum(bool(row["accepted"]) for row in attacker_decisions) / max(1, len(attacker_decisions)),
            6,
        ),
        "training_sec": round(time.perf_counter() - start, 6),
        "label_tv_mean": metadata["label_tv_mean"],
    }
    return result, decisions


def mean(rows: list[dict[str, Any]], field: str) -> float:
    return float(np.mean([float(row[field]) for row in rows]))


def sample_std(rows: list[dict[str, Any]], field: str) -> float:
    return float(np.std([float(row[field]) for row in rows], ddof=1)) if len(rows) > 1 else 0.0


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean_by_seed = {
        int(row["seed"]): float(row["final_accuracy"])
        for row in rows
        if row["attack"] == "none"
    }
    output: list[dict[str, Any]] = []
    for attack, policy in sorted({(str(row["attack"]), str(row["policy"])) for row in rows}):
        group = [row for row in rows if row["attack"] == attack and row["policy"] == policy]
        retention_values = [
            float(row["final_accuracy"]) / max(clean_by_seed[int(row["seed"])], 1e-9)
            for row in group
        ]
        output.append(
            {
                "attack": attack,
                "policy": policy,
                "seeds": len(group),
                "final_accuracy_mean": round(mean(group, "final_accuracy"), 6),
                "final_accuracy_std": round(sample_std(group, "final_accuracy"), 6),
                "clean_retention_mean": round(float(np.mean(retention_values)), 6),
                "attacker_acceptance_rate_mean": round(mean(group, "attacker_acceptance_rate"), 6),
                "accepted_updates_mean": round(mean(group, "accepted_updates"), 3),
                "training_sec_mean": round(mean(group, "training_sec"), 3),
            }
        )
    return output


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for key, value in list(serialized.items()):
                if isinstance(value, (list, dict)):
                    serialized[key] = json.dumps(value)
            writer.writerow(serialized)


def write_chart(rows: list[dict[str, Any]], path: Path) -> None:
    attack_rows = [row for row in rows if row["attack"] != "none"]
    attacks = ATTACKS
    policies = POLICIES
    x = np.arange(len(attacks))
    width = 0.25
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))
    colors = ["#757575", "#EF6C00", "#2E7D32"]
    for index, policy in enumerate(policies):
        selected = [next(row for row in attack_rows if row["attack"] == attack and row["policy"] == policy) for attack in attacks]
        axes[0].bar(
            x + (index - 1) * width,
            [row["clean_retention_mean"] for row in selected],
            width,
            label=policy,
            color=colors[index],
        )
        axes[1].bar(
            x + (index - 1) * width,
            [row["attacker_acceptance_rate_mean"] for row in selected],
            width,
            label=policy,
            color=colors[index],
        )
    axes[0].axhline(0.9, linestyle="--", color="#C62828", label="90% clean retention")
    axes[0].set_title("Final accuracy relative to clean DP trajectory")
    axes[0].set_ylabel("Retention")
    axes[1].set_title("Malicious update acceptance")
    axes[1].set_ylabel("Acceptance rate")
    for axis in axes:
        axis.set_xticks(x, [name.replace("_", "\n") for name in attacks])
        axis.grid(axis="y", alpha=0.25)
        axis.legend(fontsize=8)
    fig.suptitle("Multi-round proof-gated threat matrix", fontsize=14)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_summary_md(rows: list[dict[str, Any]], path: Path, args: argparse.Namespace) -> None:
    clean = next(row for row in rows if row["attack"] == "none")
    decision_count = (
        len(args.seeds)
        * (1 + len(ATTACKS) * len(POLICIES))
        * args.rounds
        * args.clients
    )
    lines = [
        "# multi-round threat matrix 多輪 Proof-Gated Threat Matrix 摘要",
        "",
        "## 設定",
        "",
        f"- CoverType train_size={args.train_size}、K={args.clients}、partition={args.partition}。",
        f"- Seeds={args.seeds}、rounds={args.rounds}、attacker fraction={args.attacker_fraction}。",
        "- Current gate：proof + clipping bound + additive relation。",
        "- Strengthened gate：current gate + client/round/model context + replay protection + noise-generation policy。",
        "- Bounded sign flip 刻意保持 clipping/noise 關係合法，用來界定未證明 local training provenance 的剩餘風險。",
        f"- {decision_count:,} 次決策為重用前期 actual-EZKL artifact/check contract 的 "
        "policy simulation；本實驗未逐更新產生等量 actual proofs。",
        "",
        f"Clean DP final accuracy mean={clean['final_accuracy_mean']:.6f}。",
        "",
        "| Attack | Policy | Final mean | Clean retention | Attacker acceptance | Accepted updates |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row["attack"] == "none":
            continue
        lines.append(
            f"| {row['attack']} | {row['policy']} | {row['final_accuracy_mean']:.6f} | "
            f"{row['clean_retention_mean']:.6f} | {row['attacker_acceptance_rate_mean']:.6f} | "
            f"{row['accepted_updates_mean']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## 假設判定",
            "",
            "- Relation tamper 與 clip bypass 應由 current gate 拒絕。",
            "- Replay 與 zero-noise 會暴露 current gate 的 context/randomness 缺口，應由 strengthened gate 拒絕。",
            "- Bounded sign flip 即使在 strengthened VDP gate 下仍可通過，因為本研究沒有證明完整 local training provenance。",
            "- 因此，多輪 gate 架構成立於『DP-update constraint audit』範圍；若要同時阻止任意 model poisoning，必須再加入 local-training proof 或其他 robust aggregation。",
            "- Public deterministic seed 的 epsilon infinity 限制仍未由本實驗修復。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-round proof-gated threat matrix")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62])
    parser.add_argument("--train-size", type=int, default=100000)
    parser.add_argument("--clients", type=int, default=10)
    parser.add_argument("--partition", default="dirichlet_0.1")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--min-client-size", type=int, default=64)
    parser.add_argument("--attacker-fraction", type=float, default=0.2)
    parser.add_argument("--tamper-amount", type=float, default=0.5)
    parser.add_argument("--clip-bypass-factor", type=float, default=2.0)
    args = parser.parse_args()

    all_runs: list[dict[str, Any]] = []
    all_decisions: list[dict[str, Any]] = []
    for seed in args.seeds:
        prep_args = argparse.Namespace(**vars(args))
        prep_args.seed = seed
        prepared = prepare_data(prep_args)
        print(f"Running seed={seed}, clean trajectory", flush=True)
        clean_run, clean_decisions = run_trajectory(
            args,
            seed=seed,
            attack="none",
            policy="current_vdp_gate",
            prepared=prepared,
        )
        all_runs.append(clean_run)
        all_decisions.extend(clean_decisions)
        for attack in ATTACKS:
            for policy in POLICIES:
                print(f"Running seed={seed}, attack={attack}, policy={policy}", flush=True)
                run, decisions = run_trajectory(
                    args,
                    seed=seed,
                    attack=attack,
                    policy=policy,
                    prepared=prepared,
                )
                all_runs.append(run)
                all_decisions.extend(decisions)

    summary = summarize(all_runs)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(all_runs, RESULTS_DIR / "threat_trajectories.csv")
    write_csv(all_decisions, RESULTS_DIR / "threat_decisions.csv")
    write_csv(summary, RESULTS_DIR / "threat_summary.csv")
    write_chart(summary, RESULTS_DIR / "threat_matrix.png")
    write_summary_md(summary, RESULTS_DIR / "summary.md", args)
    (RESULTS_DIR / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    print(f"Completed {len(all_runs)} trajectories and {len(all_decisions)} client decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
