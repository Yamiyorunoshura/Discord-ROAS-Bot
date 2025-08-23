# 依賴管理策略文檔
# Task ID: T7 - 環境與依賴管理系統

## 概述

本文檔定義了Discord機器人專案使用uv和pyproject.toml的現代Python依賴管理策略。此策略旨在確保開發、測試、生產環境的一致性，同時提供快速且可重現的依賴安裝體驗。

## 工具鏈架構

### 核心工具

- **uv**: 現代化Python包管理器，負責依賴解析、安裝和虛擬環境管理
- **pyproject.toml**: 專案配置中心，定義依賴、構建配置和工具設定
- **uv.lock**: 依賴版本鎖定檔案，確保所有環境依賴版本完全一致

### 檔案結構
```
專案根目錄/
├── pyproject.toml      # 專案配置與依賴定義
├── uv.lock            # 依賴版本鎖定（受版本控制）
├── .venv/             # 本地虛擬環境（不受版本控制）
└── README.md          # 包含環境設置說明
```

## 依賴分類策略

### 主要依賴 (dependencies)
- **Discord.py**: Discord API整合
- **aiohttp**: 異步HTTP客戶端
- **pydantic**: 資料驗證與序列化
- **aiosqlite**: 異步SQLite支援
- **Pillow**: 影像處理（用於用戶頭像等）
- **其他業務邏輯依賴**

### 開發依賴 (optional-dependencies.dev)
- **測試框架**: pytest, pytest-asyncio, pytest-cov, pytest-mock
- **程式碼品質**: black, isort, flake8, mypy
- **Discord測試**: dpytest
- **文檔與工具**: pyyaml（用於配置解析）

### 監控依賴 (optional-dependencies.monitoring)
- **prometheus-client**: 效能指標收集
- **grafana-api**: 監控儀表板整合

## 開發工作流程

### 初次環境設置

```bash
# 1. 確認uv已安裝
uv --version

# 2. 複製專案
git clone <repository-url>
cd discord-bot

# 3. 建立虛擬環境並安裝依賴
uv sync --extra dev

# 4. 啟動開發環境（可選）
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 5. 驗證安裝
uv run python -c "import discord; print('Discord.py可用')"
```

**預期時間**: < 5分鐘（符合N-7-3需求）

### 日常開發工作流程

#### 添加新依賴
```bash
# 添加主要依賴
uv add package-name

# 添加開發依賴
uv add --dev package-name

# 添加可選依賴組
uv add --optional monitoring package-name
```

#### 更新依賴
```bash
# 更新特定包
uv lock --upgrade-package package-name

# 更新所有依賴
uv lock --upgrade

# 同步環境
uv sync
```

#### 移除依賴
```bash
uv remove package-name
```

### 測試與品質保證

#### 運行測試
```bash
# 單元測試
uv run python -m pytest tests/unit/ -v

# 整合測試
uv run python -m pytest tests/integration/ -v

# Discord測試
uv run python -m pytest tests/dpytest/ -v

# 全部測試
uv run python -m pytest
```

#### 程式碼品質檢查
```bash
# 格式化程式碼
uv run black .
uv run isort .

# 靜態檢查
uv run flake8 .
uv run mypy services/ panels/ core/ --ignore-missing-imports
```

## CI/CD 整合策略

### GitHub Actions 配置

我們的CI工作流程已完全遷移至uv，包含以下最佳化：

#### 快取策略
```yaml
- name: Cache uv dependencies  
  uses: actions/cache@v3
  with:
    path: ~/.cache/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('**/uv.lock') }}
    restore-keys: |
      ${{ runner.os }}-uv-
```

#### 依賴安裝
```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v4
  with:
    version: "latest"
    
- name: Install dependencies with uv
  run: |
    uv sync --extra dev --no-progress
```

#### 測試執行
```yaml
- name: Run tests
  run: |
    uv run python -m pytest tests/unit/ -v \
      --cov=services --cov=panels --cov=core \
      --cov-report=xml --cov-report=html
```

### 效能基準

- **依賴安裝時間**: < 60秒（目標：符合N-7-1）
- **快取命中時**: < 10秒
- **相對於pip提升**: 30%+

## 安全策略

### 依賴安全掃描

