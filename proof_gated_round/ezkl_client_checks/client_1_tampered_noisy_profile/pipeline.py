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
