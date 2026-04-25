"""
Week 17 - Actual proof-gated round using EZKL-backed client checks.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from pathlib import Path

import torch

ROOT_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
DEMO_DIR = BASE_DIR / "ezkl_client_checks"
ARTIFACTS_DIR = ROOT_DIR / "week14_constraint_artifacts" / "results" / "artifacts" / "scale_10000"
os.chdir(BASE_DIR)


CHECK_MODEL_CODE = """\
from __future__ import annotations
import torch
import torch.nn as nn

class ConstraintCheckModel(nn.Module):
    def forward(self, packed: torch.Tensor) -> torch.Tensor:
        q_clipped = packed[:, 0:10]
        q_noise = packed[:, 10:20]
        q_noisy = packed[:, 20:30]
        expected_noisy = q_clipped + q_noise
        clip_sum_sq = torch.sum(q_clipped * q_clipped, dim=1, keepdim=True)
        relation_sum_sq = torch.sum((q_noisy - expected_noisy) ** 2, dim=1, keepdim=True)
        return torch.cat([clip_sum_sq, relation_sum_sq], dim=1)
"""


EXPORT_MODEL_CODE = """\
from __future__ import annotations
import json
from pathlib import Path
import torch
from constraint_model import ConstraintCheckModel

base = Path(__file__).resolve().parent
artifact = json.loads((base / "artifact.json").read_text(encoding="utf-8"))
packed = torch.tensor([artifact["witness"]["q_clipped"] + artifact["witness"]["q_noise"] + artifact["witness"]["q_noisy"]], dtype=torch.float32)

model = ConstraintCheckModel().eval()
torch.onnx.export(
    model,
    packed,
    base / "constraint_check.onnx",
    input_names=["packed"],
    output_names=["checks"],
    opset_version=18,
)
"""


PIPELINE_CODE = """\
from __future__ import annotations
import json
from pathlib import Path
import torch
import ezkl
from constraint_model import ConstraintCheckModel

base = Path(__file__).resolve().parent
artifact = json.loads((base / "artifact.json").read_text(encoding="utf-8"))
public = artifact["public_inputs"]
checks = artifact["checks"]

packed = torch.tensor([artifact["witness"]["q_clipped"] + artifact["witness"]["q_noise"] + artifact["witness"]["q_noisy"]], dtype=torch.float32)
model = ConstraintCheckModel().eval()
expected = model(packed).detach().cpu().tolist()

(base / "input.json").write_text(json.dumps({"input_data": packed.tolist()}), encoding="utf-8")

onnx_path = base / "constraint_check.onnx"
settings = base / "settings.json"
compiled = base / "network.ezkl"
srs = base / "kzg.srs"
pk = base / "pk.key"
vk = base / "vk.key"
witness = base / "witness.json"
proof = base / "proof.json"

ezkl.gen_settings(str(onnx_path), str(settings))
ezkl.calibrate_settings(str(base / "input.json"), str(onnx_path), str(settings), "resources")
ezkl.compile_circuit(str(onnx_path), str(compiled), str(settings))
logrows = json.loads(settings.read_text(encoding="utf-8"))["run_args"]["logrows"]
ezkl.gen_srs(str(srs), logrows)
ezkl.setup(str(compiled), str(vk), str(pk), str(srs))
ezkl.gen_witness(str(base / "input.json"), str(compiled), str(witness))
ezkl.prove(str(witness), str(compiled), str(pk), str(proof), "single", str(srs))
verified = ezkl.verify(str(proof), str(settings), str(vk), str(srs), False)

