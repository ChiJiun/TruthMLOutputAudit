"""robust aggregation: bounded-poisoning evaluation with robust aggregation."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import itertools
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from scipy import stats


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from covertype_large_dataset_scaling.run_covertype_scaling import (
    MulticlassLinearModel,
    evaluate,
    set_seed,
    state_l2_norm,
    train_local,
)
from noniid_client_scaling.run_noniid_client_scaling import prepare_data
from multiround_threat_matrix.run_multiround_threat_matrix import (
    add_states,
    build_artifact,
    clone_state,
    evaluate_artifact,
    policy_accept,
    proof_identifier,
    scale_state,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
AGGREGATORS = ("mean", "coordinate_median", "trimmed_mean")


def aggregate_states(
    states: list[dict[str, torch.Tensor]], method: str, trim_count: int
) -> dict[str, torch.Tensor]:
    if not states:
        raise ValueError("at least one state is required")
    if method == "trimmed_mean" and len(states) <= 2 * trim_count:
        raise ValueError("trim_count leaves no values to aggregate")
    output: dict[str, torch.Tensor] = {}
    for key in states[0]:
        stacked = torch.stack([state[key] for state in states], dim=0)
        if method == "mean":
            output[key] = torch.mean(stacked, dim=0)
        elif method == "coordinate_median":
            output[key] = torch.median(stacked, dim=0).values
        elif method == "trimmed_mean":
            ordered = torch.sort(stacked, dim=0).values
            output[key] = torch.mean(ordered[trim_count : len(states) - trim_count], dim=0)
        else:
            raise ValueError(f"unknown aggregation method: {method}")
    return output


def bounded_sign_flip(artifact: dict[str, Any], clip_norm: float) -> dict[str, Any]:
    attacked = copy.deepcopy(artifact)
    norm = state_l2_norm(attacked["q_clipped"])
    if norm > 0:
        attacked["q_clipped"] = scale_state(attacked["q_clipped"], -clip_norm / norm)
    attacked["q_noisy"] = add_states(attacked["q_clipped"], attacked["q_noise"])
    attacked["training_provenance_ok"] = False
    attacked["attack"] = "bounded_full_norm_sign_flip"
    attacked["proof_id"] = proof_identifier(attacked)
    return attacked


def run_trajectory(
    args: argparse.Namespace,
    *,
    seed: int,
    aggregator: str,
    attacked: bool,
    prepared: tuple[Any, torch.Tensor, torch.Tensor, dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    client_datasets, test_x, test_y, metadata = prepared
    if args.test_size > 0 and len(test_y) > args.test_size:
        rng = np.random.default_rng(seed + 1777)
        chosen = np.sort(rng.choice(len(test_y), size=args.test_size, replace=False))
        test_x = test_x[chosen]
        test_y = test_y[chosen]
    attacker_count = max(1, math.floor(args.clients * args.attacker_fraction))
    attacker_ids = sorted(
        range(args.clients), key=lambda client_id: len(client_datasets[client_id]), reverse=True
    )[:attacker_count]
    set_seed(seed)
    model = MulticlassLinearModel(54, 7).cpu()
    accuracies = [evaluate(model, test_x, test_y, torch.device("cpu"))]
    decisions: list[dict[str, Any]] = []
    seen_proofs: set[str] = set()
    start = time.perf_counter()

    for round_id in range(1, args.rounds + 1):
        global_state = clone_state(model.state_dict())
        digest = hashlib.sha256()
        for key in sorted(global_state):
            digest.update(key.encode("utf-8"))
            digest.update(global_state[key].numpy().tobytes())
        model_hash = digest.hexdigest()
        accepted_updates: list[dict[str, torch.Tensor]] = []
        round_proofs: list[str] = []
        for client_id, dataset in enumerate(client_datasets):
            update_seed = seed + round_id * 100_003 + client_id * 997
            local_state, _ = train_local(
                model,
                dataset,
                input_dim=54,
                num_classes=7,
                device=torch.device("cpu"),
                epochs=args.local_epochs,
                batch_size=args.batch_size,
                lr=args.lr,
                shuffle_seed=update_seed,
            )
            raw_update = {key: local_state[key] - global_state[key] for key in global_state}
            artifact = build_artifact(
                raw_update=raw_update,
                client_id=client_id,
                round_id=round_id,
                model_hash=model_hash,
                seed=update_seed,
                clip_norm=args.clip_norm,
                noise_multiplier=args.noise_multiplier,
            )
            is_attacker = attacked and client_id in attacker_ids
            if is_attacker:
                artifact = bounded_sign_flip(artifact, args.clip_norm)
            checks = evaluate_artifact(
                artifact,
                expected_client=client_id,
                expected_round=round_id,
                expected_model_hash=model_hash,
                clip_norm=args.clip_norm,
                seen_proofs=seen_proofs,
            )
            accepted = policy_accept("strengthened_vdp_gate", checks)
            if accepted:
                accepted_updates.append(clone_state(artifact["q_noisy"]))
            decisions.append({
                "seed": seed,
                "aggregator": aggregator,
                "condition": "bounded_poisoning" if attacked else "clean",
                "round_id": round_id,
                "client_id": client_id,
                "is_attacker": is_attacker,
                "accepted": accepted,
                "clip_norm_actual": checks["clip_norm_actual"],
                "relation_linf_gap": checks["relation_linf_gap"],
                "training_provenance_ok": checks["training_provenance_ok"],
            })
            round_proofs.append(str(artifact["proof_id"]))
        if len(accepted_updates) != args.clients:
            raise RuntimeError("strengthened gate unexpectedly rejected a bounded submission")
        aggregate = aggregate_states(accepted_updates, aggregator, attacker_count)
        model.load_state_dict(add_states(global_state, aggregate))
        accuracies.append(evaluate(model, test_x, test_y, torch.device("cpu")))
        seen_proofs.update(round_proofs)

    attacker_rows = [row for row in decisions if row["is_attacker"]]
    return ({
        "seed": seed,
        "aggregator": aggregator,
        "condition": "bounded_poisoning" if attacked else "clean",
        "clients": args.clients,
        "attackers": attacker_count,
        "rounds": args.rounds,
        "train_size": metadata["train_size"],
        "test_size": len(test_y),
        "partition": args.partition,
        "label_tv_mean": metadata["label_tv_mean"],
        "initial_accuracy": round(accuracies[0], 6),
        "final_accuracy": round(accuracies[-1], 6),
        "best_accuracy": round(max(accuracies), 6),
        "round_accuracies": [round(value, 6) for value in accuracies],
        "attacker_acceptance_rate": round(
            sum(bool(row["accepted"]) for row in attacker_rows) / max(1, len(attacker_rows)), 6
        ),
        "training_sec": round(time.perf_counter() - start, 6),
    }, decisions)


def ci95(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(stats.t.ppf(0.975, len(values) - 1) * np.std(values, ddof=1) / math.sqrt(len(values)))


def exact_sign_flip_pvalue(differences: list[float]) -> float:
    observed = abs(float(np.mean(differences)))
    if not differences:
        return 1.0
    extreme = 0
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(differences)):
        permuted = abs(float(np.mean(np.asarray(signs) * np.asarray(differences))))
        extreme += int(permuted >= observed - 1e-15)
        total += 1
    return extreme / total


def summarize(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary: list[dict[str, Any]] = []
    retention_by_aggregator: dict[str, dict[int, float]] = {}
    for aggregator in AGGREGATORS:
        clean = {int(row["seed"]): float(row["final_accuracy"]) for row in rows if row["aggregator"] == aggregator and row["condition"] == "clean"}
        attack = {int(row["seed"]): float(row["final_accuracy"]) for row in rows if row["aggregator"] == aggregator and row["condition"] == "bounded_poisoning"}
        seeds = sorted(clean)
        differences = [attack[seed] - clean[seed] for seed in seeds]
        retentions = [attack[seed] / max(clean[seed], 1e-12) for seed in seeds]
        retention_by_aggregator[aggregator] = dict(zip(seeds, retentions))
        attack_rows = [row for row in rows if row["aggregator"] == aggregator and row["condition"] == "bounded_poisoning"]
        summary.append({
            "aggregator": aggregator,
            "seeds": len(seeds),
            "clean_accuracy_mean": round(float(np.mean(list(clean.values()))), 6),
            "clean_accuracy_ci95": round(ci95(list(clean.values())), 6),
            "attack_accuracy_mean": round(float(np.mean(list(attack.values()))), 6),
            "attack_accuracy_ci95": round(ci95(list(attack.values())), 6),
            "paired_accuracy_change_mean": round(float(np.mean(differences)), 6),
            "paired_accuracy_change_ci95": round(ci95(differences), 6),
            "retention_mean": round(float(np.mean(retentions)), 6),
            "retention_ci95": round(ci95(retentions), 6),
            "attack_effect_exact_signflip_p": round(exact_sign_flip_pvalue(differences), 6),
            "attacker_acceptance_rate_mean": round(float(np.mean([row["attacker_acceptance_rate"] for row in attack_rows])), 6),
        })
    comparisons: list[dict[str, Any]] = []
    baseline = retention_by_aggregator["mean"]
    for aggregator in ("coordinate_median", "trimmed_mean"):
        gains = [retention_by_aggregator[aggregator][seed] - baseline[seed] for seed in sorted(baseline)]
        comparisons.append({
            "robust_aggregator": aggregator,
            "baseline": "mean",
            "seeds": len(gains),
            "paired_retention_gain_mean": round(float(np.mean(gains)), 6),
            "paired_retention_gain_ci95": round(ci95(gains), 6),
            "exact_signflip_p": round(exact_sign_flip_pvalue(gains), 6),
        })
    return summary, comparisons


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for key, value in list(serialized.items()):
                if isinstance(value, (list, dict)):
                    serialized[key] = json.dumps(value)
            writer.writerow(serialized)


def write_summary(summary: list[dict[str, Any]], comparisons: list[dict[str, Any]], args: argparse.Namespace) -> None:
    lines = [
        "# robust aggregation Bounded-poisoning Robust Aggregation Summary",
        "",
        f"- CoverType train/test={args.train_size}/{args.test_size}; K={args.clients}, R={args.rounds}, attackers={args.attacker_fraction:.0%}, seeds={args.seeds}.",
        f"- Non-IID partition={args.partition}; clipping C={args.clip_norm}; Gaussian systems noise multiplier={args.noise_multiplier}.",
        "- Attackers submit a sign-reversed update rescaled to the full clipping bound. It satisfies clipping, additive-noise, context, and replay checks, so the strengthened VDP gate accepts it.",
        "- Mean, coordinate-wise median, and coordinate-wise trimmed mean are compared with uniform client weighting and aggregator-specific clean controls.",
        "- Client-update decisions simulate the proved contract; this experiment does not generate one actual proof per decision.",
        "",
        "| Aggregator | Clean accuracy | Attack accuracy | Paired change | Retention | Attack p | Attacker accepted |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['aggregator']} | {row['clean_accuracy_mean']:.4f} ± {row['clean_accuracy_ci95']:.4f} | "
            f"{row['attack_accuracy_mean']:.4f} ± {row['attack_accuracy_ci95']:.4f} | "
            f"{row['paired_accuracy_change_mean']:.4f} ± {row['paired_accuracy_change_ci95']:.4f} | "
            f"{row['retention_mean']:.4f} ± {row['retention_ci95']:.4f} | "
            f"{row['attack_effect_exact_signflip_p']:.4f} | {row['attacker_acceptance_rate_mean']:.2f} |"
        )
    lines.extend(["", "## Paired robustness gain over mean", "", "| Robust aggregator | Retention gain | Exact sign-flip p |", "|---|---:|---:|"])
    for row in comparisons:
        lines.append(
            f"| {row['robust_aggregator']} | {row['paired_retention_gain_mean']:.4f} ± {row['paired_retention_gain_ci95']:.4f} | {row['exact_signflip_p']:.4f} |"
        )
    lines.extend([
        "",
        "## Scope",
        "",
        "This significantly mitigates the tested bounded-poisoning attack through an aggregation defense under the explicit assumption that no more than the trimmed fraction of clients are malicious. It does not eliminate the measured utility loss, establish arbitrary Byzantine robustness, or prove that a client followed the prescribed optimizer; those would require a stronger robust-learning analysis or a separate training-provenance circuit.",
    ])
    (RESULTS_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62, 72, 82, 92, 102, 112, 122, 132])
    parser.add_argument("--train-size", type=int, default=50_000)
    parser.add_argument("--test-size", type=int, default=20_000)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--clients", type=int, default=10)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--partition", default="dirichlet_0.5")
    parser.add_argument("--min-client-size", type=int, default=64)
    parser.add_argument("--attacker-fraction", type=float, default=0.2)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.03)
    parser.add_argument("--torch-threads", type=int, default=4)
    args = parser.parse_args()
    torch.set_num_threads(args.torch_threads)

    rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for seed in args.seeds:
        prep_args = argparse.Namespace(**vars(args), seed=seed)
        prepared = prepare_data(prep_args)
        for aggregator in AGGREGATORS:
            for attacked in (False, True):
                condition = "attack" if attacked else "clean"
                print(f"seed={seed}, aggregator={aggregator}, condition={condition}", flush=True)
                row, decision_rows = run_trajectory(
                    args, seed=seed, aggregator=aggregator, attacked=attacked, prepared=prepared
                )
                rows.append(row)
                decisions.extend(decision_rows)
    summary, comparisons = summarize(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows, RESULTS_DIR / "trajectories.csv")
    write_csv(decisions, RESULTS_DIR / "decisions.csv")
    write_csv(summary, RESULTS_DIR / "aggregation_summary.csv")
    write_csv(comparisons, RESULTS_DIR / "robustness_comparisons.csv")
    (RESULTS_DIR / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    write_summary(summary, comparisons, args)
    print(f"completed {len(rows)} trajectories and {len(decisions)} decisions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
