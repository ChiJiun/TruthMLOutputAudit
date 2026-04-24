"""
Shared utilities for Week 7/8 DP-FedAvg experiments.
"""
from __future__ import annotations

import copy
import csv
import json
import os
import random
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


def subtract_states(local_state: dict[str, torch.Tensor], global_state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: local_state[key] - global_state[key] for key in global_state}


def add_states(global_state: dict[str, torch.Tensor], update_state: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: global_state[key] + update_state[key] for key in global_state}


def weighted_average_states(states: list[dict[str, torch.Tensor]], weights: list[int]) -> dict[str, torch.Tensor]:
    total_weight = float(sum(weights))
    averaged: dict[str, torch.Tensor] = {}
    for key in states[0]:
        averaged[key] = sum(state[key] * (weight / total_weight) for state, weight in zip(states, weights))
    return averaged


def state_l2_norm(state: dict[str, torch.Tensor]) -> float:
    total = 0.0
    for tensor in state.values():
        total += float(torch.sum(tensor.float() ** 2).item())
    return total ** 0.5


def clip_update(update_state: dict[str, torch.Tensor], clip_norm: float) -> tuple[dict[str, torch.Tensor], float, float]:
    original_norm = state_l2_norm(update_state)
    if original_norm <= clip_norm or original_norm == 0.0:
        return {k: v.clone() for k, v in update_state.items()}, original_norm, 1.0

    scale = clip_norm / original_norm
    clipped_state = {key: tensor * scale for key, tensor in update_state.items()}
    return clipped_state, original_norm, scale


def generate_seeded_noise(
    reference_state: dict[str, torch.Tensor],
    noise_multiplier: float,
    clip_norm: float,
    seed: int,
) -> dict[str, torch.Tensor]:
    noise_std = noise_multiplier * clip_norm
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)

    noise_state: dict[str, torch.Tensor] = {}
    for key, tensor in reference_state.items():
        noise_state[key] = torch.randn(
            tensor.shape,
            generator=generator,
            dtype=tensor.dtype,
        ) * noise_std
    return noise_state


def add_state_noise(
    update_state: dict[str, torch.Tensor],
    noise_state: dict[str, torch.Tensor],
) -> dict[str, torch.Tensor]:
    return {key: update_state[key] + noise_state[key] for key in update_state}


def make_noise_seed(base_seed: int, round_idx: int, client_id: int) -> int:
    return int(base_seed + round_idx * 10_000 + client_id * 100)


def run_dp_fedavg_experiment(
    rounds: int,
    local_epochs: int,
    batch_size: int,
    lr: float,
    seed: int,
    clip_norm: float,
    noise_multiplier: float,
) -> tuple[list[dict[str, object]], dict[str, object], nn.Module]:
    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    clients = load_client_datasets()
    x_test, y_test = load_test_dataset()

    input_dim = x_test.shape[1]
    global_model = SimpleLinearModel(input_dim=input_dim).to(device)

    rows: list[dict[str, object]] = []
    initial_acc = evaluate_model(global_model, x_test, y_test, device)
    rows.append(
        {
            "round": 0,
            "test_accuracy": round(initial_acc, 6),
            "round_time_sec": 0.0,
            "mean_client_loss": "",
            "mean_update_norm": "",
            "mean_clip_scale": "",
            "mean_noise_norm": "",
            "num_clients": len(clients),
            "local_epochs": local_epochs,
            "clip_norm": clip_norm,
            "noise_multiplier": noise_multiplier,
        }
    )

    for round_idx in range(1, rounds + 1):
        round_start = time.perf_counter()
        global_state = {k: v.detach().cpu().clone() for k, v in global_model.state_dict().items()}

        dp_updates: list[dict[str, torch.Tensor]] = []
        client_sizes: list[int] = []
        local_losses: list[float] = []
        update_norms: list[float] = []
        clip_scales: list[float] = []
        noise_norms: list[float] = []

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
            update_state = subtract_states(local_state, global_state)
            clipped_state, update_norm, clip_scale = clip_update(update_state, clip_norm)
            noise_seed = make_noise_seed(seed, round_idx, client_id)
            noise_state = generate_seeded_noise(clipped_state, noise_multiplier, clip_norm, noise_seed)
            noisy_state = add_state_noise(clipped_state, noise_state)

            dp_updates.append(noisy_state)
            client_sizes.append(len(y_client))
            local_losses.append(avg_loss)
            update_norms.append(update_norm)
            clip_scales.append(clip_scale)
            noise_norms.append(state_l2_norm(noise_state))

        averaged_update = weighted_average_states(dp_updates, client_sizes)
        next_state = add_states(global_state, averaged_update)
        global_model.load_state_dict(next_state)

        round_time = time.perf_counter() - round_start
        test_acc = evaluate_model(global_model, x_test, y_test, device)
        rows.append(
            {
                "round": round_idx,
                "test_accuracy": round(test_acc, 6),
                "round_time_sec": round(round_time, 4),
                "mean_client_loss": round(float(np.mean(local_losses)), 6),
                "mean_update_norm": round(float(np.mean(update_norms)), 6),
                "mean_clip_scale": round(float(np.mean(clip_scales)), 6),
                "mean_noise_norm": round(float(np.mean(noise_norms)), 6),
                "num_clients": len(clients),
                "local_epochs": local_epochs,
                "clip_norm": clip_norm,
                "noise_multiplier": noise_multiplier,
            }
        )

    summary = {
        "initial_accuracy": rows[0]["test_accuracy"],
        "final_accuracy": rows[-1]["test_accuracy"],
        "best_accuracy": max(row["test_accuracy"] for row in rows),
        "mean_round_time_sec": round(float(np.mean([row["round_time_sec"] for row in rows[1:]])), 4),
        "clip_norm": clip_norm,
        "noise_multiplier": noise_multiplier,
        "noise_mode": "seeded_deterministic",
        "rounds": rounds,
        "clients": len(clients),
        "local_epochs": local_epochs,
        "device": str(device),
    }
    return rows, summary, global_model


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "round",
        "test_accuracy",
        "round_time_sec",
        "mean_client_loss",
        "mean_update_norm",
        "mean_clip_scale",
        "mean_noise_norm",
        "num_clients",
        "local_epochs",
        "clip_norm",
        "noise_multiplier",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
