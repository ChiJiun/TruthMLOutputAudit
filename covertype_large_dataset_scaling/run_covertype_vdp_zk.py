"""Generate honest/tampered actual EZKL VDP checks for a CoverType update."""
from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from multiclass_vdp_zk.run_wine_vdp_zk_cost import (
    build_multiclass_artifact,
    run_ezkl_case,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
DEFAULT_ARTIFACTS_DIR = (
    ROOT_DIR
    / "multiclass_vdp_zk"
    / "results"
    / "ezkl_cases"
    / "covertype_profile"
)


def make_tampered(honest: dict[str, Any]) -> dict[str, Any]:
    tampered = copy.deepcopy(honest)
    tampered["meta"]["case_name"] = "tampered_noisy_profile"
    tampered["witness"]["q_noisy"][0] += 1
    clipped = tampered["witness"]["q_clipped"]
    noise = tampered["witness"]["q_noise"]
    noisy = tampered["witness"]["q_noisy"]
    gaps = [c + n - observed for c, n, observed in zip(clipped, noise, noisy)]
    tampered["checks"]["relation_linf_gap"] = max(abs(value) for value in gaps)
    tampered["checks"]["relation_sum_sq"] = sum(value * value for value in gaps)
    tampered["checks"]["relation_ok"] = False
    return tampered


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "dataset", "case_name", "vector_dim", "verified", "clip_ok", "relation_ok",
        "accepted", "pipeline_sec", "prove_sec", "verify_sec", "pipeline_peak_rss_bytes",
        "proof_size_bytes", "pk_size_bytes", "srs_size_bytes", "num_rows",
        "total_assignments", "update_payload_bytes", "s2_payload_bytes",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field) for field in fields} for row in rows])


def write_summary(rows: list[dict[str, Any]], path: Path, args: argparse.Namespace) -> None:
    lines = [
        "# CoverType large-data scaling CoverType actual EZKL VDP 摘要",
        "",
        "- 資料集：Forest CoverType，581,012 筆、54 特徵、7 類別。",
        f"- Seed={args.seed}；clients={args.clients}；client_id={args.client_id}。",
        f"- 完整線性模型更新向量：{rows[0]['vector_dim']} 維。",
        f"- scale={args.scale}；clip_norm={args.clip_norm}；noise_multiplier={args.noise_multiplier}；slack_ppm={args.slack_ppm}。",
        "",
        "| Case | Proof verified | Clip OK | Relation OK | Accepted | Prove sec | Verify sec | Proof bytes | Peak RSS MiB |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_name']} | {row['verified']} | {row['clip_ok']} | {row['relation_ok']} | "
            f"{row['accepted']} | {row['prove_sec']:.6f} | {row['verify_sec']:.6f} | "
            f"{row['proof_size_bytes']} | {row['pipeline_peak_rss_bytes'] / (1024 * 1024):.1f} |"
        )
    lines.extend(
        [
            "",
            "解讀：",
            "- Honest update 必須同時通過 proof、clipping 與 additive relation。",
            "- Tampered update 對 q_noisy 偏移 1 個量化單位；其 proof 可驗證算術輸出，但 relation policy 失敗，因此 aggregation gate 拒絕。",
            "- 這證明 S2 constraint/check 可套用至由完整大型資料集產生的 385 維 client update。",
            "- Proof 電路仍只驗證 update constraint，不會因訓練樣本數增加而包含整個 local training trace。",
            "- EZKL calibration 曾輸出大型 lookup input 警告；兩個案例仍完成 compile/prove/verify，但此警告應列為量化與工具鏈風險。",
            "- Public noise seed 的 epsilon infinity 限制不變。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CoverType actual EZKL VDP checks")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--client-id", type=int, default=0)
    parser.add_argument("--clients", type=int, default=3)
    parser.add_argument("--local-epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--scale", type=int, default=10000)
    parser.add_argument("--clip-norm", type=float, default=1.0)
    parser.add_argument("--noise-multiplier", type=float, default=0.08)
    parser.add_argument("--slack-ppm", type=int, default=4201)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    args = parser.parse_args()

    honest = build_multiclass_artifact(
        dataset_name="covertype",
        case_name="honest_profile",
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
    cases = [honest, make_tampered(honest)]
    rows = [
        run_ezkl_case(case, args.artifacts_dir / str(case["meta"]["case_name"]))
        for case in cases
    ]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows, RESULTS_DIR / "covertype_vdp_zk_cost.csv")
    write_summary(rows, RESULTS_DIR / "covertype_vdp_zk_summary.md", args)
    (RESULTS_DIR / "covertype_vdp_zk_config.json").write_text(
        json.dumps({**vars(args), "artifacts_dir": str(args.artifacts_dir)}, indent=2),
        encoding="utf-8",
    )
    print(f"CoverType VDP/ZK accepted={sum(bool(row['accepted']) for row in rows)}/{len(rows)}")
    return 0 if rows[0]["accepted"] and not rows[1]["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
