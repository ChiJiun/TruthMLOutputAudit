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
