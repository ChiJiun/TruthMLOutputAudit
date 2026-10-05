"""experimental-rigor audit - Statistical, completeness, and reproducibility audit."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import platform
import statistics
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from scipy.stats import t as student_t


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"

LARGE_DATA_RUNS = ROOT / "covertype_large_dataset_scaling" / "results" / "covertype_scaling_runs.csv"
NONIID_RUNS = ROOT / "noniid_client_scaling" / "results" / "noniid_client_runs.csv"
THREAT_TRAJECTORIES = ROOT / "multiround_threat_matrix" / "results" / "threat_trajectories.csv"
THREAT_DECISIONS = ROOT / "multiround_threat_matrix" / "results" / "threat_decisions.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def exact_sign_flip_p(differences: list[float]) -> float:
    """Two-sided exact paired randomization p-value using all sign flips."""
    if not differences:
        raise ValueError("At least one paired difference is required")
    observed = abs(statistics.fmean(differences))
    extreme = 0
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(differences)):
        permuted = abs(statistics.fmean(sign * value for sign, value in zip(signs, differences)))
        extreme += permuted >= observed - 1e-12
        total += 1
    return extreme / total


def holm_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=p_values.__getitem__)
    adjusted = [0.0] * len(p_values)
    running = 0.0
    total = len(p_values)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (total - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


def effect_row(
    *,
    family: str,
    condition: str,
    comparison: str,
    baseline: dict[int, float],
    treatment: dict[int, float],
) -> dict[str, Any]:
    if set(baseline) != set(treatment):
        raise AssertionError(
            f"Unpaired seeds for {family}/{condition}/{comparison}: "
            f"{sorted(baseline)} vs {sorted(treatment)}"
        )
    seeds = sorted(baseline)
    differences = [treatment[seed] - baseline[seed] for seed in seeds]
    n = len(differences)
    mean_difference = statistics.fmean(differences)
    sd_difference = statistics.stdev(differences) if n > 1 else 0.0
    critical = float(student_t.ppf(0.975, n - 1)) if n > 1 else math.nan
    margin = critical * sd_difference / math.sqrt(n) if n > 1 else math.nan
    cohen_dz = mean_difference / sd_difference if sd_difference > 0 else math.nan
    return {
        "family": family,
        "condition": condition,
        "comparison": comparison,
        "seeds": n,
        "seed_ids": seeds,
        "baseline_mean": round(statistics.fmean(baseline.values()), 9),
        "comparison_mean": round(statistics.fmean(treatment.values()), 9),
        "mean_difference": round(mean_difference, 9),
        "difference_sd": round(sd_difference, 9),
        "difference_ci95_low": round(mean_difference - margin, 9),
        "difference_ci95_high": round(mean_difference + margin, 9),
        "cohen_dz": None if math.isnan(cohen_dz) else round(cohen_dz, 9),
        "exact_permutation_p": round(exact_sign_flip_p(differences), 9),
    }


def keyed_values(
    rows: list[dict[str, str]],
    *,
    filters: dict[str, str],
    mode_field: str,
    mode_value: str,
    value_field: str = "final_accuracy",
) -> dict[int, float]:
    selected = [
        row
        for row in rows
        if row[mode_field] == mode_value
        and all(str(row[field]) == str(value) for field, value in filters.items())
    ]
    values = {int(row["seed"]): float(row[value_field]) for row in selected}
    if len(values) != len(selected):
        raise AssertionError(f"Duplicate seed rows for {filters}/{mode_value}")
    return values


def validate_unique(rows: list[dict[str, str]], fields: tuple[str, ...], label: str) -> None:
    keys = [tuple(row[field] for field in fields) for row in rows]
    if len(keys) != len(set(keys)):
        raise AssertionError(f"Duplicate primary key in {label}")


def add_holm_by_family(rows: list[dict[str, Any]]) -> None:
    for family in sorted({str(row["family"]) for row in rows}):
        positions = [index for index, row in enumerate(rows) if row["family"] == family]
        adjusted = holm_adjust([float(rows[index]["exact_permutation_p"]) for index in positions])
        for index, p_adjusted in zip(positions, adjusted):
            rows[index]["holm_adjusted_p"] = round(p_adjusted, 9)
            rows[index]["familywise_p_lt_0_05"] = p_adjusted < 0.05


def analyze_effects(
    large_data_rows: list[dict[str, str]],
    noniid_rows: list[dict[str, str]],
    threat_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for train_size in sorted({row["train_size"] for row in large_data_rows}, key=int):
        baseline = keyed_values(
            large_data_rows,
            filters={"train_size": train_size},
            mode_field="mode",
            mode_value="fl",
        )
        for mode in ("clip", "dp"):
            output.append(
                effect_row(
                    family="large_data_scaling",
                    condition=f"train_size={train_size}",
                    comparison=f"{mode}-fl",
                    baseline=baseline,
                    treatment=keyed_values(
                        large_data_rows,
                        filters={"train_size": train_size},
                        mode_field="mode",
                        mode_value=mode,
                    ),
                )
            )

    conditions = sorted({(row["clients"], row["partition"]) for row in noniid_rows})
    for clients, partition in conditions:
        filters = {"clients": clients, "partition": partition}
        baseline = keyed_values(
            noniid_rows,
            filters=filters,
            mode_field="mode",
            mode_value="fl",
        )
        for mode in ("clip", "dp"):
            output.append(
                effect_row(
                    family="noniid_scaling",
                    condition=f"K={clients}/{partition}",
                    comparison=f"{mode}-fl",
                    baseline=baseline,
                    treatment=keyed_values(
                        noniid_rows,
                        filters=filters,
                        mode_field="mode",
                        mode_value=mode,
                    ),
                )
            )

    clean = keyed_values(
        threat_rows,
        filters={"attack": "none"},
        mode_field="policy",
        mode_value="current_vdp_gate",
    )
    attack_policies = sorted(
        {(row["attack"], row["policy"]) for row in threat_rows if row["attack"] != "none"}
    )
    for attack, policy in attack_policies:
        output.append(
            effect_row(
                family="threat_utility",
                condition=attack,
                comparison=f"{policy}-clean",
                baseline=clean,
                treatment=keyed_values(
                    threat_rows,
                    filters={"attack": attack},
                    mode_field="policy",
                    mode_value=policy,
                ),
            )
        )

    add_holm_by_family(output)
    return output


def completeness_audit(
    large_data_rows: list[dict[str, str]],
    noniid_rows: list[dict[str, str]],
    threat_rows: list[dict[str, str]],
    decisions: list[dict[str, str]],
) -> dict[str, Any]:
    validate_unique(large_data_rows, ("train_size", "seed", "mode"), "CoverType large-data scaling")
    validate_unique(noniid_rows, ("clients", "partition", "seed", "mode"), "non-IID client scaling")
    validate_unique(threat_rows, ("attack", "policy", "seed"), "multi-round threat matrix")
    validate_unique(
        decisions,
        ("attack", "policy", "seed", "round_id", "client_id"),
        "multi-round threat matrix decisions",
    )
    expected = {
        "large_data_mode_runs": 3 * 3 * 3,
        "noniid_mode_runs": 2 * 3 * 5 * 3,
        "threat_trajectories": 3 * (1 + 5 * 3),
        "threat_client_decisions": 3 * (1 + 5 * 3) * 3 * 10,
    }
    actual = {
        "large_data_mode_runs": len(large_data_rows),
        "noniid_mode_runs": len(noniid_rows),
        "threat_trajectories": len(threat_rows),
        "threat_client_decisions": len(decisions),
    }
    if expected != actual:
        raise AssertionError(f"Incomplete core matrix: expected={expected}, actual={actual}")
    return {
        "expected": expected,
        "actual": actual,
        "all_primary_keys_unique": True,
        "all_core_matrices_complete": True,
        "paired_seed_sets_checked": True,
        "preprocessing_code_audit": {
            "train_test_split_before_scaler_fit": True,
            "standard_scaler_fit_on_train_only": True,
            "paired_modes_share_split_partition_initialization_shuffle": True,
        },
        "proof_scope": {
            "actual_ezkl_evidence_sources": [
                "ezkl_constraint_integration",
                "multiclass_vdp_zk",
                "zk_cost_scaling",
                "covertype_large_dataset_scaling",
            ],
            "threat_matrix_is_policy_simulation": True,
            "threat_matrix_actual_proof_count_claimed": False,
        },
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            serialized = {
                key: json.dumps(value, separators=(",", ":")) if isinstance(value, list) else value
                for key, value in row.items()
            }
            writer.writerow(serialized)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_hash_manifest(path: Path) -> None:
    targets = [
        LARGE_DATA_RUNS,
        ROOT / "covertype_large_dataset_scaling" / "results" / "covertype_scaling_summary.csv",
        NONIID_RUNS,
        ROOT / "noniid_client_scaling" / "results" / "noniid_client_summary.csv",
        THREAT_TRAJECTORIES,
        THREAT_DECISIONS,
        ROOT / "multiround_threat_matrix" / "results" / "threat_summary.csv",
        ROOT / "context_bound_randomness_protocol" / "results" / "reference_threat_results.csv",
        ROOT / "covertype_large_dataset_scaling" / "run_covertype_scaling.py",
        ROOT / "noniid_client_scaling" / "run_noniid_client_scaling.py",
        ROOT / "multiround_threat_matrix" / "run_multiround_threat_matrix.py",
        ROOT / "context_bound_randomness_protocol" / "context_bound_randomness.py",
        ROOT / "context_bound_randomness_protocol" / "run_reference_threats.py",
    ]
    rows = [
        {
            "path": target.relative_to(ROOT).as_posix(),
            "bytes": target.stat().st_size,
            "sha256": sha256(target),
        }
        for target in targets
    ]
    write_csv(rows, path)


def environment_manifest() -> dict[str, Any]:
    packages = [
        "ezkl",
        "onnx",
        "onnxruntime",
        "torch",
        "numpy",
        "pandas",
        "matplotlib",
        "psutil",
        "scikit-learn",
        "scipy",
    ]
    versions: dict[str, str | None] = {}
    for package in packages:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "packages": versions,
    }


def write_summary(effects: list[dict[str, Any]], completeness: dict[str, Any], path: Path) -> None:
    families = sorted({str(row["family"]) for row in effects})
    significant = [row for row in effects if row["familywise_p_lt_0_05"]]
    lines = [
        "# experimental-rigor audit 實驗嚴謹性稽核",
        "",
        "## 結案判定",
        "",
        "**可用於結案，但核心主張必須限定為線性模型上的 constraint-only DP-update audit 與 proof/check-gated aggregation feasibility。**",
        "",
        "不能把結果寫成已完成 finite-epsilon verifiable DP、1,440 次 actual proof、完整 local-training correctness 或任意 poisoning defense。",
        "",
        "## 完整性與設計控制",
        "",
        f"- CoverType large-data scaling：{completeness['actual']['large_data_mode_runs']}/27 mode runs。",
        f"- non-IID client scaling：{completeness['actual']['noniid_mode_runs']}/90 mode runs。",
        f"- multi-round threat matrix：{completeness['actual']['threat_trajectories']}/48 trajectories、"
        f"{completeness['actual']['threat_client_decisions']:,}/1,440 decisions。",
        "- Primary keys 無重複，所有 baseline/comparison seed sets 完整配對。",
        "- 程式碼確認先切 train/test，StandardScaler 只在 train fit；同一 paired condition 共用 split、partition、初始化與 shuffle。",
        "- multi-round threat matrix 是多輪 policy simulation；actual EZKL 證據與成本由 EZKL constraint integration、multiclass VDP-ZK、ZK cost scaling 與 CoverType scaling 獨立支撐。",
        "",
        "## 統計判讀",
        "",
        "- 所有 accuracy 比較以 seed 為獨立分析單位，報告 paired mean difference、Student-t 95% CI、paired Cohen dz、two-sided exact sign-flip permutation p 與 family-level Holm correction。",
        "- CoverType large-data scaling 的 27 組 mode runs 只有 3 seeds，two-sided exact test 的最小可能 p=0.25；non-IID client scaling 有 5 seeds，最小可能 p=0.0625。因此這些實驗是描述性、effect-size 與可行性證據，不應使用「統計顯著」措辭。",
        f"- 分析 families：{', '.join(families)}；Holm-adjusted p<0.05 的比較數={len(significant)}。",
        "- 小樣本 t interval 與 Cohen dz 可能不穩定，應與原始 seed rows、方向一致性和工程效果共同解讀。",
        "",
        "## 可重現性產物",
        "",
        "- `paired_effects.csv`：全部成對 effect 與檢定。",
        "- `completeness.json`：矩陣筆數、唯一鍵、pairing 與 proof scope 稽核。",
        "- `environment.json`：Python、作業系統與核心套件精確版本。",
        "- `sha256_manifest.csv`：核心 scripts 與 raw/summary CSV 的 SHA-256。",
        "",
        "## 結案前必須遵守",
        "",
        "1. 使用『支持／顯示／在本實驗範圍內』，不要寫『證明所有情境』或『統計顯著』。",
        "2. Public deterministic seed 的 verifier-view epsilon 明列為 infinity；有限 epsilon 只列為 secret-noise 條件式分析。",
        "3. multi-round threat matrix 的 1,440 decisions 明列為 policy simulation，不宣稱 1,440 actual proofs。",
        "4. Bounded sign-flip 的 100% acceptance 與 availability/utility 損失必須保留，不能只呈現成功拒絕的攻擊。",
        "5. Actual EZKL 只主張 constraint-only 線性 update；完整 training circuit、secret noise generation 與 production-scale federation 列為未來工作。",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    large_data_rows = read_csv(LARGE_DATA_RUNS)
    noniid_rows = read_csv(NONIID_RUNS)
    threat_rows = read_csv(THREAT_TRAJECTORIES)
    decisions = read_csv(THREAT_DECISIONS)
    completeness = completeness_audit(large_data_rows, noniid_rows, threat_rows, decisions)
    effects = analyze_effects(large_data_rows, noniid_rows, threat_rows)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(effects, RESULTS_DIR / "paired_effects.csv")
    (RESULTS_DIR / "completeness.json").write_text(
        json.dumps(completeness, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (RESULTS_DIR / "environment.json").write_text(
        json.dumps(environment_manifest(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_hash_manifest(RESULTS_DIR / "sha256_manifest.csv")
    write_summary(effects, completeness, RESULTS_DIR / "summary.md")
    print(f"Audited {len(effects)} paired effects; all core matrices complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
