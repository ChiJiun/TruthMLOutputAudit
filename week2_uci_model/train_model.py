"""
訓練 MLP 模型並匯出為 ONNX
"""
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
import numpy as np
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

class AdultIncomeModel(nn.Module):
    """簡單的 MLP 用於二分類（移除 Sigmoid 以相容 EZKL）"""
    def __init__(self, input_dim=9, hidden_dim=16):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, 1)
        # 移除 sigmoid - 在 ZK proof 中我們只需要 logits
    
    def forward(self, x):
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        # 輸出 logits (未經 sigmoid)
        return x

def train_model(X_train, y_train, X_test, y_test, epochs=20, batch_size=128):
    """訓練模型"""
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"🔧 使用裝置: {device}")
    
    # 準備資料
    X_train_t = torch.FloatTensor(X_train)
    y_train_t = torch.FloatTensor(y_train).reshape(-1, 1)
    X_test_t = torch.FloatTensor(X_test)
    y_test_t = torch.FloatTensor(y_test).reshape(-1, 1)
    
    train_dataset = TensorDataset(X_train_t, y_train_t)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    
    # 建立模型
    input_dim = X_train.shape[1]
    model = AdultIncomeModel(input_dim=input_dim, hidden_dim=16).to(device)
    
    # 使用 BCEWithLogitsLoss（內建 sigmoid）
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    print(f"\n🚀 開始訓練 (Epochs: {epochs})")
    print(f"  模型結構: {input_dim} → 16 → 1")
    
    best_acc = 0
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        # 評估
        model.eval()
        with torch.no_grad():
            train_logits = model(X_train_t.to(device))
            test_logits = model(X_test_t.to(device))
            
            train_pred = (torch.sigmoid(train_logits) > 0.5).float()
            test_pred = (torch.sigmoid(test_logits) > 0.5).float()
            
            train_acc = (train_pred.cpu() == y_train_t).float().mean()
            test_acc = (test_pred.cpu() == y_test_t).float().mean()
        
        if test_acc > best_acc:
            best_acc = test_acc
        
        if (epoch + 1) % 5 == 0:
            print(f"  Epoch [{epoch+1}/{epochs}] Loss: {total_loss/len(train_loader):.4f} "
                  f"Train Acc: {train_acc:.4f} Test Acc: {test_acc:.4f}")
    
    print(f"\n✅ 訓練完成！最佳測試準確率: {best_acc:.4f}")
    
    return model, X_test_t

def export_to_onnx(model, sample_input, output_path='models/adult_income_model.onnx'):
    """匯出模型為 ONNX 格式"""
    
    os.makedirs('models', exist_ok=True)
    
    model.eval()
    model.cpu()
    
    torch.onnx.export(
        model,
        sample_input[:1],  # 單筆樣本
        output_path,
        export_params=True,
        opset_version=17,  # 使用 opset 17（ezkl 相容）
        do_constant_folding=True,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes=None  # 固定 batch size
    )
    
    print(f"✅ ONNX 模型已儲存: {output_path}")
    
    # 驗證 ONNX
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print("✅ ONNX 模型驗證通過")

if __name__ == "__main__":
    print("="*60)
    print("Week 2 - 訓練 Adult Income 模型")
    print("="*60)
    
    # 載入資料
    print("\n📥 載入資料...")
    X_train = np.load('data/processed/X_train.npy')
    X_test = np.load('data/processed/X_test.npy')
    y_train = np.load('data/processed/y_train.npy')
    y_test = np.load('data/processed/y_test.npy')
    
    # 訓練
    model, X_test_t = train_model(X_train, y_train, X_test, y_test, epochs=20)
    
    # 匯出 ONNX
    export_to_onnx(model, X_test_t)
    
    print("\n✅ 完成！下一步: 執行 EZKL pipeline")
