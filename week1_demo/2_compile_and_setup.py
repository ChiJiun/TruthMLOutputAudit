"""
Step 2: Compile Circuit and Trusted Setup

This script takes the ONNX model and performs all the necessary
cryptographic setup steps:
1. Generates settings for the ZK circuit.
2. Calibrates the settings for quantization.
3. Compiles the model into a ZK circuit.
4. Downloads the SRS (Structured Reference String) if not present.
5. Generates the proving key (pk) and verifying key (vk).

This step is typically performed once by a trusted party (e.g., ZK Engineer).
"""
import json
from pathlib import Path
from common import (
    ONNX_PATH, SETTINGS_JSON, INPUT_JSON,
    COMPILED_MODEL, SRS_PATH, PK_PATH, VK_PATH,
)

if __name__ == "__main__":
    print("--- 2. Compile Circuit & Setup ---")
    try:
        # --- Pre-flight check ---
        try:
            import ezkl
            print(f"✓ Found ezkl version: {ezkl.__version__}")
        except ImportError:
            print("✗ ezkl package not found.")
            print("Please install it in your 'zkML' conda environment by running:")
            print("  pip install ezkl")
            exit(1)

        print("\n[1/5] Generating settings...")
        # Note: ezkl API syntax has changed. Using positional arguments.
        # Create the settings file
        res = ezkl.gen_settings(
            str(ONNX_PATH),
            str(SETTINGS_JSON),
        )
        assert res is True

        print("\n[2/5] Calibrating settings...")
        # Calibrate settings to quantize the model
        res = ezkl.calibrate_settings(
            str(INPUT_JSON),
            str(ONNX_PATH),
            str(SETTINGS_JSON),
            "resources"  # "resources" or "accuracy"
        )
        assert res is True

        print("\n[3/5] Compiling circuit...")
        res = ezkl.compile_circuit(
            str(ONNX_PATH),
            str(COMPILED_MODEL),
            str(SETTINGS_JSON)
        )
        assert res is True

        print("\n[4/5] Checking for SRS...")
        if not Path(SRS_PATH).exists():
            print("⚠ SRS not found. Attempting to download...")
            # srs_path, settings_path
            res = ezkl.get_srs(
                str(SRS_PATH),
                str(SETTINGS_JSON)
            )
            assert res is True
        else:
            print(f"✓ Using existing SRS: {SRS_PATH}")

        print("\n[5/5] Running setup...")
        # A trusted setup ceremony would be required for a production application.
        # For this demo, we can generate the keys locally.
        # Check all required files before setup
        required_files = [
            ("ONNX model", ONNX_PATH),
            ("Settings", SETTINGS_JSON),
            ("Compiled model", COMPILED_MODEL),
            ("SRS", SRS_PATH),
        ]
        for name, path in required_files:
            if not Path(path).exists():
                print(f"✗ {name} not found at {path}")
                exit(1)
            else:
                print(f"✓ {name} found: {path}")
        
        # compiled_model_path, vk_path, pk_path, srs_path
        res = ezkl.setup(str(COMPILED_MODEL), str(VK_PATH), str(PK_PATH), str(SRS_PATH))
        assert res is True

        print("\n✓ Setup complete!")
        print(f"  - Proving key: {PK_PATH}")
        print(f"  - Verifying key: {VK_PATH}")

    except Exception as e:
        print(f"\n✗ An error occurred during setup: {e}")
        exit(1)

    print("--- Step 2 Complete ---\n")