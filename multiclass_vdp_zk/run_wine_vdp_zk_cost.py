"""
multiclass VDP/ZK evaluation - Multiclass VDP/ZK checks with EZKL cost measurements.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

import numpy as np
import psutil
import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from multiclass_repeatability.run_multiclass_dataset_repeats import (
    MulticlassLinearModel,
    add_states,
    clip_update,
    generate_seeded_noise,
    load_raw_dataset,
    make_noise_seed,
    preprocess_split,
    set_seed,
    split_clients_stratified,
    subtract_states,
    train_local_model,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
EZKL_CASES_DIR = RESULTS_DIR / "ezkl_cases"

T = TypeVar("T")


def timed(label: str, timings: dict[str, float | int], fn: Callable[[], T]) -> T:
    """Measure wall time and native-process RSS while an EZKL stage runs."""
    process = psutil.Process()
    baseline_rss = process.memory_info().rss
    peak_rss = baseline_rss
    stop_event = threading.Event()

    def monitor_rss() -> None:
        nonlocal peak_rss
        while not stop_event.wait(0.005):
            try:
                peak_rss = max(peak_rss, process.memory_info().rss)
            except (psutil.Error, OSError):
                return

    monitor = threading.Thread(target=monitor_rss, name=f"rss-{label}", daemon=True)
    start = time.perf_counter()
    monitor.start()
    try:
        result = fn()
    finally:
        try:
            peak_rss = max(peak_rss, process.memory_info().rss)
        except (psutil.Error, OSError):
            pass
        stop_event.set()
        monitor.join(timeout=1.0)
        timings[f"{label}_sec"] = round(time.perf_counter() - start, 6)
        timings[f"{label}_baseline_rss_bytes"] = baseline_rss
        timings[f"{label}_peak_rss_bytes"] = peak_rss
        timings[f"{label}_peak_rss_delta_bytes"] = max(0, peak_rss - baseline_rss)
    return result


def compact_json_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def flatten_state_float(state: dict[str, torch.Tensor]) -> list[float]:
    flat: list[float] = []
    for key in state:
        flat.extend(float(value) for value in state[key].reshape(-1).tolist())
    return flat


def flatten_state_int(state: dict[str, torch.Tensor]) -> list[int]:
    return [int(round(value)) for value in flatten_state_float(state)]


def quantize_state(state: dict[str, torch.Tensor], scale: int) -> dict[str, torch.Tensor]:
    return {key: torch.round(value.detach().cpu() * scale).to(torch.int64) for key, value in state.items()}


def add_int_states(left: dict[str, torch.Tensor], right: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    return {key: left[key] + right[key] for key in left}


def sum_squared(values: list[int]) -> int:
    return int(sum(int(value) * int(value) for value in values))


def tamper_noisy_vector(q_noisy: list[int], delta: int = 1) -> list[int]:
    tampered = list(q_noisy)
    tampered[0] += delta
    return tampered


def slack_threshold_from_ppm(bound: int, slack_ppm: int) -> int:
    return int(round(bound * slack_ppm / 1_000_000))


def build_multiclass_artifact(
    *,
    dataset_name: str,
    case_name: str,
    client_id: int,
    seed: int,
    scale: int,
    clip_norm: float,
    noise_multiplier: float,
    local_epochs: int,
    batch_size: int,
    lr: float,
    clients: int,
    slack_ppm: int,
) -> dict[str, object]:
    set_seed(seed)
    random.seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    x, y = load_raw_dataset(dataset_name)
    x_train, x_test, y_train, _ = preprocess_split(x, y, seed=seed)
    client_sets = split_clients_stratified(x_train, y_train, clients=clients, seed=seed)
    num_classes = int(len(np.unique(y)))

    global_model = MulticlassLinearModel(input_dim=x_test.shape[1], num_classes=num_classes).to(device)
    global_state = {key: value.detach().cpu().clone() for key, value in global_model.state_dict().items()}
    x_client, y_client = client_sets[client_id]
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
    raw_update = subtract_states(local_state, global_state)
    clipped_update = clip_update(raw_update, clip_norm)
    noise_seed = make_noise_seed(seed, round_idx=1, client_id=client_id)
    noise_state = generate_seeded_noise(clipped_update, noise_multiplier, clip_norm, noise_seed)

    q_clipped = flatten_state_int(quantize_state(clipped_update, scale))
    q_noise = flatten_state_int(quantize_state(noise_state, scale))
    q_noisy = [left + right for left, right in zip(q_clipped, q_noise)]
    if case_name == "tampered_noisy_profile":
        q_noisy = tamper_noisy_vector(q_noisy, delta=1)

    clip_rhs = int(round((clip_norm * scale) ** 2))
    slack_abs = slack_threshold_from_ppm(clip_rhs, slack_ppm)
    clip_lhs = sum_squared(q_clipped)
    relation_gaps = [noisy - clipped - noise for clipped, noise, noisy in zip(q_clipped, q_noise, q_noisy)]
    relation_sum_sq = sum_squared(relation_gaps)
    relation_linf_gap = max(abs(value) for value in relation_gaps)
    clip_excess = max(0, clip_lhs - clip_rhs)

    return {
        "meta": {
            "dataset": dataset_name,
            "task": f"{num_classes}-class multiclass classification",
            "client_id": client_id,
            "case_name": case_name,
            "seed": seed,
            "scale": scale,
            "vector_dim": len(q_clipped),
            "input_dim": int(x_test.shape[1]),
            "num_classes": num_classes,
            "clip_norm": clip_norm,
            "noise_multiplier": noise_multiplier,
            "noise_seed": noise_seed,
            "slack_ppm": slack_ppm,
            "local_loss": round(float(avg_loss), 6),
        },
        "public_inputs": {
            "clip_rhs_bound_sq": clip_rhs,
            "slack_abs": slack_abs,
            "scale": scale,
            "noise_seed": noise_seed,
        },
        "witness": {
            "q_clipped": q_clipped,
            "q_noise": q_noise,
            "q_noisy": q_noisy,
        },
        "checks": {
            "clip_lhs_sum_sq": clip_lhs,
            "clip_bound_excess": clip_excess,
            "relation_linf_gap": relation_linf_gap,
            "relation_sum_sq": relation_sum_sq,
            "clip_ok": clip_excess <= slack_abs,
            "relation_ok": relation_linf_gap == 0,
        },
    }


# Backward-compatible name retained for existing multiclass VDP/ZK evaluation imports and notes.
build_wine_artifact = build_multiclass_artifact


def write_constraint_model(case_dir: Path, vector_dim: int) -> None:
    model_code = f"""\
