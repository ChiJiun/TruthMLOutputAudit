"""
Step 1: Model Training and Export

This script defines a simple PyTorch model, performs a mock training,
and exports it to the ONNX format. It also creates a sample input file
for the ZK proof generation.

This step is typically performed by a Machine Learning Engineer.
"""
import json
import torch
import torch.nn as nn
import numpy as np

from common import ONNX_PATH, INPUT_JSON


def build_model():
    """Build a very simple linear model that ezkl can handle."""
    return nn.Sequential(
        nn.Linear(10, 4),
    )


def quick_train(model):
    """Perform a tiny synthetic 'training' to give the model non-random weights."""
    model.train()
    optim = torch.optim.SGD(model.parameters(), lr=0.01)
    loss_fn = nn.CrossEntropyLoss()
    for _ in range(5):
        x = torch.randn(8, 10)
        y = torch.randint(0, 4, (8,))
        optim.zero_grad()
        logits = model(x)
        loss = loss_fn(logits, y)
        loss.backward()
        optim.step()
    return model


def export_onnx(model, path):
    """Export the trained model to ONNX format."""
    model.eval()
    dummy_input = torch.randn(1, 10)
    torch.onnx.export(
        model,
        dummy_input,
        str(path),
        input_names=["input"],
        output_names=["output"],
        opset_version=15,
        do_constant_folding=True,
        export_params=True,
    )
    print(f"✓ Exported ONNX model to {path}")


def create_sample_input():
    """Create a sample input JSON file for the model."""
    # Use the same input as in the provided context for consistency
    sample_input_data = [0.25092643485400423, -1.639964720244637, -1.9068021855927813, -0.131556262723808, -0.7229207932732373, 0.3858317070867058, -0.8964725620292089, -1.6143924178333438, -0.7675082178199432, -0.6326206504262908]
    sample_input = {"input_data": [sample_input_data]}
    with open(INPUT_JSON, 'w') as f:
        json.dump(sample_input, f, indent=2)
    print(f"✓ Created sample input at {INPUT_JSON}")


if __name__ == "__main__":
    print("--- 1. Model Training & Export ---")
    model = build_model()
    model = quick_train(model)
    export_onnx(model, ONNX_PATH)
    create_sample_input()
    print("--- Step 1 Complete ---\n")