"""
Common constants and helper functions for the ezkl workflow scripts.
"""
import sys
import shutil
import subprocess
from pathlib import Path

# --- Constants ---
ONNX_PATH = "demo_model.onnx"
INPUT_JSON = "input.json"
SETTINGS_JSON = "settings.json"
COMPILED_MODEL = "network.ezkl"
WITNESS_JSON = "witness.json"
SRS_PATH = "kzg.srs"
PK_PATH = "pk.key"
VK_PATH = "vk.key"
PROOF_PATH = "proof.json"


# --- Helper Functions ---