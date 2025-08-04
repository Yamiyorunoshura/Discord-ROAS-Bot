# Discord ADR Bot - 故障排除指南

本文件提供 Discord ADR Bot 常見問題的診斷和解決方案。

## 🚨 緊急故障排除

### Bot 完全無法啟動

#### 檢查清單
1. **驗證 Python 版本**:
   ```bash
   python3 --version  # 必須是 3.12+
   python3 -c "import sys; print(sys.version_info >= (3, 12))"
   ```

2. **檢查 Discord Token**:
   ```bash
   # 驗證 .env 檔案存在且格式正確
   cat .env | grep "TOKEN="
   
   # 測試 Token 有效性
   discord-adr-bot test-token
   ```

3. **驗證依賴安裝**:
   ```bash
   # 檢查虛擬環境
   source .venv/bin/activate
   pip list | grep discord
   
   # 重新安裝依賴
   uv pip install --upgrade discord-adr-bot
   ```

4. **檢查權限**:
   ```bash
   ls -la .env      # 應該有讀取權限
   ls -la logs/     # 應該有寫入權限
   ls -la data/     # 應該有讀寫權限
   ```

### 快速診斷指令
```bash
# 全面健康檢查
discord-adr-bot health-check

# 配置驗證
discord-adr-bot validate-config

# 連線測試
discord-adr-bot test-connection

# 檢視系統資訊
discord-adr-bot system-info
```

## 🔧 安裝相關問題

### Python 版本問題

#### 問題: Python 版本過舊
```
Error: Python 3.12 or later is required. Found: Python 3.10
```

**解決方案 - Ubuntu/Debian:**
```bash
# 添加 deadsnakes PPA
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update

# 安裝 Python 3.12
sudo apt install python3.12 python3.12-venv python3.12-pip

# 設定為預設版本
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
```

**解決方案 - CentOS/RHEL:**
```bash
# 啟用 EPEL 倉庫
sudo yum install epel-release

# 安裝 Python 3.12
sudo yum install python312 python312-pip

# 建立符號連結
sudo ln -sf /usr/bin/python3.12 /usr/bin/python3
```

**解決方案 - macOS:**
```bash
# 使用 Homebrew
brew install python@3.12
brew link python@3.12

# 或使用 pyenv
brew install pyenv
pyenv install 3.12.0
pyenv global 3.12.0
```

#### 問題: Python 找不到或路徑錯誤
```
bash: python3: command not found
```

**解決方案:**
```bash
# 檢查 Python 安裝位置
which python3
which python3.12

# 添加到 PATH（添加到 ~/.bashrc 或 ~/.zshrc）
export PATH="/usr/bin/python3.12:$PATH"

# 重新載入 shell 配置
source ~/.bashrc
```

### uv 包管理器問題

#### 問題: uv 安裝失敗
```
curl: command not found
```

**解決方案:**
```bash
# Ubuntu/Debian
sudo apt install curl wget

# CentOS/RHEL
sudo yum install curl wget

# 手動安裝 uv
pip install uv
```

#### 問題: uv 權限錯誤
```
Permission denied: uv
```

**解決方案:**
```bash
# 檢查 uv 路徑
which uv

# 添加到 PATH
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 或使用 pip 安裝
pip install --user uv
```

### 虛擬環境問題

#### 問題: 虛擬環境建立失敗
```
Error: Failed to create virtual environment
```

**解決方案:**
```bash
# 檢查 venv 模組
python3 -m venv --help

# Ubuntu/Debian 需要安裝 venv
sudo apt install python3.12-venv

# 清理並重新建立
rm -rf .venv
uv venv .venv
```

#### 問題: 虛擬環境啟動失敗
```
bash: .venv/bin/activate: No such file or directory
```

**解決方案:**
```bash
# 檢查虛擬環境結構
ls -la .venv/
ls -la .venv/bin/

# 重新建立虛擬環境
rm -rf .venv
python3 -m venv .venv
# 或
uv venv .venv
```

## 🌐 網路與連線問題

### Discord API 連線問題

#### 問題: 無法連接到 Discord API
```
aiohttp.ClientConnectorError: Cannot connect to host discord.com
```

**診斷步驟:**
```bash
# 測試基本網路連線
ping discord.com
ping 8.8.8.8

# 測試 HTTPS 連線
curl -I https://discord.com/api/v10/gateway

# 檢查 DNS 解析
nslookup discord.com
dig discord.com
```

**解決方案:**
```bash
# 檢查防火牆設定
sudo ufw status
sudo iptables -L

# 允許 HTTPS 輸出
sudo ufw allow out 443

# 檢查 proxy 設定
echo $HTTP_PROXY
echo $HTTPS_PROXY

# 如果使用 proxy，設定環境變數
export HTTPS_PROXY=http://proxy.example.com:8080
```

#### 問題: SSL 憑證錯誤
```
ssl.SSLCertVerificationError: certificate verify failed
```

