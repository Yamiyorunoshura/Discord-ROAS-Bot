# Python 3.13 升級指導

## 概述

本專案已從Python 3.10+升級至Python 3.13+，以利用最新的效能改進和語言特性。

## 主要變更

### 1. 環境需求更新
- **Python版本**: 從 `>=3.10` 升級至 `>=3.13`
- **Discord.py版本**: 從 `>=2.5.2` 升級至 `>=2.6.0`

### 2. 新語法特性採用
- **Self類型**: 在`services/achievement/models.py`中採用了Python 3.13的`Self`類型，簡化了類方法的返回類型註解
- **改進的typing系統**: 利用了更精確的型別檢查

### 3. 效能提升
- Python 3.13提供5-15%的效能提升
- 記憶體使用減少約7%
- 改進的垃圾回收機制

## 本地開發環境升級步驟

### 1. 安裝Python 3.13
**macOS (使用Homebrew)**:
```bash
brew install python@3.13
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install python3.13 python3.13-dev python3.13-venv
```

### 2. 更新專案環境
```bash
# 使用uv (推薦)
uv python install 3.13
uv venv --python 3.13
uv sync

# 或使用傳統方法
python3.13 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows
pip install -r requirement.txt
```

### 3. 驗證升級
```bash
# 檢查Python版本
python --version  # 應該顯示 Python 3.13.x

# 檢查關鍵套件
python -c "import discord; print(f'discord.py: {discord.__version__}')"
python -c "import sys; print(f'Python版本: {sys.version}')"
```

## 容器環境

容器環境已經使用`python:3.13-slim`基底映像，無需額外配置。

## 相容性注意事項

### 已測試的相容性
- ✅ Discord.py 2.6.0
- ✅ aiohttp 3.12.15
- ✅ 所有核心依賴套件
- ✅ 現有程式碼語法

### 潛在問題
- 一些第三方套件可能需要等待Python 3.13相容版本
- 循環導入問題需要持續關注

## 新特性使用指南

### Self類型
```python
from typing import Self

class MyClass:
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:  # 而非 -> 'MyClass'
        return cls(**data)
```

### 改進的錯誤訊息
Python 3.13提供了更清晰的錯誤訊息，有助於調試。

### 效能優化
- 字典和集合操作更快
- 字串處理效能改進
- 函數調用開銷降低

## 回滾策略

如遇到相容性問題，可以暫時回退：

1. **修改pyproject.toml**:
   ```toml
   requires-python = ">=3.12"
   ```

2. **重新安裝依賴**:
   ```bash
   uv sync --python 3.12
   ```

3. **更新容器映像**:
   ```dockerfile
   FROM python:3.12-slim
   ```

## 監控指標

升級後請關注以下指標：
- 應用程式啟動時間
- 記憶體使用量
- Discord API回應時間
- 資料庫查詢效能

## 問題回報

如發現與Python 3.13升級相關的問題，請：
1. 記錄錯誤訊息和堆疊追蹤
2. 註明Python版本和相依套件版本
3. 提供重現步驟
4. 考慮暫時回退並回報問題

---
**升級完成日期**: 2025-08-23  
**Task ID**: T9  
**負責人**: fullstack-developer (Alex)