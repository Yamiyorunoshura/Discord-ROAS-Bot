# Discord ADR Bot - 安裝指南

本文件提供 Discord ADR Bot v2.0 的詳細安裝說明，涵蓋所有支援的作業系統和安裝方式。

## 📋 系統需求

### 基本需求
- **Python**: 3.12 或更高版本（必須）
- **記憶體**: 最少 512MB RAM（建議 1GB 以上）
- **硬碟空間**: 最少 100MB 可用空間
- **網路**: 穩定的網際網路連線

### 支援的作業系統
- **Windows**: Windows 10 (1903+) 或 Windows 11
- **Linux**: Ubuntu 20.04+, Debian 11+, CentOS 8+, Fedora 34+
- **macOS**: macOS 11 (Big Sur) 或更新版本

### 必要的 Discord 設定
- 有效的 Discord Bot Token
- Bot 必須被邀請到目標伺服器
- 適當的 Bot 權限設定

## 🚀 快速安裝

### Option 1: 自動安裝腳本（推薦）

#### Linux/macOS
```bash
# 方法 1: 直接執行（推薦）
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/discord-adr-bot/main/scripts/install.sh | bash

# 方法 2: 下載後執行
wget https://raw.githubusercontent.com/YOUR_USERNAME/discord-adr-bot/main/scripts/install.sh
chmod +x install.sh
./install.sh

# 方法 3: 使用 curl 下載
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/discord-adr-bot/main/scripts/install.sh
chmod +x install.sh
./install.sh
```

#### Windows PowerShell
```powershell
# 方法 1: 直接執行（推薦）
powershell -c "irm https://raw.githubusercontent.com/YOUR_USERNAME/discord-adr-bot/main/scripts/install.ps1 | iex"

# 方法 2: 下載後執行
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/YOUR_USERNAME/discord-adr-bot/main/scripts/install.ps1" -OutFile "install.ps1"
.\install.ps1

# 方法 3: 使用參數安裝
.\install.ps1 -InstallPath "C:\MyBot" -Force
```

### Option 2: 套件安裝

#### 使用預編譯套件
```bash
# 下載最新版本的 .whl 檔案
wget https://github.com/YOUR_USERNAME/discord-adr-bot/releases/latest/download/discord_adr_bot-*.whl

# 安裝套件
uv venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate.bat  # Windows

uv pip install discord_adr_bot-*.whl
```

## 🔧 詳細安裝步驟

### 步驟 1: 環境準備

#### 安裝 Python 3.12+

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-pip
```

**CentOS/RHEL/Fedora:**
```bash
# Fedora
sudo dnf install python3.12 python3.12-pip

# CentOS/RHEL (需要 EPEL)
sudo yum install epel-release
sudo yum install python312 python312-pip
```

**macOS:**
```bash
# 使用 Homebrew
brew install python@3.12

# 或使用 pyenv
brew install pyenv
pyenv install 3.12.0
pyenv global 3.12.0
```

**Windows:**
1. 前往 [Python 官網](https://www.python.org/downloads/windows/)
2. 下載 Python 3.12+ 安裝程式
3. 執行安裝程式，確保勾選「Add Python to PATH」
4. 驗證安裝：`python --version`

#### 安裝 uv 包管理器

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**或使用 pip:**
```bash
pip install uv
```

### 步驟 2: 下載與安裝

#### 方法 A: 從原始碼安裝

```bash
# 克隆專案
git clone https://github.com/YOUR_USERNAME/discord-adr-bot.git
cd discord-adr-bot

# 建立虛擬環境
uv venv .venv

# 啟動虛擬環境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows

# 安裝依賴
uv pip install -e .
```

#### 方法 B: 從發布版本安裝

```bash
# 下載最新發布版本
wget https://github.com/YOUR_USERNAME/discord-adr-bot/releases/latest/download/discord_adr_bot-2.1.0-py3-none-any.whl

# 建立安裝目錄
mkdir discord-adr-bot
cd discord-adr-bot

# 建立虛擬環境
uv venv .venv
source .venv/bin/activate

# 安裝套件
uv pip install ../discord_adr_bot-2.1.0-py3-none-any.whl
```

### 步驟 3: 配置設定

#### 建立配置檔案
```bash
# 複製範例配置
cp .env.example .env

# 編輯配置檔案
nano .env  # Linux/macOS
# 或
notepad .env  # Windows
```

#### 基本配置內容
```env
# Discord Bot Token (必須)
TOKEN=your_discord_bot_token_here

# 環境設定
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# 資料庫設定
DB_POOL_SIZE=10
DB_QUERY_TIMEOUT=30

# 安全設定
SECURITY_RATE_LIMIT_ENABLED=true