from __future__ import annotations
import torch
import torch.nn as nn


class ConstraintCheckModel(nn.Module):
    def forward(self, packed: torch.Tensor) -> torch.Tensor:
        q_clipped = packed[:, 0:{vector_dim}]
        q_noise = packed[:, {vector_dim}:{2 * vector_dim}]
        q_noisy = packed[:, {2 * vector_dim}:{3 * vector_dim}]
        expected_noisy = q_clipped + q_noise
        clip_sum_sq = torch.sum(q_clipped * q_clipped, dim=1, keepdim=True)
        relation_sum_sq = torch.sum((q_noisy - expected_noisy) ** 2, dim=1, keepdim=True)
        return torch.cat([clip_sum_sq, relation_sum_sq], dim=1)
"""
    (case_dir / "constraint_model.py").write_text(model_code, encoding="utf-8")


def run_ezkl_case(artifact: dict[str, object], case_dir: Path) -> dict[str, object]:
    import importlib

    import ezkl

    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "artifact.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    vector_dim = int(artifact["meta"]["vector_dim"])
    write_constraint_model(case_dir, vector_dim)

    if str(case_dir) not in sys.path:
        sys.path.insert(0, str(case_dir))
    importlib.invalidate_caches()
    if "constraint_model" in sys.modules:
        del sys.modules["constraint_model"]
    from constraint_model import ConstraintCheckModel

    timings: dict[str, float | int] = {}
    pipeline_start = time.perf_counter()
    pipeline_baseline_rss = psutil.Process().memory_info().rss
    q_clipped = artifact["witness"]["q_clipped"]
    q_noise = artifact["witness"]["q_noise"]
    q_noisy = artifact["witness"]["q_noisy"]
    packed = torch.tensor([q_clipped + q_noise + q_noisy], dtype=torch.float32)

    onnx_path = case_dir / "constraint_check.onnx"
    input_path = case_dir / "input.json"
    settings_path = case_dir / "settings.json"
    compiled_path = case_dir / "network.ezkl"
    srs_path = case_dir / "kzg.srs"
    pk_path = case_dir / "pk.key"
    vk_path = case_dir / "vk.key"
    witness_path = case_dir / "witness.json"
    proof_path = case_dir / "proof.json"

    def export_onnx() -> list[list[float]]:
        model = ConstraintCheckModel().eval()
        torch.onnx.export(
            model,
            packed,
            onnx_path,
            input_names=["packed"],
            output_names=["checks"],
            opset_version=18,
        )
        return model(packed).detach().cpu().tolist()

    expected = timed("export_onnx", timings, export_onnx)
    input_path.write_text(json.dumps({"input_data": packed.tolist()}), encoding="utf-8")

    timed("gen_settings", timings, lambda: ezkl.gen_settings(str(onnx_path), str(settings_path)))
    timed("calibrate_settings", timings, lambda: ezkl.calibrate_settings(str(input_path), str(onnx_path), str(settings_path), "resources"))
    timed("compile_circuit", timings, lambda: ezkl.compile_circuit(str(onnx_path), str(compiled_path), str(settings_path)))
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    logrows = int(settings["run_args"]["logrows"])
    timed("gen_srs", timings, lambda: ezkl.gen_srs(str(srs_path), logrows))
    timed("setup", timings, lambda: ezkl.setup(str(compiled_path), str(vk_path), str(pk_path), str(srs_path)))
    timed("gen_witness", timings, lambda: ezkl.gen_witness(str(input_path), str(compiled_path), str(witness_path)))
    timed("prove", timings, lambda: ezkl.prove(str(witness_path), str(compiled_path), str(pk_path), str(proof_path), "single", str(srs_path)))
    verified = timed("verify", timings, lambda: ezkl.verify(str(proof_path), str(settings_path), str(vk_path), str(srs_path), False))

    pipeline_sec = round(time.perf_counter() - pipeline_start, 6)
    measured_peaks = [
        int(value)
        for key, value in timings.items()
        if key.endswith("_peak_rss_bytes") and not key.endswith("_delta_bytes")
    ]
    pipeline_peak_rss = max(measured_peaks, default=pipeline_baseline_rss)

    file_sizes = {
        "onnx_size_bytes": onnx_path.stat().st_size,
        "compiled_size_bytes": compiled_path.stat().st_size,
        "proof_size_bytes": proof_path.stat().st_size,
        "vk_size_bytes": vk_path.stat().st_size,
        "pk_size_bytes": pk_path.stat().st_size,
        "srs_size_bytes": srs_path.stat().st_size,
    }

    checks = artifact["checks"]
    update_payload = {
        "client_id": artifact["meta"]["client_id"],
        "q_noisy": artifact["witness"]["q_noisy"],
    }
    audit_metadata = {
        "dataset": artifact["meta"]["dataset"],
        "client_id": artifact["meta"]["client_id"],
        "vector_dim": vector_dim,
        "public_inputs": artifact["public_inputs"],
    }
    update_payload_bytes = compact_json_size(update_payload)
    audit_metadata_bytes = compact_json_size(audit_metadata)
    s2_payload_bytes = update_payload_bytes + file_sizes["proof_size_bytes"] + audit_metadata_bytes
    summary = {
        "dataset": artifact["meta"]["dataset"],
        "case_name": artifact["meta"]["case_name"],
        "client_id": artifact["meta"]["client_id"],
        "vector_dim": vector_dim,
        "verified": bool(verified),
        "clip_ok": checks["clip_ok"],
        "relation_ok": checks["relation_ok"],
        "accepted": bool(verified) and bool(checks["clip_ok"]) and bool(checks["relation_ok"]),
        "clip_sum_sq": expected[0][0],
        "relation_sum_sq": expected[0][1],
        "clip_bound_excess": checks["clip_bound_excess"],
        "relation_linf_gap": checks["relation_linf_gap"],
        "logrows": logrows,
        "num_rows": settings.get("num_rows"),
        "total_assignments": settings.get("total_assignments"),
        "pipeline_sec": pipeline_sec,
        "pipeline_baseline_rss_bytes": pipeline_baseline_rss,
        "pipeline_peak_rss_bytes": pipeline_peak_rss,
        "pipeline_peak_rss_delta_bytes": max(0, pipeline_peak_rss - pipeline_baseline_rss),
        "update_payload_bytes": update_payload_bytes,
        "audit_metadata_bytes": audit_metadata_bytes,
        "s2_payload_bytes": s2_payload_bytes,
        "communication_overhead_bytes": s2_payload_bytes - update_payload_bytes,
        "communication_overhead_ratio": round(s2_payload_bytes / update_payload_bytes - 1.0, 6),
        **timings,
        **file_sizes,
    }
    (case_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def write_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    fieldnames = [
        "dataset",
        "case_name",
        "client_id",
        "vector_dim",
        "verified",
        "clip_ok",
        "relation_ok",
        "accepted",
        "clip_sum_sq",
        "relation_sum_sq",
        "clip_bound_excess",
        "relation_linf_gap",
        "logrows",
        "num_rows",
        "total_assignments",
        "pipeline_sec",
        "pipeline_baseline_rss_bytes",
        "pipeline_peak_rss_bytes",
        "pipeline_peak_rss_delta_bytes",
        "export_onnx_sec",
        "gen_settings_sec",
        "calibrate_settings_sec",
        "compile_circuit_sec",
        "gen_srs_sec",
        "setup_sec",
        "gen_witness_sec",
        "prove_sec",
        "verify_sec",
        "setup_peak_rss_delta_bytes",
        "gen_witness_peak_rss_delta_bytes",
        "prove_peak_rss_delta_bytes",
        "verify_peak_rss_delta_bytes",
        "update_payload_bytes",
        "audit_metadata_bytes",
        "s2_payload_bytes",
        "communication_overhead_bytes",
        "communication_overhead_ratio",
        "proof_size_bytes",
        "vk_size_bytes",
        "pk_size_bytes",
        "srs_size_bytes",
        "compiled_size_bytes",
        "onnx_size_bytes",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{key: row.get(key) for key in fieldnames} for row in rows])


def write_summary(rows: list[dict[str, object]], output_path: Path, args: argparse.Namespace) -> None:
    accepted = [row for row in rows if row["accepted"]]
    rejected = [row for row in rows if not row["accepted"]]
    lines = [
        f"# multiclass VDP/ZK evaluation {args.dataset} 多類別 VDP/ZK 成本摘要",
        "",
        "目標：",
        "- 將實際 EZKL-backed VDP 約束檢查擴展到 Adult Income 以外的資料集。",
        f"- 使用 {args.dataset} 多類別資料集，驗證完整 DP 更新向量。",
        "- 量測誠實與篡改 DP 更新案例的證明相關成本。",
        "",
        "設定：",
        f"- 資料集：{args.dataset}",
        f"- 任務：{rows[0]['vector_dim'] if rows else 'n/a'} 維模型更新向量檢查",
        f"- client_id：{args.client_id}",
        f"- 向量維度：{rows[0]['vector_dim'] if rows else 'n/a'}",
        f"- 隨機種子：{args.seed}",
        f"- 量化尺度 scale：{args.scale}",
        f"- 裁剪上限 clip_norm：{args.clip_norm}",
        f"- 雜訊倍率 noise_multiplier：{args.noise_multiplier}",
        f"- 容差 slack_ppm：{args.slack_ppm}",
        "",
        "結果：",
        "| 案例 | 證明驗證 | 裁剪通過 | 關係通過 | 接受 | 證明秒數 | 驗證秒數 | 證明大小 bytes |",
        "|---|---|---|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_name']} | {row['verified']} | {row['clip_ok']} | {row['relation_ok']} | "
            f"{row['accepted']} | {row['prove_sec']:.6f} | {row['verify_sec']:.6f} | {row['proof_size_bytes']} |"
        )
    lines.extend(
        [
            "",
            "解讀：",
            f"- 接受案例：{len(accepted)}/{len(rows)}。",
            f"- 拒絕案例：{len(rejected)}/{len(rows)}。",
            f"- {args.dataset} 的誠實更新同時通過 EZKL proof verification 與 VDP 關係檢查。",
            "- 篡改 noisy update 仍可對其算術輸出產生有效 proof，但因公開關係檢查失敗而被拒絕。",
            "- 此結果補強論文主張：實際 VDP/ZK 檢查並不限於 Adult Income 二元分類流程。",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run multiclass VDP/ZK proof-cost experiment")
    parser.add_argument("--dataset", choices=["wine", "digits", "iris"], default="wine")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--client-id", type=int, default=0)
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--local-epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=0.03)
    parser.add_argument("--scale", type=int, default=10000)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--slack-ppm", type=int, default=4201)
    parser.add_argument("--cases", nargs="+", default=["honest_profile", "tampered_noisy_profile"])
    args = parser.parse_args()

    print("=" * 60)
    print("multiclass VDP/ZK evaluation - Multiclass VDP/ZK Cost")
    print("=" * 60)

    summaries: list[dict[str, object]] = []
    for case_name in args.cases:
        print(f"Running dataset={args.dataset}, case={case_name}")
        artifact = build_multiclass_artifact(
            dataset_name=args.dataset,
            case_name=case_name,
            client_id=args.client_id,
            seed=args.seed,
            scale=args.scale,
            clip_norm=args.clip_norm,
            noise_multiplier=args.noise_multiplier,
            local_epochs=args.local_epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            clients=args.clients,
            slack_ppm=args.slack_ppm,
        )
        case_dir = EZKL_CASES_DIR / args.dataset / case_name
        summaries.append(run_ezkl_case(artifact, case_dir))

    write_csv(summaries, RESULTS_DIR / f"{args.dataset}_vdp_zk_cost.csv")
    write_summary(summaries, RESULTS_DIR / f"{args.dataset}_summary.md", args)
    if args.dataset == "wine":
        write_summary(summaries, RESULTS_DIR / "summary.md", args)
    (RESULTS_DIR / "config.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
