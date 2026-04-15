"""
Week 5 - Federated Learning baseline simulator using FedAvg.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
WEEK2_DIR = ROOT_DIR / "week2_uci_model"
CLIENTS_DIR = WEEK2_DIR / "data" / "clients"
PROCESSED_DIR = WEEK2_DIR / "data" / "processed"
RESULTS_DIR = BASE_DIR / "results"
MODELS_DIR = BASE_DIR / "models"

os.chdir(BASE_DIR)


class SimpleLinearModel(nn.Module):
    def __init__(self, input_dim: int = 9):
        super().__init__()
        self.fc = nn.Linear(input_dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(x)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_client_datasets() -> list[tuple[np.ndarray, np.ndarray]]:
    metadata_path = CLIENTS_DIR / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    clients: list[tuple[np.ndarray, np.ndarray]] = []
    for client_info in metadata["clients"]:
        client_id = client_info["client_id"]
        x = np.load(CLIENTS_DIR / f"client_{client_id}_X.npy")
        y = np.load(CLIENTS_DIR / f"client_{client_id}_y.npy")
        clients.append((x, y))
    return clients


def load_test_dataset() -> tuple[np.ndarray, np.ndarray]:
    x_test = np.load(PROCESSED_DIR / "X_test.npy")
    y_test = np.load(PROCESSED_DIR / "y_test.npy")
    return x_test, y_test


def evaluate_model(model: nn.Module, x_test: np.ndarray, y_test: np.ndarray, device: torch.device) -> float:
    model.eval()
    x_t = torch.tensor(x_test, dtype=torch.float32, device=device)
    y_t = torch.tensor(y_test, dtype=torch.float32, device=device).reshape(-1, 1)

    with torch.no_grad():
        logits = model(x_t)
        preds = (torch.sigmoid(logits) > 0.5).float()
        acc = (preds == y_t).float().mean().item()
    return acc


def train_local_model(
    global_model: nn.Module,
    x_client: np.ndarray,
    y_client: np.ndarray,
    device: torch.device,
    epochs: int,
    batch_size: int,
    lr: float,
) -> tuple[dict[str, torch.Tensor], float]:
    local_model = copy.deepcopy(global_model).to(device)
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

            total_loss += loss.item()
            batches += 1

    state_dict = {k: v.detach().cpu().clone() for k, v in local_model.state_dict().items()}
    avg_loss = total_loss / max(1, batches)
    return state_dict, avg_loss


def fedavg(states: list[dict[str, torch.Tensor]], weights: list[int]) -> dict[str, torch.Tensor]:
    total_weight = float(sum(weights))
    averaged: dict[str, torch.Tensor] = {}

    for key in states[0]:
        weighted_sum = sum(state[key] * (weight / total_weight) for state, weight in zip(states, weights))
        averaged[key] = weighted_sum

    return averaged


def write_round_metrics(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "round",
        "test_accuracy",
        "round_time_sec",
        "mean_client_loss",
        "num_clients",
        "local_epochs",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, object]], output_path: Path) -> None:
    final_row = rows[-1]
    best_row = max(rows, key=lambda row: row["test_accuracy"])
    lines = [
        "# Week 5 FedAvg Summary",
        "",
        f"- Final round accuracy: round {final_row['round']} -> {final_row['test_accuracy']:.6f}",
        f"- Best accuracy: round {best_row['round']} -> {best_row['test_accuracy']:.6f}",
        f"- Mean round time: {np.mean([row['round_time_sec'] for row in rows[1:]]):.4f} sec",
        "",
        "Configuration:",
        f"- clients: {final_row['num_clients']}",
        f"- rounds: {len(rows) - 1}",
        f"- local_epochs: {final_row['local_epochs']}",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 5 FedAvg baseline")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    clients = load_client_datasets()
    x_test, y_test = load_test_dataset()

    input_dim = x_test.shape[1]
    global_model = SimpleLinearModel(input_dim=input_dim).to(device)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    initial_acc = evaluate_model(global_model, x_test, y_test, device)
    rows.append(
        {
            "round": 0,
            "test_accuracy": round(initial_acc, 6),
            "round_time_sec": 0.0,
            "mean_client_loss": "",
            "num_clients": len(clients),
            "local_epochs": args.local_epochs,
        }
    )

    print("=" * 60)
    print("Week 5 - FedAvg Simulator")
    print("=" * 60)
    print(f"Device: {device}")
    print(f"Clients: {len(clients)}, Rounds: {args.rounds}, Local Epochs: {args.local_epochs}")
    print(f"Initial test accuracy: {initial_acc:.4f}")

    for round_idx in range(1, args.rounds + 1):
        round_start = time.perf_counter()
        local_states: list[dict[str, torch.Tensor]] = []
        local_losses: list[float] = []
        client_sizes: list[int] = []

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
            local_states.append(local_state)
            local_losses.append(avg_loss)
            client_sizes.append(len(y_client))
            print(f"Round {round_idx} - Client {client_id}: loss={avg_loss:.4f}, samples={len(y_client)}")

        averaged_state = fedavg(local_states, client_sizes)
        global_model.load_state_dict(averaged_state)

        round_time = time.perf_counter() - round_start
        test_acc = evaluate_model(global_model, x_test, y_test, device)
        mean_loss = float(np.mean(local_losses))

        rows.append(
            {
                "round": round_idx,
                "test_accuracy": round(test_acc, 6),
                "round_time_sec": round(round_time, 4),
                "mean_client_loss": round(mean_loss, 6),
                "num_clients": len(clients),
                "local_epochs": args.local_epochs,
            }
        )

        print(
            f"Round {round_idx} complete: "
            f"test_accuracy={test_acc:.4f}, mean_client_loss={mean_loss:.4f}, round_time={round_time:.3f}s"
        )

    torch.save(global_model.state_dict(), MODELS_DIR / "fedavg_global_model.pt")
    write_round_metrics(rows, RESULTS_DIR / "round_metrics.csv")
    write_summary(rows, RESULTS_DIR / "summary.md")

    print(f"\nResults saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
