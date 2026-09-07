"""Generate reproducible context-bound randomness protocol reference-protocol threat results."""
from __future__ import annotations

import copy
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from context_bound_randomness_protocol.context_bound_randomness import (
    ReferenceCoordinator,
    build_honest_bundle,
)


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
CASES = [
    "honest",
    "replay",
    "round_swap",
    "model_swap",
    "challenge_swap",
    "zero_noise",
    "secret_swap",
    "clip_bypass",
    "noisy_tamper",
    "challenge_reissue",
]


def setup_bundle(q_clipped: list[int] | None = None):
    coordinator = ReferenceCoordinator()
    statement, witness = build_honest_bundle(
        coordinator=coordinator,
        client_id=7,
        round_id=3,
        model_hash="sha256:global-model-round-2",
        nonce="client7-round3-attempt1",
        client_secret=bytes.fromhex("11" * 32),
        update_salt=bytes.fromhex("22" * 32),
        q_clipped=q_clipped or [3, -4, 5, 1, -2, 4, -3, 2],
        server_challenge=bytes.fromhex("33" * 32),
        clip_bound_sq=100,
        noise_k=16,
        noise_unit=1,
    )
    return coordinator, statement, witness


def run_case(case: str) -> dict[str, Any]:
    expected_accept = case == "honest"
    if case == "clip_bypass":
        coordinator, statement, witness = setup_bundle([8, 8, 8, 8, 8, 8, 8, 8])
    else:
        coordinator, statement, witness = setup_bundle()
    statement = copy.deepcopy(statement)
    witness = copy.deepcopy(witness)
    first_submission_accepted: bool | None = None
    protocol_error: str | None = None

    if case == "replay":
        first_submission_accepted = coordinator.verify_reference(statement, witness)["accepted"]
    elif case == "round_swap":
        statement["round_id"] += 1
    elif case == "model_swap":
        statement["model_hash"] = "sha256:other-global-model"
    elif case == "challenge_swap":
        statement["server_challenge"] = "44" * 32
    elif case == "zero_noise":
        witness["q_noise"] = [0] * len(witness["q_noise"])
        statement["q_noisy"] = list(witness["q_clipped"])
    elif case == "secret_swap":
        witness["client_secret"] = "55" * 32
    elif case == "noisy_tamper":
        statement["q_noisy"][0] += 1
    elif case == "challenge_reissue":
        try:
            coordinator.issue_challenge(statement["commitment_id"], bytes.fromhex("66" * 32))
        except ValueError as exc:
            protocol_error = str(exc)
        return {
            "case": case,
            "expected_accept": False,
            "accepted": False,
            "matches_expectation": protocol_error is not None,
            "first_submission_accepted": None,
            "failed_checks": ["one_challenge_per_commitment"],
            "protocol_error": protocol_error,
            "public_contains_secret_or_seed": False,
        }
    elif case != "honest" and case != "clip_bypass":
        raise ValueError(case)

    decision = coordinator.verify_reference(statement, witness)
    public_text = json.dumps(statement, sort_keys=True)
    secret_hex = witness["client_secret"]
    public_contains_secret = (
        "client_secret" in statement
        or "noise_seed" in statement
        or "q_noise" in statement
        or secret_hex in public_text
    )
    return {
        "case": case,
        "expected_accept": expected_accept,
        "accepted": decision["accepted"],
        "matches_expectation": decision["accepted"] == expected_accept,
        "first_submission_accepted": first_submission_accepted,
        "failed_checks": decision["failed_checks"],
        "protocol_error": protocol_error,
        "public_contains_secret_or_seed": public_contains_secret,
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            serialized["failed_checks"] = json.dumps(row["failed_checks"], separators=(",", ":"))
            writer.writerow(serialized)


def write_summary(rows: list[dict[str, Any]], path: Path) -> None:
    lines = [
        "# context-bound randomness protocol Context-Bound Hidden-Randomness Reference 摘要",
        "",
        "## 結果",
        "",
        "| Case | Expected | Accepted | Failed checks |",
        "|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['case']} | {str(row['expected_accept']).lower()} | "
            f"{str(row['accepted']).lower()} | {', '.join(row['failed_checks']) or '-'} |"
        )
    lines.extend(
        [
            "",
            "## 判定",
            "",
            f"- Cases matching expectation：{sum(row['matches_expectation'] for row in rows)}/{len(rows)}。",
            "- Public statement 不含 client secret、derived seed 或 q_noise；verifier 只能看到 DP noisy update 與 commitments/context。",
            "- Commit-before-challenge、單一 challenge、context binding、challenge consumption 與 replay cache 共同阻止 host-level replay/context swap/adaptive retry。",
            "- Zero-noise 必須同時維持 relation，但仍因 seed-derived noise check 失敗而被拒絕。",
            "",
            "## 嚴格邊界",
            "",
            "- 這是 intended circuit relation 的 host-side reference evaluator，不是 actual ZK proof。",
            "- HMAC-SHA256/SHAKE256 與 centered-binomial sampler 尚未映射到 circuit，也尚未完成 sampler-specific DP theorem/accountant。",
            "- 因此它修復 multi-round threat matrix policy contract 的規格缺口，但尚不能宣稱已完成 finite-epsilon verifiable DP。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    rows = [run_case(case) for case in CASES]
    if not all(row["matches_expectation"] for row in rows):
        raise RuntimeError("At least one threat case did not match its expected decision")
    if any(row["public_contains_secret_or_seed"] for row in rows):
        raise RuntimeError("A public statement exposed secret randomness")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(rows, RESULTS_DIR / "reference_threat_results.csv")
    write_summary(rows, RESULTS_DIR / "summary.md")
    (RESULTS_DIR / "config.json").write_text(
        json.dumps(
            {
                "protocol": "vdp-fl-context-randomness-v1",
                "cases": CASES,
                "noise_sampler": "host-reference centered-binomial(k=16)",
                "actual_zk": False,
                "finite_epsilon_claim": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Completed {len(rows)}/{len(rows)} context/randomness threat cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
