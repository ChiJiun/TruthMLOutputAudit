"""
Week 20 - Repeat FL/DP experiments across multiple similar tabular datasets.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.compose import ColumnTransformer
from sklearn.datasets import fetch_openml, load_breast_cancer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from torch.utils.data import DataLoader, TensorDataset


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"

DATASETS = {
    "breast_cancer_wisconsin": {"source": "sklearn"},
    "pima_diabetes": {"source": "openml", "data_id": 37},
    "german_credit": {"source": "openml", "data_id": 31},
    "banknote_authentication": {"source": "openml", "data_id": 1462},
}


class SimpleLinearModel(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.fc = nn.Linear(input_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(x)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_raw_dataset(dataset_name: str) -> tuple[pd.DataFrame, np.ndarray]:
    spec = DATASETS[dataset_name]
    if spec["source"] == "sklearn":
        x, y = load_breast_cancer(return_X_y=True)
        feature_names = [f"feature_{idx}" for idx in range(x.shape[1])]
        return pd.DataFrame(x, columns=feature_names), y.astype(int)

    data = fetch_openml(data_id=int(spec["data_id"]), as_frame=True, parser="auto")
    x_df = data.data.copy()
    y_raw = data.target
    y = LabelEncoder().fit_transform(y_raw)
    if len(np.unique(y)) != 2:
        raise ValueError(f"{dataset_name} is not binary after label encoding.")
    return x_df, y.astype(int)


def preprocess_split(
    x_df: pd.DataFrame,
    y: np.ndarray,
    *,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x_train, x_test, y_train, y_test = train_test_split(
        x_df,
        y,
        test_size=0.2,
        random_state=seed,
        stratify=y,
    )

    categorical_cols = [
        col
        for col in x_train.columns
        if pd.api.types.is_object_dtype(x_train[col]) or isinstance(x_train[col].dtype, pd.CategoricalDtype)
    ]
    numeric_cols = [col for col in x_train.columns if col not in categorical_cols]

    transformer = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_cols,
            ),
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical_cols,
            ),
        ],
    )

    x_train_arr = transformer.fit_transform(x_train).astype(np.float32)
    x_test_arr = transformer.transform(x_test).astype(np.float32)
    return x_train_arr, x_test_arr, y_train.astype(np.float32), y_test.astype(np.float32)


def split_clients(x_train: np.ndarray, y_train: np.ndarray, clients: int, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    indices = np.arange(len(x_train))
    rng = np.random.default_rng(seed)
    rng.shuffle(indices)
    partitions = np.array_split(indices, clients)
    return [(x_train[part], y_train[part]) for part in partitions]


def evaluate_model(model: nn.Module, x_test: np.ndarray, y_test: np.ndarray, device: torch.device) -> float:
    model.eval()
    x_t = torch.tensor(x_test, dtype=torch.float32, device=device)
    y_t = torch.tensor(y_test, dtype=torch.float32, device=device).reshape(-1, 1)
    with torch.no_grad():
        logits = model(x_t)
        preds = (torch.sigmoid(logits) > 0.5).float()
        return float((preds == y_t).float().mean().item())


def train_local_model(
    global_model: nn.Module,
    x_client: np.ndarray,
    y_client: np.ndarray,
    device: torch.device,
    epochs: int,
    batch_size: int,
    lr: float,
) -> tuple[dict[str, torch.Tensor], float]:
    local_model = SimpleLinearModel(input_dim=x_client.shape[1]).to(device)
    local_model.load_state_dict(global_model.state_dict())
    local_model.train()

    dataset = TensorDataset(
        torch.tensor(x_client, dtype=torch.float32),
        torch.tensor(y_client, dtype=torch.float32).reshape(-1, 1),
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(local_model.parameters(), lr=lr)

    total_loss = 0.0
    batches = 0
    for _ in range(epochs):
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            logits = local_model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())
            batches += 1

    state = {key: value.detach().cpu().clone() for key, value in local_model.state_dict().items()}
    return state, total_loss / max(1, batches)


def subtract_states(local_state: dict[str, torch.Tensor], global_state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: local_state[key] - global_state[key] for key in global_state}


def add_states(global_state: dict[str, torch.Tensor], update_state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: global_state[key] + update_state[key] for key in global_state}


def weighted_average_states(states: list[dict[str, torch.Tensor]], weights: list[int]) -> dict[str, torch.Tensor]:
    total_weight = float(sum(weights))
    return {
        key: sum(state[key] * (weight / total_weight) for state, weight in zip(states, weights))
        for key in states[0]
    }


def state_l2_norm(state: dict[str, torch.Tensor]) -> float:
    total = 0.0
    for tensor in state.values():
        total += float(torch.sum(tensor.float() ** 2).item())
    return total ** 0.5


def clip_update(update_state: dict[str, torch.Tensor], clip_norm: float) -> dict[str, torch.Tensor]:
    norm = state_l2_norm(update_state)
    if norm == 0.0 or norm <= clip_norm:
        return {key: value.clone() for key, value in update_state.items()}
    scale = clip_norm / norm
    return {key: value * scale for key, value in update_state.items()}


def make_noise_seed(base_seed: int, round_idx: int, client_id: int) -> int:
    return int(base_seed + round_idx * 10_000 + client_id * 100)


def generate_seeded_noise(
    reference_state: dict[str, torch.Tensor],
    noise_multiplier: float,
    clip_norm: float,
    seed: int,
) -> dict[str, torch.Tensor]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    noise_std = noise_multiplier * clip_norm
    return {
        key: torch.randn(value.shape, generator=generator, dtype=value.dtype) * noise_std
        for key, value in reference_state.items()
    }


def run_experiment(
    *,
    dataset_name: str,
    mode: str,
    seed: int,
    rounds: int,
    local_epochs: int,
    batch_size: int,
    lr: float,
    clients: int,
    clip_norm: float,
    noise_multiplier: float,
) -> dict[str, object]:
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    x_df, y = load_raw_dataset(dataset_name)
    x_train, x_test, y_train, y_test = preprocess_split(x_df, y, seed=seed)
    client_sets = split_clients(x_train, y_train, clients=clients, seed=seed)

    global_model = SimpleLinearModel(input_dim=x_test.shape[1]).to(device)
    initial_acc = evaluate_model(global_model, x_test, y_test, device)
    round_accuracies = [initial_acc]
    round_losses: list[float] = []

    for round_idx in range(1, rounds + 1):
        global_state = {key: value.detach().cpu().clone() for key, value in global_model.state_dict().items()}
        updates: list[dict[str, torch.Tensor]] = []
        client_sizes: list[int] = []
        losses: list[float] = []

        for client_id, (x_client, y_client) in enumerate(client_sets):
            local_state, avg_loss = train_local_model(
                global_model=global_model,
                x_client=x_client,
                y_client=y_client,
                device=device,
                epochs=local_epochs,
                batch_size=batch_size,
                lr=lr,
            )
            update_state = subtract_states(local_state, global_state)
            if mode == "dp":
                clipped_state = clip_update(update_state, clip_norm)
                noise_state = generate_seeded_noise(
                    clipped_state,
                    noise_multiplier=noise_multiplier,
                    clip_norm=clip_norm,
                    seed=make_noise_seed(seed, round_idx, client_id),
                )
                update_state = {key: clipped_state[key] + noise_state[key] for key in clipped_state}
            updates.append(update_state)
            client_sizes.append(len(y_client))
            losses.append(avg_loss)

        averaged_update = weighted_average_states(updates, client_sizes)
        global_model.load_state_dict(add_states(global_state, averaged_update))
        round_accuracies.append(evaluate_model(global_model, x_test, y_test, device))
        round_losses.append(float(np.mean(losses)))

    return {
        "dataset": dataset_name,
        "mode": mode,
        "seed": seed,
        "clients": clients,
        "rounds": rounds,
        "samples": int(len(y)),
        "input_dim": int(x_test.shape[1]),
        "test_size": int(len(y_test)),
        "initial_accuracy": round(initial_acc, 6),
        "final_accuracy": round(round_accuracies[-1], 6),
        "best_accuracy": round(max(round_accuracies), 6),
        "mean_round_loss": round(float(np.mean(round_losses)), 6),
    }


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dataset",
        "mode",
        "seed",
        "clients",
        "rounds",
        "samples",
        "input_dim",
        "test_size",
        "initial_accuracy",
        "final_accuracy",
        "best_accuracy",
        "mean_round_loss",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dataset",
        "samples",
        "input_dim",
        "fl_final_mean",
        "fl_final_std",
        "dp_final_mean",
        "dp_final_std",
        "final_accuracy_gap",
        "dp_retention_ratio",
        "fl_best_mean",
        "dp_best_mean",
        "dp_effect_preserved",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary_rows: list[dict[str, object]] = []
    datasets = sorted({str(row["dataset"]) for row in rows})
    for dataset in datasets:
        dataset_rows = [row for row in rows if row["dataset"] == dataset]
        fl_rows = [row for row in dataset_rows if row["mode"] == "fl"]
        dp_rows = [row for row in dataset_rows if row["mode"] == "dp"]
        fl_final = np.array([float(row["final_accuracy"]) for row in fl_rows])
        dp_final = np.array([float(row["final_accuracy"]) for row in dp_rows])
        fl_best = np.array([float(row["best_accuracy"]) for row in fl_rows])
        dp_best = np.array([float(row["best_accuracy"]) for row in dp_rows])
        final_gap = float(np.mean(fl_final) - np.mean(dp_final))
        retention = float(np.mean(dp_final) / max(1e-9, np.mean(fl_final)))
        summary_rows.append(
            {
                "dataset": dataset,
                "samples": int(dataset_rows[0]["samples"]),
                "input_dim": int(dataset_rows[0]["input_dim"]),
                "fl_final_mean": round(float(np.mean(fl_final)), 6),
                "fl_final_std": round(float(np.std(fl_final)), 6),
                "dp_final_mean": round(float(np.mean(dp_final)), 6),
                "dp_final_std": round(float(np.std(dp_final)), 6),
                "final_accuracy_gap": round(final_gap, 6),
                "dp_retention_ratio": round(retention, 6),
                "fl_best_mean": round(float(np.mean(fl_best)), 6),
                "dp_best_mean": round(float(np.mean(dp_best)), 6),
                "dp_effect_preserved": retention >= 0.9,
            }
        )
    return summary_rows


def write_summary_md(
    summary_rows: list[dict[str, object]],
    output_path: Path,
    *,
    seeds: list[int],
    rounds: int,
    clients: int,
    clip_norm: float,
    noise_multiplier: float,
) -> None:
    effective_count = sum(1 for row in summary_rows if row["dp_effect_preserved"])
    lines = [
        "# Week 20 Multi-Dataset Repeatability Summary",
        "",
        "Goal:",
        "- Repeat the same FL/DP baseline experiment on multiple similar tabular binary classification datasets.",
        "- Check whether DP remains close to the FL baseline across datasets and random seeds.",
        "",
        "Datasets:",
    ]
    lines.extend(
        f"- {row['dataset']}: samples={row['samples']}, encoded_features={row['input_dim']}"
        for row in summary_rows
    )
    lines.extend(
        [
            "",
            "Configuration:",
            f"- seeds: {seeds}",
            f"- clients: {clients}",
            f"- rounds: {rounds}",
            f"- clip_norm: {clip_norm}",
            f"- noise_multiplier: {noise_multiplier}",
            "",
            "Results:",
            "| Dataset | FL final mean | DP final mean | Gap | DP/FL retention | Effective? |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in summary_rows:
        lines.append(
            f"| {row['dataset']} | {row['fl_final_mean']:.6f} | {row['dp_final_mean']:.6f} | "
            f"{row['final_accuracy_gap']:.6f} | {row['dp_retention_ratio']:.6f} | {row['dp_effect_preserved']} |"
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            f"- DP stayed within 90% of the FL final-accuracy baseline on {effective_count}/{len(summary_rows)} datasets.",
            "- This supports that the current DP update prototype is not only tuned to Adult Income, although performance varies by dataset.",
            "- The next useful step is to repeat the proof-gated VDP/ZK check on selected non-Adult datasets rather than only comparing FL and DP baselines.",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated FL/DP experiments across multiple tabular datasets")
    parser.add_argument("--datasets", nargs="+", default=list(DATASETS.keys()))
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62])
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for dataset_name in args.datasets:
        if dataset_name not in DATASETS:
            raise ValueError(f"Unknown dataset: {dataset_name}")
        for seed in args.seeds:
            for mode in ("fl", "dp"):
                print(f"Running dataset={dataset_name}, seed={seed}, mode={mode}")
                rows.append(
                    run_experiment(
                        dataset_name=dataset_name,
                        mode=mode,
                        seed=seed,
                        rounds=args.rounds,
                        local_epochs=args.local_epochs,
                        batch_size=args.batch_size,
                        lr=args.lr,
                        clients=args.clients,
                        clip_norm=args.clip_norm,
                        noise_multiplier=args.noise_multiplier,
                    )
                )

    summary_rows = summarize(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows, RESULTS_DIR / "multi_dataset_runs.csv")
    write_summary_csv(summary_rows, RESULTS_DIR / "multi_dataset_summary.csv")
    write_summary_md(
        summary_rows,
        RESULTS_DIR / "summary.md",
        seeds=args.seeds,
        rounds=args.rounds,
        clients=args.clients,
        clip_norm=args.clip_norm,
        noise_multiplier=args.noise_multiplier,
    )
    (RESULTS_DIR / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