# 功能開關
ACTIVITY_METER_ENABLED=true
WELCOME_ENABLED=true
PROTECTION_ENABLED=true
MESSAGE_LISTENER_ENABLED=true
SYNC_DATA_ENABLED=true
```

### 步驟 4: Discord Bot 設定

#### 建立 Discord 應用程式
1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 點選「New Application」
3. 輸入應用程式名稱
4. 在「Bot」頁面中建立 Bot
5. 複製 Bot Token 到 `.env` 檔案

#### 設定 Bot 權限
必要權限：
- `Send Messages`
- `Read Message History`
- `Manage Messages`
- `Embed Links`
- `Attach Files`
- `Use Slash Commands`
- `Manage Roles`
- `View Channels`

#### 邀請 Bot 到伺服器
1. 在「OAuth2 > URL Generator」中選擇：
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: 選擇上述必要權限
2. 使用生成的 URL 邀請 Bot

### 步驟 5: 啟動與驗證

#### 啟動 Bot
```bash
# 使用已安裝的指令
discord-adr-bot run

# 或使用 Python 模組
python -m discord_adr_bot run

# 開發模式啟動
discord-adr-bot run --debug
```

#### 驗證安裝
```bash
# 檢查版本
discord-adr-bot --version

# 驗證配置
discord-adr-bot validate-config

# 測試連線
discord-adr-bot test-connection
```

## 🔄 升級與維護

### 升級到新版本

#### 使用升級腳本
```bash
# Linux/macOS
./scripts/upgrade.sh

# Windows
.\scripts\upgrade.ps1

# 強制升級
./scripts/upgrade.sh --force
```

#### 手動升級
```bash
# 停止 Bot
pkill -f discord-adr-bot

# 備份當前安裝
cp -r .venv .venv.backup
cp .env .env.backup

# 下載新版本
wget https://github.com/YOUR_USERNAME/discord-adr-bot/releases/latest/download/discord_adr_bot-*.whl

# 升級套件
source .venv/bin/activate
uv pip install --upgrade discord_adr_bot-*.whl

# 重新啟動
discord-adr-bot run
```

### 回滾到舊版本

```bash
# 使用升級腳本回滾
./scripts/upgrade.sh --rollback

# 手動回滾
rm -rf .venv
mv .venv.backup .venv
cp .env.backup .env
```

## 🐳 Docker 安裝

### 使用 Docker Compose（推薦）

建立 `docker-compose.yml`：
```yaml
version: '3.8'

services:
  discord-adr-bot:
    image: discord-adr-bot:latest
    container_name: discord-adr-bot
    restart: unless-stopped
    environment:
      - TOKEN=${TOKEN}
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./.env:/app/.env:ro
    networks:
      - bot-network

networks:
  bot-network:
    driver: bridge
```

啟動：
```bash
docker-compose up -d
```

### 使用 Docker

```bash
# 建立 Docker 映像
docker build -t discord-adr-bot .

# 運行容器
docker run -d \
  --name discord-adr-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/.env:/app/.env:ro \
  discord-adr-bot
```

## 🔒 安全性設定

### 檔案權限
```bash
# 設定適當的檔案權限
chmod 600 .env
chmod 755 scripts/*.sh
chmod -R 755 logs/
chmod -R 700 data/
```

### 防火牆設定
```bash
# Ubuntu/Debian
sudo ufw allow out 443  # Discord API
sudo ufw deny in 22     # 如果不需要 SSH

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --reload
```

## 📊 效能調校

### 系統最佳化
```bash
# 增加檔案描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 設定 swap（如果記憶體不足）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Bot 設定最佳化
```env
# 效能相關設定
DB_POOL_SIZE=20
DB_QUERY_TIMEOUT=60
CACHE_TTL=300
BATCH_SIZE=100
```

## 🚨 故障排除

### 常見問題

#### 1. Python 版本問題
```bash
# 檢查 Python 版本
python3 --version
python3.12 --version

# 設定預設 Python 版本
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
```

#### 2. 權限錯誤
```bash
# 修復權限
chmod +x scripts/*.sh
chown -R $USER:$USER .
```

#### 3. 依賴安裝失敗
```bash
# 清理並重新安裝
rm -rf .venv
uv venv .venv
source .venv/bin/activate
uv pip install --upgrade pip
uv pip install -e .
```

#### 4. Discord 連線問題
```bash
# 測試網路連線
curl -I https://discord.com/api/v10/gateway
ping discord.com

# 檢查 Token 有效性
discord-adr-bot test-token
```

### 日誌檔案位置
- **主要日誌**: `logs/main.log`
- **錯誤日誌**: `logs/error.log`
- **安裝日誌**: `install.log`
- **升級日誌**: `upgrade.log`

### 取得協助
如果遇到問題：
1. 檢查 [故障排除指南](troubleshooting.md)
2. 查看相關日誌檔案
3. 在 GitHub 上提交 Issue
4. 聯繫維護團隊

## 📚 相關文件
- [故障排除指南](troubleshooting.md)
- [配置說明](configuration.md)
- [API 文件](api.md)
- [開發指南](development.md)