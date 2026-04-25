"""
Week 18 - End-to-end S2 round outcome using proof-gated aggregation.
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
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
PROOF_GATED_DIR = ROOT_DIR / "week17_proof_gated_round"
ARTIFACTS_DIR = ROOT_DIR / "week14_constraint_artifacts" / "results" / "artifacts" / "scale_10000"
os.chdir(BASE_DIR)

from week7_dp_updater.dp_fedavg_core import (
    SimpleLinearModel,
    add_states,
    evaluate_model,
    load_test_dataset,
    set_seed,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_proof_gated_rows() -> list[dict[str, str]]:
    csv_path = PROOF_GATED_DIR / "results" / "proof_gated_round.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as csvfile:
        return list(csv.DictReader(csvfile))


def vector_to_state(vector: list[float], shapes: dict[str, list[int]]) -> dict[str, torch.Tensor]:
    state: dict[str, torch.Tensor] = {}
    cursor = 0
    for key, shape in shapes.items():
        size = 1
        for dim in shape:
            size *= dim
        values = vector[cursor:cursor + size]
        state[key] = torch.tensor(values, dtype=torch.float32).reshape(shape)
        cursor += size
    return state


def average_vectors(vectors: list[list[int]]) -> list[float]:
    if not vectors:
        return []
    count = len(vectors)
    return [sum(values) / count for values in zip(*vectors)]


def dequantize_vector(vector: list[float], scale: int) -> list[float]:
    return [value / scale for value in vector]


def build_case_vectors(rows: list[dict[str, str]]) -> tuple[list[list[int]], list[list[int]], dict[str, list[int]]]:
    accepted_vectors: list[list[int]] = []
    selected_vectors: list[list[int]] = []
    shapes: dict[str, list[int]] | None = None

    for row in rows:
        client_id = int(row["client_id"])
        case_name = row["case_name"]
        artifact = load_json(ARTIFACTS_DIR / f"client_{client_id}_{case_name}.json")
        selected_vectors.append(artifact["witness"]["q_noisy"])
        if row["accepted"] == "True":
            accepted_vectors.append(artifact["witness"]["q_noisy"])
        if shapes is None:
            shapes = artifact["meta"]["shapes"]

    if shapes is None:
        raise RuntimeError("No artifact shapes found.")
    return accepted_vectors, selected_vectors, shapes


def write_summary(
    output_path: Path,
    *,
    initial_accuracy: float,
    proof_gated_accuracy: float,
    ungated_accuracy: float,
    accepted_clients: int,
    total_clients: int,
) -> None:
    lines = [
        "# Week 18 End-to-End S2 Round Summary",
        "",
        f"- Initial accuracy: {initial_accuracy:.6f}",
        f"- Proof-gated next-round accuracy: {proof_gated_accuracy:.6f}",
        f"- Ungated next-round accuracy: {ungated_accuracy:.6f}",
        f"- Accepted clients: {accepted_clients}/{total_clients}",
        "",
        "Interpretation:",
        "- This round applies the proof-gated aggregate back to the global model and measures the resulting accuracy.",
        "- The ungated comparison shows what would happen if the server ignored the proof/check outcome and aggregated every submitted update.",
        "- This is the closest repo-level prototype to an end-to-end FL + VDP + ZK round outcome.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end S2 round outcome")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scale", type=int, default=10000)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 18 - End-to-End S2 Round")
    print("=" * 60)

    rows = load_proof_gated_rows()
    accepted_vectors, selected_vectors, shapes = build_case_vectors(rows)

    accepted_average_q = average_vectors(accepted_vectors)
    ungated_average_q = average_vectors(selected_vectors)
    accepted_average = dequantize_vector(accepted_average_q, args.scale)
    ungated_average = dequantize_vector(ungated_average_q, args.scale)

    accepted_update_state = vector_to_state(accepted_average, shapes)
    ungated_update_state = vector_to_state(ungated_average, shapes)

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    x_test, y_test = load_test_dataset()
    global_model = SimpleLinearModel(input_dim=x_test.shape[1]).to(device)
    global_state = {key: tensor.detach().cpu().clone() for key, tensor in global_model.state_dict().items()}

    initial_accuracy = evaluate_model(global_model, x_test, y_test, device)

    proof_gated_model = SimpleLinearModel(input_dim=x_test.shape[1]).to(device)
    proof_gated_model.load_state_dict(add_states(global_state, accepted_update_state))
    proof_gated_accuracy = evaluate_model(proof_gated_model, x_test, y_test, device)

    ungated_model = SimpleLinearModel(input_dim=x_test.shape[1]).to(device)
    ungated_model.load_state_dict(add_states(global_state, ungated_update_state))
    ungated_accuracy = evaluate_model(ungated_model, x_test, y_test, device)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "accepted_average_q_noisy.json").write_text(
        json.dumps({"accepted_average_q_noisy": accepted_average_q}, indent=2),
        encoding="utf-8",
    )
    (RESULTS_DIR / "ungated_average_q_noisy.json").write_text(
        json.dumps({"ungated_average_q_noisy": ungated_average_q}, indent=2),
        encoding="utf-8",
    )
    write_summary(
        RESULTS_DIR / "summary.md",
        initial_accuracy=initial_accuracy,
        proof_gated_accuracy=proof_gated_accuracy,
        ungated_accuracy=ungated_accuracy,
        accepted_clients=len(accepted_vectors),
        total_clients=len(selected_vectors),
    )

    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