**解決方案:**
```bash
# 更新 CA 憑證
# Ubuntu/Debian
sudo apt update && sudo apt install ca-certificates

# CentOS/RHEL
sudo yum update ca-certificates

# macOS
brew install ca-certificates

# 如果仍有問題，檢查系統時間
sudo ntpdate -s time.nist.gov
```

### 網路代理問題

#### 問題: 企業防火牆阻擋
**解決方案:**
```bash
# 設定 proxy 環境變數
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export NO_PROXY=localhost,127.0.0.1

# 在 .env 檔案中設定
echo "HTTP_PROXY=http://proxy.company.com:8080" >> .env
echo "HTTPS_PROXY=http://proxy.company.com:8080" >> .env
```

## 🔐 認證與權限問題

### Discord Token 問題

#### 問題: Token 無效或過期
```
discord.errors.LoginFailure: Improper token has been passed
```

**解決方案:**
1. **重新生成 Token**:
   - 前往 [Discord Developer Portal](https://discord.com/developers/applications)
   - 選擇您的應用程式
   - 在「Bot」頁面中點選「Reset Token」
   - 複製新 Token 到 `.env` 檔案

2. **檢查 Token 格式**:
   ```bash
   # Token 應該以這些前綴開始
   # Bot Token: 通常以 MTg... 或 NzA... 開始
   # 檢查 .env 檔案格式
   cat .env | grep "TOKEN="
   ```

#### 問題: Bot 權限不足
```
discord.errors.Forbidden: 403 Forbidden (error code: 50013)
```

**解決方案:**
1. **檢查 Bot 權限**:
   - 確認 Bot 有必要的權限
   - 檢查角色層級結構
   - 確認 Bot 角色位置

2. **必要權限清單**:
   ```
   - Send Messages
   - Read Message History
   - Manage Messages
   - Embed Links
   - Attach Files
   - Use Slash Commands
   - Manage Roles (如果需要)
   - Administrator (開發測試時)
   ```

### 檔案權限問題

#### 問題: 無法寫入日誌檔案
```
PermissionError: [Errno 13] Permission denied: 'logs/main.log'
```

**解決方案:**
```bash
# 檢查目錄權限
ls -la logs/

# 修復權限
chmod 755 logs/
chmod 644 logs/*.log

# 確保目錄存在
mkdir -p logs data

# 設定正確的擁有者
sudo chown -R $USER:$USER logs/ data/
```

## 🗄️ 資料庫問題

### SQLite 資料庫問題

#### 問題: 資料庫檔案鎖定
```
sqlite3.OperationalError: database is locked
```

**解決方案:**
```bash
# 檢查是否有其他程序使用資料庫
lsof data/*.db

# 強制停止所有 Bot 程序
pkill -f discord-adr-bot

# 檢查資料庫完整性
sqlite3 data/main.db "PRAGMA integrity_check;"

# 如果需要，重建資料庫
mv data/main.db data/main.db.backup
discord-adr-bot init-database
```

#### 問題: 資料庫損壞
```
sqlite3.DatabaseError: database disk image is malformed
```

**解決方案:**
```bash
# 嘗試修復資料庫
sqlite3 data/main.db ".recover" | sqlite3 data/main_recovered.db

# 或從備份恢復
cp data/backups/latest/main.db data/main.db

# 重新初始化資料庫（會遺失資料）
rm data/main.db
discord-adr-bot init-database
```

### 資料庫連線池問題

#### 問題: 連線池耗盡
```
asyncio.TimeoutError: Database connection timeout
```

**解決方案:**
```env
# 調整 .env 檔案中的設定
DB_POOL_SIZE=20
DB_QUERY_TIMEOUT=60
DB_MAX_CONNECTIONS=50
DB_CONNECTION_TIMEOUT=30
```

## 🧩 模組相關問題

### 活躍度系統問題

#### 問題: NumPy 安裝失敗
```
ImportError: No module named 'numpy'
```

**解決方案:**
```bash
# 安裝 NumPy 依賴
source .venv/bin/activate
uv pip install numpy>=1.24.0

# 或重新安裝整個套件
uv pip install --upgrade --force-reinstall discord-adr-bot
```

#### 問題: 圖片生成失敗
```
PIL.UnidentifiedImageError: cannot identify image file
```

**解決方案:**
```bash
# 安裝 Pillow 依賴
uv pip install Pillow>=11.2.1

# 檢查字體檔案
ls -la assets/fonts/

# 下載缺失的字體
mkdir -p assets/fonts
wget -O assets/fonts/default.ttf "https://fonts.google.com/download?family=Noto%20Sans%20TC"
```

### 歡迎系統問題

#### 問題: 頭像下載失敗
```
aiohttp.ClientTimeoutError: Timeout on downloading avatar
```

**解決方案:**
```env
# 調整超時設定
AVATAR_DOWNLOAD_TIMEOUT=30
HTTP_REQUEST_TIMEOUT=60
MAX_RETRY_ATTEMPTS=3
```

### 保護系統問題

#### 問題: 檔案掃描失敗
```
FileNotFoundError: [Errno 2] No such file or directory: 'temp_file'
```

**解決方案:**
```bash
# 確保臨時目錄存在
mkdir -p /tmp/discord-adr-bot

# 檢查磁碟空間
df -h /tmp

# 清理舊的臨時檔案
find /tmp -name "discord-adr-bot*" -mtime +1 -delete
```

## 🚀 效能問題

### 記憶體使用過高

#### 診斷:
```bash
# 檢查記憶體使用
ps aux | grep discord-adr-bot
top -p $(pgrep discord-adr-bot)

# 使用 htop 詳細監控
htop -p $(pgrep discord-adr-bot)
```

#### 解決方案:
```env
# 調整設定減少記憶體使用
CACHE_SIZE=1000
BATCH_SIZE=50
DB_POOL_SIZE=5
MAX_CONCURRENT_TASKS=10
```

### CPU 使用率過高

#### 診斷:
```bash
# 檢查 CPU 使用
top -p $(pgrep discord-adr-bot)

# 使用 perf 分析
sudo perf top -p $(pgrep discord-adr-bot)
```

#### 解決方案:
```env
# 調整處理頻率
MESSAGE_PROCESSING_INTERVAL=5
ACTIVITY_UPDATE_INTERVAL=60
CLEANUP_INTERVAL=3600
```

## 📋 系統資源問題

### 磁碟空間不足

#### 檢查:
```bash
# 檢查磁碟使用
df -h
du -sh logs/ data/

# 查找大檔案
find . -type f -size +100M
```

#### 清理:
```bash
# 清理舊日誌
find logs/ -name "*.log" -mtime +30 -delete

# 壓縮舊日誌
gzip logs/*.log.1

# 清理臨時檔案
rm -rf /tmp/discord-adr-bot*
```

### 檔案描述符不足

#### 問題:
```
OSError: [Errno 24] Too many open files
```

#### 解決方案:
```bash
# 檢查當前限制
ulimit -n

# 暫時增加限制
ulimit -n 65536

# 永久設定（添加到 /etc/security/limits.conf）
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf
```

## 🔍 日誌分析

### 日誌檔案位置
```bash
# 主要日誌檔案
logs/main.log              # 一般操作日誌
logs/error.log             # 錯誤日誌
logs/activity_meter.log    # 活躍度系統日誌
logs/welcome.log           # 歡迎系統日誌
logs/protection.log        # 保護系統日誌
logs/database.log          # 資料庫操作日誌

# 安裝與升級日誌
install.log                # 安裝日誌
upgrade.log               # 升級日誌
```

### 日誌分析指令
```bash
# 查看最新錯誤
tail -n 50 logs/error.log

# 搜尋特定錯誤
grep -i "error" logs/main.log

# 分析效能問題
grep -i "slow\|timeout\|performance" logs/*.log

# 統計錯誤類型
grep "ERROR" logs/main.log | cut -d' ' -f4- | sort | uniq -c | sort -nr
```

### 啟用除錯模式
```bash
# 暫時啟用除錯
discord-adr-bot run --debug

# 設定環境變數
export DEBUG=true
export LOG_LEVEL=DEBUG

# 或修改 .env 檔案
echo "DEBUG=true" >> .env
echo "LOG_LEVEL=DEBUG" >> .env
```

## 🆘 取得協助

### 自助資源
1. **檢查文件**: [安裝指南](installation.md)
2. **搜尋 GitHub Issues**: [GitHub 問題頁面](https://github.com/YOUR_USERNAME/discord-adr-bot/issues)
3. **查看範例配置**: `.env.example` 檔案

### 回報問題

#### 準備資訊
```bash
# 收集系統資訊
discord-adr-bot system-info > system_info.txt

# 收集日誌
tar -czf logs_$(date +%Y%m%d).tar.gz logs/

# 檢查配置（移除敏感資訊）
grep -v "TOKEN\|SECRET\|PASSWORD" .env > config_sanitized.txt
```

#### 問題回報範本
```
## 問題描述
簡述遇到的問題

## 環境資訊
- 作業系統: 
- Python 版本: 
- Bot 版本: 
- 安裝方式: 

## 重現步驟
1. 
2. 
3. 

## 錯誤訊息
```
[貼上錯誤訊息]
```

## 預期行為
描述預期的正常行為

## 額外資訊
- 日誌檔案: [附加相關日誌]
- 設定檔案: [附加去敏感化的設定]
```

### 聯繫支援
- **GitHub Issues**: [提交新問題](https://github.com/YOUR_USERNAME/discord-adr-bot/issues/new)
- **Discord 伺服器**: [加入支援伺服器](https://discord.gg/YOUR_INVITE)
- **Email**: support@your-domain.com

### 緊急支援
對於生產環境的緊急問題：
1. 檢查 [狀態頁面](https://status.your-domain.com)
2. 查看 [已知問題](https://github.com/YOUR_USERNAME/discord-adr-bot/issues?q=is%3Aissue+is%3Aopen+label%3Abug)
3. 聯繫緊急支援: emergency@your-domain.com