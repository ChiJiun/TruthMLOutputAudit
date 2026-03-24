"""
Step 3: Generate Proof
...
"""
from common import (
    INPUT_JSON, COMPILED_MODEL,
    WITNESS_JSON, PK_PATH, PROOF_PATH, SRS_PATH,
    SETTINGS_JSON
)

if __name__ == "__main__":
    print("--- 3. Generate Proof ---")
    try:
        # --- Pre-flight check ---
        try:
            import ezkl
            print(f"✓ Found ezkl version: {ezkl.__version__}")
        except ImportError:
            # ... (安裝提示碼) ...
            exit(1)

        print("\n[1/2] Generating witness...")
        # =========================================================================
        # 修正 1：EZKL v10.2.7 語法 (強制使用位置參數)
        # =========================================================================
        ezkl.gen_witness(
            data=str(INPUT_JSON),
            model=str(COMPILED_MODEL),
            output=str(WITNESS_JSON)
        )

        print("\n[2/2] Generating proof (this may take a while)...")
        # =========================================================================
        # 修正 2：EZKL v10.2.7 語法 (強制使用位置參數)
        # =========================================================================
        ezkl.prove(
            witness=str(WITNESS_JSON),
            model=str(COMPILED_MODEL),
            pk_path=str(PK_PATH),
            proof_path=str(PROOF_PATH),
            proof_type="single",
            srs_path=str(SRS_PATH)
        )

        print(f"\n✓ Proof generated successfully: {PROOF_PATH}")
    except Exception as e:
        print(f"\n✗ An error occurred during proof generation: {e}")
        print(f"DEBUG: EZKL Version: {ezkl.__version__}")
        exit(1)
    print("--- Step 3 Complete ---\n")