summary = {
    "verified": bool(verified),
    "clip_sum_sq": expected[0][0],
    "relation_sum_sq": expected[0][1],
    "clip_rhs_bound_sq": public["clip_rhs_bound_sq"],
    "slack_abs": public["slack_abs"],
    "clip_ok": checks["clip_ok"],
    "relation_ok": checks["relation_ok"],
}
(base / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary))
"""


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prepare_case_dir(client_id: int, case_name: str) -> Path:
    case_dir = DEMO_DIR / f"client_{client_id}_{case_name}"
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "constraint_model.py").write_text(CHECK_MODEL_CODE, encoding="utf-8")
    (case_dir / "export_model.py").write_text(EXPORT_MODEL_CODE, encoding="utf-8")
    (case_dir / "pipeline.py").write_text(PIPELINE_CODE, encoding="utf-8")
    return case_dir


def run_conda_python(script_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["conda", "run", "-n", "zkML", "python", str(script_path)],
        cwd=script_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def run_case(client_id: int, case_name: str) -> dict[str, object]:
    source_artifact = ARTIFACTS_DIR / f"client_{client_id}_{case_name}.json"
    case_dir = prepare_case_dir(client_id, case_name)
    (case_dir / "artifact.json").write_text(source_artifact.read_text(encoding="utf-8"), encoding="utf-8")

    export_res = run_conda_python(case_dir / "export_model.py")
    pipeline_res = run_conda_python(case_dir / "pipeline.py")

    summary_path = case_dir / "summary.json"
    summary = load_json(summary_path) if summary_path.exists() else {}
    artifact = load_json(source_artifact)
    accepted = bool(summary.get("verified")) and bool(summary.get("clip_ok")) and bool(summary.get("relation_ok"))
    return {
        "client_id": client_id,
        "case_name": case_name,
        "verified": summary.get("verified"),
        "clip_ok": summary.get("clip_ok"),
        "relation_ok": summary.get("relation_ok"),
        "accepted": accepted,
        "q_noisy": artifact["witness"]["q_noisy"],
        "summary_path": str(summary_path.relative_to(ROOT_DIR)),
        "export_returncode": export_res.returncode,
        "pipeline_returncode": pipeline_res.returncode,
        "stdout_tail": (pipeline_res.stdout or "").strip()[-300:],
        "stderr_tail": (pipeline_res.stderr or "").strip()[-300:],
    }


def average_vectors(vectors: list[list[int]]) -> list[float]:
    if not vectors:
        return []
    count = len(vectors)
    return [sum(values) / count for values in zip(*vectors)]


def write_rows(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "client_id",
        "case_name",
        "verified",
        "clip_ok",
        "relation_ok",
        "accepted",
        "summary_path",
        "export_returncode",
        "pipeline_returncode",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{k: row[k] for k in fieldnames} for row in rows])


def write_summary(
    rows: list[dict[str, object]],
    output_path: Path,
    tampered_client: int,
    accepted_average: list[float],
) -> None:
    accepted_rows = [row for row in rows if row["accepted"]]
    rejected_rows = [row for row in rows if not row["accepted"]]
    lines = [
        "# Week 17 Proof-Gated Round Summary",
        "",
        f"- Tampered client: {tampered_client}",
        f"- Accepted proofs: {len(accepted_rows)}/{len(rows)}",
        f"- Rejected proofs: {len(rejected_rows)}/{len(rows)}",
        f"- Tampered client accepted: {next(row['accepted'] for row in rows if row['client_id'] == tampered_client)}",
        f"- Accepted aggregate vector length: {len(accepted_average)}",
        "",
        "Accepted clients:",
    ]
    lines.extend(
        f"- client {row['client_id']} ({row['case_name']}): verified={row['verified']}, clip_ok={row['clip_ok']}, relation_ok={row['relation_ok']}"
        for row in accepted_rows
    )
    lines.extend(
        [
            "",
            "Rejected clients:",
        ]
    )
    lines.extend(
        f"- client {row['client_id']} ({row['case_name']}): verified={row['verified']}, clip_ok={row['clip_ok']}, relation_ok={row['relation_ok']}"
        for row in rejected_rows
    )
    lines.extend(
        [
            "",
            "Interpretation:",
            "- This experiment runs actual EZKL-backed client checks before aggregation.",
            "- The server only aggregates q_noisy vectors from clients whose proofs verify and whose recommended-profile checks pass.",
            "- This is closer to a true proof-gated FL+VDP round than the earlier single-artifact smoke test.",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_aggregate(output_path: Path, accepted_average: list[float]) -> None:
    output_path.write_text(json.dumps({"accepted_average_q_noisy": accepted_average}, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a proof-gated round with actual EZKL client checks")
    parser.add_argument("--tampered-client", type=int, default=1)
    args = parser.parse_args()

    print("=" * 60)
    print("Week 17 - Proof-Gated Round")
    print("=" * 60)

    rows: list[dict[str, object]] = []
    for client_id in range(3):
        case_name = "tampered_noisy_profile" if client_id == args.tampered_client else "honest_profile"
        print(f"Running client {client_id} -> {case_name}")
        rows.append(run_case(client_id, case_name))

    accepted_vectors = [row["q_noisy"] for row in rows if row["accepted"]]
    accepted_average = average_vectors(accepted_vectors)

    write_rows(rows, RESULTS_DIR / "proof_gated_round.csv")
    write_aggregate(RESULTS_DIR / "accepted_aggregate.json", accepted_average)
    write_summary(rows, RESULTS_DIR / "summary.md", args.tampered_client, accepted_average)
    print(f"Results saved to: {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