```bash
# 安全漏洞掃描
uv add --dev safety bandit
uv run safety check

# 程式碼安全分析
uv run bandit -r services/ panels/ core/
```

### 版本固定策略

- **生產依賴**: 使用精確版本（透過uv.lock自動管理）
- **開發依賴**: 允許次要版本更新（>= 語法）
- **安全更新**: 定期（每月）更新所有依賴

## 環境一致性保證

### 版本鎖定機制

- **uv.lock檔案**: 記錄所有依賴的確切版本和雜湊值
- **版本控制**: uv.lock必須提交到版本控制系統
- **跨平台支援**: uv.lock包含多平台資訊

### 環境驗證

```bash
# 驗證環境一致性
uv sync --frozen  # 嚴格按照uv.lock安裝

# 檢查依賴樹
uv tree

# 檢查過時依賴
uv outdated
```

## 疑難排解指南

### 常見問題與解決方案

#### 1. "uv command not found"
**問題**: uv未安裝或不在PATH中
**解決方案**:
```bash
# macOS (Homebrew)
brew install uv

# 其他平台
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. "Package conflicts detected"
**問題**: 依賴衝突
**解決方案**:
```bash
# 清除快取並重新解析
uv cache clean
uv lock --refresh
uv sync
```

#### 3. "Virtual environment mismatch"
**問題**: 多個虛擬環境衝突
**解決方案**:
```bash
# 刪除現有環境
rm -rf .venv

# 重新建立
uv sync --extra dev
```

#### 4. CI建置失敗
**問題**: CI環境與本地不一致
**解決方案**:
```bash
# 確認uv.lock已提交
git add uv.lock
git commit -m "更新依賴鎖定檔案"

# 在CI中使用frozen模式
uv sync --frozen --extra dev
```

#### 5. 依賴安裝緩慢
**問題**: 網路或快取問題
**解決方案**:
```bash
# 清除並重建快取
uv cache clean
uv sync --reinstall
```

### 除錯工具

```bash
# 詳細輸出
uv sync -v

# 檢查環境狀態
uv info

# 驗證專案配置
uv check
```

## 遷移指南

### 從pip/requirements.txt遷移

如果從舊系統遷移，請遵循以下步驟：

1. **備份現有配置**
   ```bash
   cp requirements.txt requirements.txt.backup
   cp requirements-dev.txt requirements-dev.txt.backup
   ```

2. **初始化uv專案**
   ```bash
   uv init --python 3.10
   ```

3. **轉換依賴**
   ```bash
   # 從requirements.txt讀取並添加到pyproject.toml
   while read requirement; do uv add "$requirement"; done < requirements.txt
   while read requirement; do uv add --dev "$requirement"; done < requirements-dev.txt
   ```

4. **生成鎖定檔案**
   ```bash
   uv lock
   ```

5. **驗證遷移**
   ```bash
   uv sync
   uv run python -m pytest
   ```

## 最佳實踐

### 開發最佳實踐

1. **定期更新**: 每週檢查並更新依賴
2. **最小依賴**: 僅添加必要的依賴
3. **版本範圍**: 合理設定版本範圍，避免過度限制
4. **測試覆蓋**: 依賴更新後必須執行完整測試

### 協作最佳實踐

1. **鎖定檔案同步**: 每次PR必須包含uv.lock更新
2. **環境重建**: 定期重建本地環境確保一致性
3. **文檔同步**: 依賴變更必須更新相關文檔

### 效能最佳化

1. **快取利用**: 充分利用uv的快取機制
2. **平行安裝**: uv預設使用平行安裝
3. **增量更新**: 僅更新必要的依賴

## 支援與維護

### 定期維護任務

- **每週**: 檢查安全更新
- **每月**: 更新所有依賴到最新穩定版本
- **每季**: 評估並清理不再使用的依賴

### 監控指標

- 依賴安裝時間
- CI建置成功率
- 安全漏洞數量
- 依賴版本新鮮度

### 聯絡資訊

如遇到本文檔未涵蓋的問題，請：
1. 查閱uv官方文檔: https://docs.astral.sh/uv/
2. 提交GitHub Issue
3. 聯繫開發團隊

---

**版本**: 1.0  
**最後更新**: 2025-08-23  
**責任人**: Marcus（後端系統守護者）  
**相關任務**: T7 - 環境與依賴管理系統