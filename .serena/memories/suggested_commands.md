# Discord ADR Bot v1.6 - 建議命令

## 系統命令（Darwin/macOS）

### 基本系統命令
```bash
# 檔案操作
ls -la                       # 列出檔案（詳細）
find . -name "*.py"          # 尋找 Python 檔案
grep -r "pattern" .          # 搜尋文字內容
cat filename                 # 顯示檔案內容
tail -f logs/main.log        # 即時查看日誌

# 目錄操作
cd /path/to/project          # 切換目錄
mkdir -p logs dbs            # 建立目錄
rm -rf __pycache__           # 刪除快取

# 權限管理
chmod +x deploy.py           # 設定執行權限
chown user:group file        # 更改檔案擁有者
```

### Git 操作
```bash
# 基本操作
git status                   # 查看狀態
git add .                    # 添加所有更改
git commit -m "message"      # 提交更改
git push origin main         # 推送到遠端

# 分支操作
git branch                   # 查看分支
git checkout -b feature      # 建立新分支
git merge feature            # 合併分支
git pull origin main         # 拉取最新更改
```

## 環境管理

### 虛擬環境
```bash
# 建立虛擬環境
python3 -m venv venv

# 激活虛擬環境
source venv/bin/activate     # macOS/Linux
venv\Scripts\activate        # Windows

# 停用虛擬環境
deactivate

# 檢查虛擬環境
which python                 # 確認 Python 路徑
pip list                     # 查看已安裝套件
```

### 依賴管理
```bash
# 安裝依賴
pip install -r requirement.txt

# 更新依賴
pip install --upgrade discord.py

# 檢查依賴
pip check                    # 檢查依賴衝突
pip freeze > requirements.txt # 匯出依賴清單

# 清理依賴
pip uninstall package-name
```

## 開發命令

### 程式碼運行
```bash
# 啟動機器人
python main.py

# 背景運行
nohup python main.py &       # 背景運行
screen -S discordbot python main.py  # 使用 screen

# 除錯模式
export DEBUG=True
python main.py

# 生產環境
export ENVIRONMENT=production
python main.py
```

### 程式碼品質
```bash
# 格式化程式碼
black .                      # 格式化所有 Python 檔案
black cogs/                  # 格式化特定目錄

# 程式碼檢查
flake8 .                     # 風格檢查
mypy .                       # 類型檢查
bandit -r .                  # 安全檢查

# 自動品質檢查
python quality_check.py
```

## 測試命令

### 單元測試
```bash
# 運行所有測試
pytest

# 運行特定測試
pytest tests/unit/test_activity_meter.py

# 帶覆蓋率的測試
pytest --cov=cogs

# 效能測試
pytest tests/performance/

# 優化測試
python run_tests_optimized.py
```

### 整合測試
```bash
# 資料庫測試
pytest tests/unit/test_database.py

# API 測試
pytest tests/unit/test_api.py

# 互動測試
pytest tests/unit/test_interactions.py
```

## 資料庫操作

### 資料庫管理
```bash
# 查看資料庫
sqlite3 dbs/activity.db ".tables"
sqlite3 dbs/activity.db ".schema"

# 備份資料庫
cp dbs/activity.db backups/activity_$(date +%Y%m%d).db

# 恢復資料庫
cp backups/activity_backup.db dbs/activity.db

# 資料庫查詢
sqlite3 dbs/activity.db "SELECT * FROM users LIMIT 10;"
```

## 日誌管理

### 日誌查看
```bash
# 查看即時日誌
tail -f logs/main.log

# 查看特定模組日誌
tail -f logs/activity_meter.log

# 搜尋日誌
grep "ERROR" logs/main.log
grep "用戶" logs/activity_meter.log

# 日誌分析
awk '/ERROR/ {print $0}' logs/main.log
```

### 日誌清理
```bash
# 清空日誌
> logs/main.log

# 刪除舊日誌
find logs/ -name "*.log" -mtime +7 -delete

# 日誌輪轉
logrotate -f logrotate.conf
```

## 部署命令

### 開發部署
```bash
# 開發環境啟動
export ENVIRONMENT=development
python main.py

# 檢查配置
python -c "import config; print(config.TOKEN[:10])"

# 測試連線
python -c "import discord; print(discord.__version__)"
```

### 生產部署
```bash
# 生產環境部署
python deploy.py

# 使用 supervisor 管理
sudo supervisorctl start discordbot
sudo supervisorctl status discordbot
sudo supervisorctl restart discordbot

# 使用 systemd 管理
sudo systemctl start discordbot
sudo systemctl enable discordbot
sudo systemctl status discordbot
```

## 監控命令

### 系統監控
```bash
# 查看進程
ps aux | grep python
pgrep -f "python main.py"

# 系統資源
top -p $(pgrep -f "python main.py")
htop

# 記憶體使用
free -h
vm_stat

# 磁碟使用
df -h
du -sh logs/
```

### 應用監控
```bash
# 檢查 Bot 狀態
curl -s http://localhost:8080/health

# 查看錯誤日誌
grep -A 5 -B 5 "ERROR" logs/main_error.log

# 統計日誌
wc -l logs/*.log
```

## 維護命令

### 清理命令
```bash
# 清理 Python 快取
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete

# 清理日誌
find logs/ -name "*.log" -size +100M -delete

# 清理備份
find backups/ -mtime +30 -delete
```

### 更新命令
```bash
# 更新依賴
pip install --upgrade -r requirement.txt

# 檢查更新
pip list --outdated

# 更新 Git 子模組
git submodule update --init --recursive
```

## 工具命令

### 開發工具
```bash
# 啟動 Jupyter（如有安裝）
jupyter notebook

# 啟動 IPython
ipython

# 檢查 Python 路徑
which python
python -c "import sys; print(sys.path)"
```

### 除錯工具
```bash
# Python 除錯器
python -m pdb main.py

# 檢查模組導入
python -c "import cogs.activity_meter; print('OK')"

# 檢查 Discord 連線
python -c "import discord; print('Discord version:', discord.__version__)"
```

## 常用組合命令

### 重新啟動流程
```bash
# 停止 → 更新 → 啟動
pkill -f "python main.py"
git pull
pip install --upgrade -r requirement.txt
python main.py
```

### 備份流程
```bash
# 完整備份
mkdir -p backups/$(date +%Y%m%d)
cp -r dbs/ backups/$(date +%Y%m%d)/
cp -r logs/ backups/$(date +%Y%m%d)/
```

### 故障排除
```bash
# 檢查環境
python --version
pip list | grep discord
echo $TOKEN | cut -c1-10

# 檢查權限
ls -la dbs/
ls -la logs/

# 測試連線
python -c "import os; print('TOKEN' in os.environ)"
```