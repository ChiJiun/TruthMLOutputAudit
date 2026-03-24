"""
Week 2 專用 EZKL pipeline
使用訓練好的 Adult Income 模型
"""
import sys
import os
import json
import numpy as np
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

def create_input_json():
    """創建輸入資料 JSON"""
    # 載入一筆測試資料
    X_test = np.load('data/processed/X_test.npy')
    sample = X_test[0].tolist()  # 取第一筆（單個樣本）
    
    input_data = {"input_data": [sample]}  # 正確格式：[[...]]
    
    with open('input.json', 'w') as f:
        json.dump(input_data, f)
    
    print("✅ input.json 已創建")

def run_ezkl_pipeline():
    """執行完整的 EZKL 流程"""
    
    # 檢查 ezkl 是否安裝
    try:
        import ezkl
        print(f"✓ 找到 ezkl 版本: {ezkl.__version__}")
    except ImportError:
        print("❌ ezkl 套件未安裝！")
        print("請執行: pip install ezkl")
        return False
    
    # 設定路徑
    model_path = Path("models/adult_income_model.onnx")
    settings_path = Path("src/settings.json")
    input_path = Path("input.json")
    compiled_model = Path("src/network.ezkl")
    srs_path = Path("src/kzg.srs")
    pk_path = Path("results/pk.key")
    vk_path = Path("results/vk.key")
    witness_path = Path("witness.json")
    proof_path = Path("results/proof.json")
    
    if not model_path.exists():
        print("❌ 找不到模型檔案！請先執行 python train_model.py")
        return False
    
    os.makedirs("results", exist_ok=True)
    os.makedirs("src", exist_ok=True)
    
    print("\n" + "="*60)
    print("Week 2 - EZKL Pipeline")
    print("="*60)
    
    # 創建輸入資料
    create_input_json()
    
    # Step 1: Gen-settings
    print("\n[1/6] 生成 settings...")
    res = ezkl.gen_settings(str(model_path), str(settings_path))
    if not res:
        print("❌ Gen-settings 失敗")
        return False
    print("✅ Settings 生成完成")
    
    # Step 2: Calibrate settings
    print("\n[2/6] Calibrate settings...")
    res = ezkl.calibrate_settings(
        str(input_path),
        str(model_path),
        str(settings_path),
        "resources"
    )
    if not res:
        print("❌ Calibrate 失敗")
        return False
    print("✅ Settings 校準完成")
    
    # Step 3: Compile
    print("\n[3/6] 編譯電路...")
    res = ezkl.compile_circuit(
        str(model_path),
        str(compiled_model),
        str(settings_path)
    )
    if not res:
        print("❌ Compile 失敗")
        return False
    print("✅ 電路編譯完成")
    
    # Step 4: Setup directly (may auto-download SRS)
    print("\n[4/6] Skip get_srs - 直接執行 setup...")
    print("  (Setup 可能會自動下載 SRS)")
    
    # Step 5: Setup
    print("\n[5/6] Setup (生成 proving/verifying keys)...")
    res = ezkl.setup(
        str(compiled_model),
        str(vk_path),
        str(pk_path),
        str(srs_path)
    )
    if not res:
        print("❌ Setup 失敗")
        return False
    print("✅ Setup 完成")
    
    # Step 6: Gen-witness
    print("\n[6/6] 生成 witness...")
    res = ezkl.gen_witness(
        data=str(input_path),
        model=str(compiled_model),
        output=str(witness_path)
    )
    if not res:
        print("❌ Gen-witness 失敗")
        return False
    print("✅ Witness 生成完成")
    
    # Step 7: Prove
    print("\n[7/7] 生成證明...")
    res = ezkl.prove(
        witness=str(witness_path),
        model=str(compiled_model),
        pk_path=str(pk_path),
        proof_path=str(proof_path),
        proof_type="single",
        srs_path=str(srs_path)
    )
    if not res:
        print("❌ Prove 失敗")
        return False
    print("✅ Proof 生成完成")
    
    # Step 8: Verify
    print("\n[8/8] 驗證證明...")
    res = ezkl.verify(
        str(proof_path),
        str(settings_path),
        str(vk_path),
        str(srs_path)
    )
    if not res:
        print("❌ Verify 失敗")
        return False
    print("✅ Verify 通過！")
    
    print("\n" + "="*60)
    print("🎉 Week 2 Pipeline 完成！")
    print("="*60)
    
    # 顯示 proof 資訊
    if proof_path.exists():
        with open(proof_path, 'r') as f:
            proof = json.load(f)
        
        proof_size = proof_path.stat().st_size / 1024
        print(f"\n📊 結果:")
        print(f"  Proof 大小: {proof_size:.2f} KB")
        print(f"  輸出路徑: results/")
    
    return True

if __name__ == "__main__":
    success = run_ezkl_pipeline()
    sys.exit(0 if success else 1)
