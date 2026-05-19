"""
Week 19 - Repeat FL/DP experiments on a similar tabular binary dataset.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"


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


def load_dataset(seed: int, clients: int) -> tuple[list[tuple[np.ndarray, np.ndarray]], np.ndarray, np.ndarray]:
    x, y = load_breast_cancer(return_X_y=True)
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=seed,
        stratify=y,
    )

    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_train)
    x_test = scaler.transform(x_test)

    indices = np.arange(len(x_train))
    rng = np.random.default_rng(seed)
    rng.shuffle(indices)
    partitions = np.array_split(indices, clients)

    client_sets: list[tuple[np.ndarray, np.ndarray]] = []
    for part in partitions:
        client_sets.append((x_train[part], y_train[part]))
    return client_sets, x_test, y_test


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

    state = {k: v.detach().cpu().clone() for k, v in local_model.state_dict().items()}
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


def clip_update(update_state: dict[str, torch.Tensor], clip_norm: float) -> tuple[dict[str, torch.Tensor], float]:
    norm = state_l2_norm(update_state)
    if norm == 0.0 or norm <= clip_norm:
        return {k: v.clone() for k, v in update_state.items()}, norm
    scale = clip_norm / norm
    return {key: tensor * scale for key, tensor in update_state.items()}, norm


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
        key: torch.randn(tensor.shape, generator=generator, dtype=tensor.dtype) * noise_std
        for key, tensor in reference_state.items()
    }


def run_experiment(
    *,
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
    client_sets, x_test, y_test = load_dataset(seed=seed, clients=clients)
    global_model = SimpleLinearModel(input_dim=x_test.shape[1]).to(device)

    initial_acc = evaluate_model(global_model, x_test, y_test, device)
    round_accuracies = [initial_acc]
    round_losses: list[float] = []

    for round_idx in range(1, rounds + 1):
        global_state = {k: v.detach().cpu().clone() for k, v in global_model.state_dict().items()}
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
                clipped_state, _ = clip_update(update_state, clip_norm)
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
        "dataset": "breast_cancer_wisconsin",
        "mode": mode,
        "seed": seed,
        "clients": clients,
        "rounds": rounds,
        "initial_accuracy": round(initial_acc, 6),
        "final_accuracy": round(round_accuracies[-1], 6),
        "best_accuracy": round(max(round_accuracies), 6),
        "mean_round_loss": round(float(np.mean(round_losses)), 6),
        "input_dim": int(x_test.shape[1]),
        "test_size": int(len(y_test)),
    }


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dataset",
        "mode",
        "seed",
        "clients",
        "rounds",
        "initial_accuracy",
        "final_accuracy",
        "best_accuracy",
        "mean_round_loss",
        "input_dim",
        "test_size",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path, seeds: list[int], clip_norm: float, noise_multiplier: float) -> None:
    grouped: dict[str, list[dict[str, object]]] = {"fl": [], "dp": []}
    for row in rows:
        grouped[str(row["mode"])].append(row)

    def mean_std(metric: str, mode: str) -> tuple[float, float]:
        values = [float(row[metric]) for row in grouped[mode]]
        return float(np.mean(values)), float(np.std(values))

    fl_final_mean, fl_final_std = mean_std("final_accuracy", "fl")
    dp_final_mean, dp_final_std = mean_std("final_accuracy", "dp")
    fl_best_mean, _ = mean_std("best_accuracy", "fl")
    dp_best_mean, _ = mean_std("best_accuracy", "dp")

    lines = [
        "# Week 19 Breast Cancer Repeatability Summary",
        "",
        "Dataset:",
        "- Wisconsin Breast Cancer Diagnostic dataset from `sklearn.datasets.load_breast_cancer`",
        "- binary tabular classification, 30 features, 569 samples",
        "",
        "Configuration:",
        f"- seeds: {seeds}",
        f"- clients: {rows[0]['clients'] if rows else 3}",
        f"- rounds: {rows[0]['rounds'] if rows else 5}",
        f"- clip_norm: {clip_norm}",
        f"- noise_multiplier: {noise_multiplier}",
        "",
        "Results:",
        f"- FL final accuracy mean/std: {fl_final_mean:.6f} / {fl_final_std:.6f}",
        f"- DP final accuracy mean/std: {dp_final_mean:.6f} / {dp_final_std:.6f}",
        f"- FL best accuracy mean: {fl_best_mean:.6f}",
        f"- DP best accuracy mean: {dp_best_mean:.6f}",
        "",
        "Interpretation:",
        "- A second tabular binary dataset helps check whether the FL/DP trend observed on Adult Income is dataset-specific.",
        "- If DP remains close to the FL baseline across multiple random seeds, that supports the stability of the current prototype beyond one dataset.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run repeated FL/DP experiments on a similar tabular dataset")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62, 72, 82])
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    args = parser.parse_args()

    rows: list[dict[str, object]] = []
    for seed in args.seeds:
        for mode in ("fl", "dp"):
            rows.append(
                run_experiment(
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

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows, RESULTS_DIR / "repeat_runs.csv")
    write_summary(
        rows,
        RESULTS_DIR / "summary.md",
        seeds=args.seeds,
        clip_norm=args.clip_norm,
        noise_multiplier=args.noise_multiplier,
    )
    (RESULTS_DIR / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
