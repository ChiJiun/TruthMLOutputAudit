"""
multiclass repeatability - Repeat FL/DP experiments on non-binary multiclass datasets.
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
from sklearn.datasets import fetch_covtype, load_digits, load_iris, load_wine
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"

DATASETS = {
    "iris": {"loader": load_iris, "description": "3-class flower classification"},
    "wine": {"loader": load_wine, "description": "3-class wine cultivar classification"},
    "digits": {"loader": load_digits, "description": "10-class handwritten digit classification"},
}


class MulticlassLinearModel(nn.Module):
    def __init__(self, input_dim: int, num_classes: int) -> None:
        super().__init__()
        self.fc = nn.Linear(input_dim, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(x)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_raw_dataset(dataset_name: str) -> tuple[np.ndarray, np.ndarray]:
    if dataset_name == "covertype":
        data, target = fetch_covtype(return_X_y=True)
        return data.astype(np.float32), (target.astype(np.int64) - 1)
    dataset = DATASETS[dataset_name]["loader"]()
    return dataset.data.astype(np.float32), dataset.target.astype(np.int64)


def preprocess_split(
    x: np.ndarray,
    y: np.ndarray,
    *,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=seed,
        stratify=y,
    )
    scaler = StandardScaler()
    x_train = scaler.fit_transform(x_train).astype(np.float32)
    x_test = scaler.transform(x_test).astype(np.float32)
    return x_train, x_test, y_train.astype(np.int64), y_test.astype(np.int64)


def split_clients_stratified(
    x_train: np.ndarray,
    y_train: np.ndarray,
    clients: int,
    seed: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    client_indices: list[list[int]] = [[] for _ in range(clients)]

    for class_label in np.unique(y_train):
        class_indices = np.where(y_train == class_label)[0]
        rng.shuffle(class_indices)
        for offset, index in enumerate(class_indices):
            client_indices[offset % clients].append(int(index))

    client_sets: list[tuple[np.ndarray, np.ndarray]] = []
    for indices in client_indices:
        rng.shuffle(indices)
        idx = np.array(indices, dtype=np.int64)
        client_sets.append((x_train[idx], y_train[idx]))
    return client_sets


def evaluate_model(model: nn.Module, x_test: np.ndarray, y_test: np.ndarray, device: torch.device) -> float:
    model.eval()
    x_t = torch.tensor(x_test, dtype=torch.float32, device=device)
    y_t = torch.tensor(y_test, dtype=torch.long, device=device)
    with torch.no_grad():
        preds = torch.argmax(model(x_t), dim=1)
        return float((preds == y_t).float().mean().item())


def train_local_model(
    global_model: nn.Module,
    x_client: np.ndarray,
    y_client: np.ndarray,
    *,
    input_dim: int,
    num_classes: int,
    device: torch.device,
    epochs: int,
    batch_size: int,
    lr: float,
) -> tuple[dict[str, torch.Tensor], float]:
    local_model = MulticlassLinearModel(input_dim=input_dim, num_classes=num_classes).to(device)
    local_model.load_state_dict(global_model.state_dict())
    local_model.train()

    dataset = TensorDataset(
        torch.tensor(x_client, dtype=torch.float32),
        torch.tensor(y_client, dtype=torch.long),
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(local_model.parameters(), lr=lr)

    total_loss = 0.0
    batches = 0
    for _ in range(epochs):
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            optimizer.zero_grad()
            loss = criterion(local_model(batch_x), batch_y)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item())
            batches += 1

    return {k: v.detach().cpu().clone() for k, v in local_model.state_dict().items()}, total_loss / max(1, batches)


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
    return float(sum(torch.sum(tensor.float() ** 2).item() for tensor in state.values()) ** 0.5)


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
    x, y = load_raw_dataset(dataset_name)
    x_train, x_test, y_train, y_test = preprocess_split(x, y, seed=seed)
    client_sets = split_clients_stratified(x_train, y_train, clients=clients, seed=seed)
    num_classes = int(len(np.unique(y)))

    global_model = MulticlassLinearModel(input_dim=x_test.shape[1], num_classes=num_classes).to(device)
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
                global_model,
                x_client,
                y_client,
                input_dim=x_test.shape[1],
                num_classes=num_classes,
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
        "num_classes": num_classes,
        "test_size": int(len(y_test)),
        "initial_accuracy": round(initial_acc, 6),
        "final_accuracy": round(round_accuracies[-1], 6),
        "best_accuracy": round(max(round_accuracies), 6),
        "mean_round_loss": round(float(np.mean(round_losses)), 6),
    }


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    fieldnames = [
        "dataset",
        "mode",
        "seed",
        "clients",
        "rounds",
        "samples",
        "input_dim",
        "num_classes",
        "test_size",
        "initial_accuracy",
        "final_accuracy",
        "best_accuracy",
        "mean_round_loss",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary_rows: list[dict[str, object]] = []
    for dataset in sorted({str(row["dataset"]) for row in rows}):
        dataset_rows = [row for row in rows if row["dataset"] == dataset]
        fl_rows = [row for row in dataset_rows if row["mode"] == "fl"]
        dp_rows = [row for row in dataset_rows if row["mode"] == "dp"]
        fl_final = np.array([float(row["final_accuracy"]) for row in fl_rows])
        dp_final = np.array([float(row["final_accuracy"]) for row in dp_rows])
        fl_best = np.array([float(row["best_accuracy"]) for row in fl_rows])
        dp_best = np.array([float(row["best_accuracy"]) for row in dp_rows])
        retention = float(np.mean(dp_final) / max(1e-9, np.mean(fl_final)))
        summary_rows.append(
            {
                "dataset": dataset,
                "description": DATASETS[dataset]["description"],
                "samples": int(dataset_rows[0]["samples"]),
                "input_dim": int(dataset_rows[0]["input_dim"]),
                "num_classes": int(dataset_rows[0]["num_classes"]),
                "fl_final_mean": round(float(np.mean(fl_final)), 6),
                "fl_final_std": round(float(np.std(fl_final)), 6),
                "dp_final_mean": round(float(np.mean(dp_final)), 6),
                "dp_final_std": round(float(np.std(dp_final)), 6),
                "final_accuracy_gap": round(float(np.mean(fl_final) - np.mean(dp_final)), 6),
                "dp_retention_ratio": round(retention, 6),
                "fl_best_mean": round(float(np.mean(fl_best)), 6),
                "dp_best_mean": round(float(np.mean(dp_best)), 6),
                "dp_effect_preserved": retention >= 0.9,
            }
        )
    return summary_rows


def write_summary_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    fieldnames = [
        "dataset",
        "description",
        "samples",
        "input_dim",
        "num_classes",
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
        "# multiclass repeatability 多類別資料集重複實驗摘要",
        "",
        "目標：",
        "- 將 FL/DP 重複實驗從二元分類擴展到非二元的多類別資料集。",
        "- 檢查模型輸出層與損失函數改為多類別設定後，DP 更新是否仍接近 FL 基準。",
        "",
        "設定：",
        f"- 隨機種子：{seeds}",
        f"- 客戶端數量：{clients}",
        f"- 訓練輪數：{rounds}",
        f"- 裁剪上限 clip_norm：{clip_norm}",
        f"- 雜訊倍率 noise_multiplier：{noise_multiplier}",
        "",
        "資料集：",
    ]
    lines.extend(
        f"- {row['dataset']}：{row['description']}，樣本數={row['samples']}，"
        f"類別數={row['num_classes']}，特徵數={row['input_dim']}"
        for row in summary_rows
    )
    lines.extend(
        [
            "",
            "結果：",
            "| 資料集 | 類別數 | FL 最終平均 | DP 最終平均 | 差距 | DP/FL 保留率 | 是否達標 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in summary_rows:
        lines.append(
            f"| {row['dataset']} | {row['num_classes']} | {row['fl_final_mean']:.6f} | "
            f"{row['dp_final_mean']:.6f} | {row['final_accuracy_gap']:.6f} | "
            f"{row['dp_retention_ratio']:.6f} | {row['dp_effect_preserved']} |"
        )
    lines.extend(
        [
            "",
            "解讀：",
            f"- DP 在 {effective_count}/{len(summary_rows)} 個多類別資料集上維持 FL 最終準確率基準的 90% 以上。",
            "- 這是基準層級的多類別擴展：目前檢查 FL/DP 在多類別輸出上的行為，尚未對這些新資料集產生完整 EZKL 證明。",
            "- 若未來有資料集低於門檻，下一步應針對訓練輪數、clip_norm 與 noise_multiplier 進行參數掃描。",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FL/DP experiments on multiclass datasets")
    parser.add_argument("--datasets", nargs="+", default=list(DATASETS.keys()))
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 52, 62])
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--local-epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.03)
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
    write_csv(rows, RESULTS_DIR / "multiclass_runs.csv")
    write_summary_csv(summary_rows, RESULTS_DIR / "multiclass_summary.csv")
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
