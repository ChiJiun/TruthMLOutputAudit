"""
Common constants and helper functions for the ezkl workflow scripts.
"""
import sys
import shutil
import subprocess
from pathlib import Path

# --- Constants ---
BASE_DIR = Path(__file__).resolve().parent

ONNX_PATH = BASE_DIR / "demo_model.onnx"
INPUT_JSON = BASE_DIR / "input.json"
SETTINGS_JSON = BASE_DIR / "settings.json"
COMPILED_MODEL = BASE_DIR / "network.ezkl"
WITNESS_JSON = BASE_DIR / "witness.json"
SRS_PATH = BASE_DIR / "kzg.srs"
PK_PATH = BASE_DIR / "pk.key"
VK_PATH = BASE_DIR / "vk.key"
PROOF_PATH = BASE_DIR / "proof.json"


# --- Helper Functions ---
