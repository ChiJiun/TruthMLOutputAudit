"""
UCI Adult Income Dataset 下載和預處理
Dataset: https://archive.ics.uci.edu/ml/datasets/adult
目標: 預測年收入是否超過 50K
"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
import os
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)


def save_client_splits(X_train, y_train, num_clients=3, seed=42):
    """將訓練資料平均切分成多個 clients，供後續 FL 實驗使用"""

    rng = np.random.default_rng(seed)
    indices = rng.permutation(len(X_train))
    client_indices = np.array_split(indices, num_clients)

    clients_dir = 'data/clients'
    os.makedirs(clients_dir, exist_ok=True)

    metadata = {
        "num_clients": num_clients,
        "random_seed": seed,
        "total_train_samples": int(len(X_train)),
        "clients": [],
    }

    print(f"\n🤝 產生 FL client splits (K={num_clients})...")

    for client_id, idx in enumerate(client_indices):
        client_x = X_train[idx]
        client_y = y_train[idx]

        np.save(os.path.join(clients_dir, f'client_{client_id}_X.npy'), client_x)
        np.save(os.path.join(clients_dir, f'client_{client_id}_y.npy'), client_y)

        positive_ratio = float(client_y.mean()) if len(client_y) > 0 else 0.0
        metadata["clients"].append(
            {
                "client_id": client_id,
                "num_samples": int(len(client_y)),
                "positive_ratio": round(positive_ratio, 6),
            }
        )

        print(
            f"  Client {client_id}: {len(client_y)} 筆, "
            f"正樣本比例 {positive_ratio:.2%}"
        )

    with open(os.path.join(clients_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("✅ Client splits 已儲存到 data/clients/")

def download_and_prepare_data():
    """下載並準備 UCI Adult Income 資料集"""
    
    # 欄位名稱
    column_names = [
        'age', 'workclass', 'fnlwgt', 'education', 'education-num',
        'marital-status', 'occupation', 'relationship', 'race', 'sex',
        'capital-gain', 'capital-loss', 'hours-per-week', 'native-country', 'income'
    ]
    
    # 下載資料
    train_url = "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data"
    test_url = "https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.test"
    
    print("📥 下載訓練資料...")
    df_train = pd.read_csv(train_url, names=column_names, skipinitialspace=True)
    
    print("📥 下載測試資料...")
    df_test = pd.read_csv(test_url, names=column_names, skipinitialspace=True, skiprows=1)
    
    # 合併資料
    df = pd.concat([df_train, df_test], ignore_index=True)
    
    # 儲存原始資料
    os.makedirs('data/raw', exist_ok=True)
    df.to_csv('data/raw/adult_raw.csv', index=False)
    print(f"✅ 原始資料已儲存: {len(df)} 筆")
    
    return df

def preprocess_data(df):
    """資料預處理和特徵工程"""
    
    print("\n🔧 開始資料預處理...")
    
    # 移除缺失值
    df = df.replace(' ?', np.nan)
    df = df.dropna()
    print(f"  移除缺失值後: {len(df)} 筆")
    
    # 選擇數值特徵（簡化模型）
    numerical_features = ['age', 'education-num', 'capital-gain', 
                         'capital-loss', 'hours-per-week']
    
    # 選擇部分類別特徵
    categorical_features = ['workclass', 'marital-status', 'occupation', 'sex']
    
    # 編碼類別特徵
    le = LabelEncoder()
    for col in categorical_features:
        df[col + '_encoded'] = le.fit_transform(df[col])
    
    # 準備特徵矩陣
    feature_cols = numerical_features + [col + '_encoded' for col in categorical_features]
    X = df[feature_cols].values
    
    # 目標變數
    df['income_binary'] = (df['income'].str.strip() == '>50K').astype(int)
    y = df['income_binary'].values
    
    # 標準化
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # 分割資料集
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"  訓練集: {len(X_train)} 筆")
    print(f"  測試集: {len(X_test)} 筆")
    print(f"  特徵數: {X_train.shape[1]}")
    
    # 儲存處理後的資料
    os.makedirs('data/processed', exist_ok=True)
    np.save('data/processed/X_train.npy', X_train)
    np.save('data/processed/X_test.npy', X_test)
    np.save('data/processed/y_train.npy', y_train)
    np.save('data/processed/y_test.npy', y_test)
    
    print("✅ 處理後資料已儲存到 data/processed/")
    
    save_client_splits(X_train, y_train, num_clients=3, seed=42)

    return X_train, X_test, y_train, y_test, feature_cols

if __name__ == "__main__":
    print("="*60)
    print("Week 2 - UCI Adult Income 資料準備")
    print("="*60)
    
    # 下載資料
    df = download_and_prepare_data()
    
    # 預處理
    X_train, X_test, y_train, y_test, features = preprocess_data(df)
    
    print("\n📊 資料摘要:")
    print(f"  特徵: {features}")
    print(f"  訓練集正樣本比例: {y_train.mean():.2%}")
    print(f"  測試集正樣本比例: {y_test.mean():.2%}")
    print("\n✅ 資料準備完成！下一步: 訓練模型")
