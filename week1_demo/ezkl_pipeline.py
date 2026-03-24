"""
Orchestrator script that runs the entire ZKML workflow by calling modular scripts.
This script is for demonstration and testing purposes. In a real application,
each script (1_*, 2_*, etc.) would be run by different actors.

Run: python -m ezkl_pipeline
"""
import subprocess
import sys
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    print("Cleaning up old files...")
    files_to_delete = [
        BASE_DIR / "settings.json",
        BASE_DIR / "network.ezkl",
        BASE_DIR / "kzg.srs",
        BASE_DIR / "pk.key",
        BASE_DIR / "vk.key",
        BASE_DIR / "witness.json",
        BASE_DIR / "proof.json",
    ]
    for file in files_to_delete:
        if os.path.exists(file):
            os.remove(file)
            print(f"Deleted: {file}")
    
    scripts = [
        "1_train_and_export.py",
        "2_compile_and_setup.py",
        "3_prove.py",
        "4_verify.py"
    ]

    all_success = True
    for i, script_name in enumerate(scripts):
        print(f"\n{'='*20} [Step {i+1}/{len(scripts)}] Running: {script_name} {'='*20}")
        try:
            # Use sys.executable to ensure we use the same python interpreter
            subprocess.run(
                [sys.executable, str(BASE_DIR / script_name)],
                cwd=BASE_DIR,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"\n✗ Script {script_name} failed with exit code {e.returncode}.")
            all_success = False
            break
        except FileNotFoundError:
            print(f"\n✗ Script {script_name} not found.")
            all_success = False
            break

    if all_success:
        print("\n\n" + "="*60)
        print("🎉🎉🎉 Full pipeline completed successfully! 🎉🎉🎉")
        print("="*60)
    else:
        print("\n\n" + "="*60)
        print("🔥🔥🔥 Pipeline failed. Check the errors above. 🔥🔥🔥")
        print("="*60)
