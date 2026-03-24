"""
訓練極簡 MLP 模型並匯出為 ONNX（與 EZKL 最大兼容性）
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

class SimpleLinearModel(nn.Module):
    """極簡線性模型（與 EZKL 最大兼容性）"""
    def __init__(self, input_dim=9):
        super().__init__()
        # 只使用線性層，沒有激活函數
        self.fc = nn.Linear(input_dim, 1)
    
    def forward(self, x):
        return self.fc(x)

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
    model = SimpleLinearModel(input_dim=input_dim).to(device)
    
    # 使用 BCEWithLogitsLoss
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    
    print(f"\n🚀 開始訓練 (Epochs: {epochs})")
    print(f"  模型結構: {input_dim} → 1 (純線性)")
    
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
    
    # 使用與 Week 1 相同的參數
    dummy_input = sample_input[:1].cpu()
    
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        export_params=True,
        opset_version=15,  # 使用 opset 15（與 Week 1 相同）
        do_constant_folding=True,
        input_names=['input'],
        output_names=['output']
    )
    
    print(f"✅ ONNX 模型已儲存: {output_path}")
    
    # 驗證 ONNX
    import onnx
    onnx_model = onnx.load(output_path)
    onnx.checker.check_model(onnx_model)
    print("✅ ONNX 模型驗證通過")
    
    # 顯示模型資訊
    print(f"\n模型資訊:")
    print(f"  輸入: {[inp.name for inp in onnx_model.graph.input]}")
    print(f"  輸出: {[out.name for out in onnx_model.graph.output]}")

if __name__ == "__main__":
    print("="*60)
    print("Week 2 - 訓練 Adult Income 模型（簡化版）")
    print("="*60)
    
    # 載入資料
    print("\n📥 載入資料...")
    X_train = np.load('data/processed/X_train.npy')
    X_test = np.load('data/processed/X_test.npy')
    y_train = np.load('data/processed/y_train.npy')
    y_test = np.load('data/processed/y_test.npy')
    
    # 訓練
    model, X_test_t = train_model(X_train, y_train, X_test, y_test, epochs=30)
    
    # 匯出 ONNX
    export_to_onnx(model, X_test_t)
    
    print("\n✅ 完成！下一步: 執行 EZKL pipeline")
