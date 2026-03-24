"""
Week 3 - Scale sweep for the Week 2 Adult Income model.

This script evaluates quantized accuracy for a fixed ONNX model under
different scales, and optionally runs the EZKL prove/verify pipeline
for each scale when the `ezkl` package is available.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper


ROOT = Path(__file__).resolve().parents[1]
WEEK2_DIR = ROOT / "week2_uci_model"
OUTPUT_DIR = Path(__file__).resolve().parent / "results"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

MODEL_PATH = WEEK2_DIR / "models" / "adult_income_model.onnx"
X_TEST_PATH = WEEK2_DIR / "data" / "processed" / "X_test.npy"
Y_TEST_PATH = WEEK2_DIR / "data" / "processed" / "y_test.npy"
WEEK2_SRS_PATH = WEEK2_DIR / "src" / "kzg.srs"


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def load_linear_weights(model_path: Path) -> tuple[np.ndarray, np.ndarray]:
    model = onnx.load(str(model_path))
    initializers = {
        initializer.name: numpy_helper.to_array(initializer)
        for initializer in model.graph.initializer
    }

    weight = None
    bias = None
    for name, value in initializers.items():
        if value.ndim == 2 and weight is None:
            weight = value.astype(np.float64)
        elif value.ndim == 1 and bias is None:
            bias = value.astype(np.float64)

    if weight is None or bias is None:
        raise ValueError(f"Could not find linear layer weights in {model_path}")

    return weight, bias


def quantized_accuracy(
    x_test: np.ndarray,
    y_test: np.ndarray,
    weight: np.ndarray,
    bias: np.ndarray,
    scale: int,
) -> float:
    factor = 2 ** scale
    q_x = np.round(x_test * factor)
    q_w = np.round(weight * factor)
    q_b = np.round(bias * (factor ** 2))

    logits_int = q_x @ q_w.T + q_b.reshape(1, -1)
    logits = logits_int / (factor ** 2)

    probs = sigmoid(logits.reshape(-1))
    preds = (probs > 0.5).astype(np.float64)
    return float((preds == y_test.astype(np.float64)).mean())


def create_input_json(output_path: Path, sample: np.ndarray) -> None:
    payload = {"input_data": [sample.tolist()]}
    output_path.write_text(json.dumps(payload), encoding="utf-8")


def force_scale_settings(settings_path: Path, scale: int) -> None:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    run_args = settings.setdefault("run_args", {})
    run_args["input_scale"] = scale
    run_args["param_scale"] = scale

    settings["model_input_scales"] = [scale]
    settings["model_output_scales"] = [scale * 2]

    settings_path.write_text(
        json.dumps(settings, ensure_ascii=False),
        encoding="utf-8",
    )


def run_ezkl_pipeline_for_scale(
    scale: int,
    model_path: Path,
    sample: np.ndarray,
) -> dict[str, object]:
    try:
        import ezkl
    except ImportError:
        return {
            "ezkl_status": "skipped",
            "proving_time_sec": "",
            "verify_time_sec": "",
            "proof_size_kb": "",
            "verified": "",
            "error": "ezkl not installed",
        }

    scale_dir = ARTIFACTS_DIR / f"scale_{scale}"
    src_dir = scale_dir / "src"
    results_dir = scale_dir / "results"

    if scale_dir.exists():
        shutil.rmtree(scale_dir)
    src_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    input_path = scale_dir / "input.json"
    settings_path = src_dir / "settings.json"
    compiled_model_path = src_dir / "network.ezkl"
    srs_path = src_dir / "kzg.srs"
    pk_path = results_dir / "pk.key"
    vk_path = results_dir / "vk.key"
    witness_path = scale_dir / "witness.json"
    proof_path = results_dir / "proof.json"

    create_input_json(input_path, sample)

    res = ezkl.gen_settings(str(model_path), str(settings_path))
    if not res:
        raise RuntimeError("gen_settings failed")

    res = ezkl.calibrate_settings(
        str(input_path),
        str(model_path),
        str(settings_path),
        "resources",
    )
    if not res:
        raise RuntimeError("calibrate_settings failed")

    force_scale_settings(settings_path, scale)

    res = ezkl.compile_circuit(
        str(model_path),
        str(compiled_model_path),
        str(settings_path),
    )
    if not res:
        raise RuntimeError("compile_circuit failed")

    if WEEK2_SRS_PATH.exists():
        shutil.copy2(WEEK2_SRS_PATH, srs_path)
    else:
        res = ezkl.get_srs(str(srs_path), str(settings_path))
        if not res:
            raise RuntimeError("get_srs failed")

    res = ezkl.setup(
        str(compiled_model_path),
        str(vk_path),
        str(pk_path),
        str(srs_path),
    )
    if not res:
        raise RuntimeError("setup failed")

    res = ezkl.gen_witness(
        data=str(input_path),
        model=str(compiled_model_path),
        output=str(witness_path),
    )
    if not res:
        raise RuntimeError("gen_witness failed")

    prove_start = time.perf_counter()
    res = ezkl.prove(
        witness=str(witness_path),
        model=str(compiled_model_path),
        pk_path=str(pk_path),
        proof_path=str(proof_path),
        proof_type="single",
        srs_path=str(srs_path),
    )
    proving_time_sec = time.perf_counter() - prove_start
    if not res:
        raise RuntimeError("prove failed")

    verify_start = time.perf_counter()
    verified = ezkl.verify(
        str(proof_path),
        str(settings_path),
        str(vk_path),
        str(srs_path),
    )
    verify_time_sec = time.perf_counter() - verify_start

    return {
        "ezkl_status": "completed",
        "proving_time_sec": round(proving_time_sec, 4),
        "verify_time_sec": round(verify_time_sec, 4),
        "proof_size_kb": round(proof_path.stat().st_size / 1024, 4),
        "verified": bool(verified),
        "error": "",
    }


def write_results_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scale",
        "quantized_accuracy",
        "ezkl_status",
        "proving_time_sec",
        "verify_time_sec",
        "proof_size_kb",
        "verified",
        "error",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week 3 scale sweep")
    parser.add_argument(
        "--scales",
        nargs="+",
        type=int,
        default=[8, 12, 16],
        help="Scale values to test",
    )
    parser.add_argument(
        "--accuracy-only",
        action="store_true",
        help="Skip EZKL prove/verify and only export quantized accuracy",
    )
    args = parser.parse_args()

    if not MODEL_PATH.exists():
        print(f"Model not found: {MODEL_PATH}")
        print("Please finish Week 2 training first.")
        return 1

    x_test = np.load(X_TEST_PATH)
    y_test = np.load(Y_TEST_PATH)
    weight, bias = load_linear_weights(MODEL_PATH)

    rows: list[dict[str, object]] = []

    print("=" * 60)
    print("Week 3 - Scale Sweep")
    print("=" * 60)

    for scale in args.scales:
        accuracy = quantized_accuracy(x_test, y_test, weight, bias, scale)
        row: dict[str, object] = {
            "scale": scale,
            "quantized_accuracy": round(accuracy, 6),
        }

        print(f"\n[Scale {scale}] Quantized accuracy: {accuracy:.4f}")

        if args.accuracy_only:
            row.update(
                {
                    "ezkl_status": "skipped",
                    "proving_time_sec": "",
                    "verify_time_sec": "",
                    "proof_size_kb": "",
                    "verified": "",
                    "error": "accuracy-only mode",
                }
            )
        else:
            try:
                ezkl_result = run_ezkl_pipeline_for_scale(
                    scale=scale,
                    model_path=MODEL_PATH,
                    sample=x_test[0],
                )
                row.update(ezkl_result)
                print(f"  EZKL status: {row['ezkl_status']}")
            except Exception as exc:
                row.update(
                    {
                        "ezkl_status": "failed",
                        "proving_time_sec": "",
                        "verify_time_sec": "",
                        "proof_size_kb": "",
                        "verified": False,
                        "error": str(exc),
                    }
                )
                print(f"  EZKL failed: {exc}")

        rows.append(row)

    output_path = OUTPUT_DIR / "scale_sweep_results.csv"
    write_results_csv(rows, output_path)

    print(f"\nResults saved to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
