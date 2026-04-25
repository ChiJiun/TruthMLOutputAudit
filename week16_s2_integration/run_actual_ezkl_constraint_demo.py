"""
Week 16 - Actual EZKL demo for the recommended constraint profile.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
ARTIFACTS_DIR = ROOT_DIR / "week14_constraint_artifacts" / "results" / "artifacts" / "scale_10000"
SCRIPT_DIR = BASE_DIR / "ezkl_actual_demo"
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
output = model(packed).detach().cpu().tolist()
(base / "expected_output.json").write_text(json.dumps(output), encoding="utf-8")
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
input_payload = {
    "input_data": packed.tolist(),
}
(base / "input.json").write_text(json.dumps(input_payload), encoding="utf-8")

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


def prepare_demo_dir(case_name: str) -> Path:
    demo_dir = SCRIPT_DIR / case_name
    demo_dir.mkdir(parents=True, exist_ok=True)
    (demo_dir / "constraint_model.py").write_text(CHECK_MODEL_CODE, encoding="utf-8")
    (demo_dir / "export_model.py").write_text(EXPORT_MODEL_CODE, encoding="utf-8")
    (demo_dir / "pipeline.py").write_text(PIPELINE_CODE, encoding="utf-8")
    return demo_dir


def run_conda_python(script_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["conda", "run", "-n", "zkML", "python", str(script_path)],
        cwd=script_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def run_case(case_name: str) -> dict[str, object]:
    source_artifact = ARTIFACTS_DIR / f"client_0_{case_name}.json"
    demo_dir = prepare_demo_dir(case_name)
    (demo_dir / "artifact.json").write_text(source_artifact.read_text(encoding="utf-8"), encoding="utf-8")

    export_res = run_conda_python(demo_dir / "export_model.py")
    pipeline_res = run_conda_python(demo_dir / "pipeline.py")

    summary_path = demo_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    return {
        "case_name": case_name,
        "export_returncode": export_res.returncode,
        "pipeline_returncode": pipeline_res.returncode,
        "verified": summary.get("verified"),
        "clip_sum_sq": summary.get("clip_sum_sq"),
        "relation_sum_sq": summary.get("relation_sum_sq"),
        "clip_ok": summary.get("clip_ok"),
        "relation_ok": summary.get("relation_ok"),
        "stdout_tail": (pipeline_res.stdout or "").strip()[-500:],
        "stderr_tail": (pipeline_res.stderr or "").strip()[-500:],
    }


def write_summary(results: list[dict[str, object]], output_path: Path) -> None:
    lines = [
        "# Week 16 Actual EZKL Constraint Demo Summary",
        "",
    ]
    for result in results:
        lines.extend(
            [
                f"- {result['case_name']}: verified={result['verified']}, clip_ok={result['clip_ok']}, relation_ok={result['relation_ok']}, clip_sum_sq={result['clip_sum_sq']}, relation_sum_sq={result['relation_sum_sq']}",
            ]
        )
    lines.extend(
        [
            "",
            "Interpretation:",
            "- This demo uses the real EZKL Python API on a small ONNX check model derived from the recommended constraint profile.",
            "- A successful verify means the backend can prove the arithmetic check model for the supplied artifact.",
            "- The artifact is still separate from a full FL training circuit, but this moves S2 from stub-only to actual proof/verify on constraint-style data.",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run actual EZKL demo for recommended constraint profile")
    parser.add_argument("--cases", nargs="+", default=["honest_profile", "tampered_noisy_profile"])
    args = parser.parse_args()

    print("=" * 60)
    print("Week 16 - Actual EZKL Constraint Demo")
    print("=" * 60)

    results = [run_case(case_name) for case_name in args.cases]
    output_path = BASE_DIR / "results" / "actual_ezkl_summary.md"
    write_summary(results, output_path)
    print(f"Results saved to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
