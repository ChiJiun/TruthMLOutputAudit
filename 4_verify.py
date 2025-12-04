"""
Step 4: Verify Proof

This script acts as the "Verifier". It takes the public proof,
the verifying key, and the circuit settings to verify that the
proof is valid.

This step can be run by anyone, including a smart contract on a blockchain,
to confirm the integrity of the computation without needing the private input.
"""
from common import (
    PROOF_PATH, SETTINGS_JSON, VK_PATH, SRS_PATH
)

if __name__ == "__main__":
    print("--- 4. Verify Proof ---")
    try:
        # --- Pre-flight check ---
        try:
            import ezkl
        except ImportError:
            print("✗ ezkl package not found.")
            print("Please install it in your 'zkML' conda environment by running:")
            print("  pip install ezkl")
            exit(1)

        print("\n[1/1] Verifying proof...")
        is_valid = ezkl.verify(
            proof_path=str(PROOF_PATH),
            settings_path=str(SETTINGS_JSON),
            vk_path=str(VK_PATH),
            srs_path=str(SRS_PATH),
            non_reduced_srs=False
        )

        if is_valid:
            print("\n✓ Proof verification PASSED! ✨")
        else:
            print("\n✗ Proof verification FAILED.")
            exit(1)
    except Exception as e:
        print(f"\n✗ An error occurred during verification: {e}")
        exit(1)

    print("--- Step 4 Complete ---\n")