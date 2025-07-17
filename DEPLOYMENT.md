# Discord ADR Bot v1.6 - 部署指南

## 📋 目錄
- [v1.6 新功能](#v16-新功能)
- [部署環境](#部署環境)
- [本地部署](#本地部署)
- [伺服器部署](#伺服器部署)
- [容器化部署](#容器化部署)
- [性能監控](#性能監控)
- [監控與維護](#監控與維護)
- [故障排除](#故障排除)

## 🆕 v1.6 新功能

### 🚀 性能優化系統
- **智能緩存管理**: 自適應緩存策略，預載入機制
- **高級資料庫連接池**: 負載均衡，連接預熱，自動故障恢復
- **事件匯流排優化**: 批處理，事件壓縮，多工作者架構
- **性能監控儀表板**: 實時性能指標，6個專業監控頁面

### 🔧 管理工具增強
- **性能監控指令**: `/性能監控` - 管理員專用實時監控
- **代碼品質檢查**: `quality_check.py` - 自動化品質檢查
- **測試框架完善**: 24個性能監控測試用例
- **CI/CD 支持**: GitHub Actions 工作流程範本

### 📊 監控能力
- **實時性能指標**: CPU、記憶體、磁碟、網路使用率
- **組件統計**: 緩存命中率、資料庫性能、事件處理統計
- **智能警報**: 三級警報系統（嚴重、警告、建議）
- **性能報告**: JSON格式完整性能報告導出

## 🖥️ 部署環境

### 系統需求
- **作業系統**: Linux (推薦 Ubuntu 20.04+)、Windows 10+、macOS 10.15+
- **Python**: 3.8 或更高版本
- **記憶體**: 最少 512MB RAM，推薦 1GB+
- **磁碟空間**: 最少 100MB，推薦 500MB+
- **網路**: 穩定的網際網路連線

### 支援平台
- ✅ Ubuntu 20.04/22.04
- ✅ CentOS 7/8
- ✅ Debian 10/11
- ✅ Windows 10/11
- ✅ macOS 10.15+
- ✅ Docker (所有平台)

## 🏠 本地部署

### 1. 環境準備

#### Windows
```powershell
# 安裝 Python (如果尚未安裝)
# 從 https://python.org 下載並安裝

# 建立專案目錄
mkdir "Discord ADR Bot v1.5"
cd "Discord ADR Bot v1.5"

# 建立虛擬環境
python -m venv venv
venv\Scripts\activate

# 安裝依賴
pip install -r requirement.txt
```

#### Linux/macOS
```bash
# 安裝 Python (Ubuntu/Debian)
sudo apt update
sudo apt install python3 python3-pip python3-venv

# 建立專案目錄
mkdir "Discord ADR Bot v1.5"
cd "Discord ADR Bot v1.5"

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirement.txt
```

### 2. 配置設定

#### 建立環境變數檔案
```bash
# 建立 .env 檔案
touch .env
```

#### 編輯 .env 檔案
```env
# Discord Bot 設定
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_GUILD_ID=your_guild_id_here

# 環境設定
ENVIRONMENT=development
LOG_LEVEL=INFO

# 資料庫設定
DATABASE_PATH=dbs/
BACKUP_ENABLED=true
BACKUP_INTERVAL=24

# 網路設定
REQUEST_TIMEOUT=30
MAX_RETRIES=3

# 效能設定
CACHE_SIZE=1000
BATCH_SIZE=50
```

### 3. 啟動機器人

#### 直接啟動
```bash
# 啟動機器人
python main.py
```

#### 使用啟動腳本
```bash
# 建立啟動腳本
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python main.py
EOF

# 設定執行權限
chmod +x start.sh

# 啟動
./start.sh
```

## 🖥️ 伺服器部署

### 1. 伺服器準備

#### Ubuntu/Debian 系統
```bash
# 更新系統
sudo apt update && sudo apt upgrade -y

# 安裝必要套件
sudo apt install -y python3 python3-pip python3-venv git curl wget

# 建立用戶 (推薦)
sudo adduser discordbot
sudo usermod -aG sudo discordbot
su - discordbot
```

#### CentOS/RHEL 系統
```bash
# 更新系統
sudo yum update -y

# 安裝必要套件
sudo yum install -y python3 python3-pip git curl wget

# 建立用戶
sudo adduser discordbot
sudo usermod -aG wheel discordbot
su - discordbot
```

### 2. 專案部署

#### 克隆專案
```bash
# 切換到用戶目錄
cd ~

# 克隆專案
git clone <repository-url> "Discord ADR Bot v1.5"
cd "Discord ADR Bot v1.5"

# 建立虛擬環境
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirement.txt
```

#### 設定環境變數
```bash
# 建立生產環境配置
cp .env.example .env.production

# 編輯配置
nano .env.production
```

### 3. 使用 Systemd 管理

#### 建立服務檔案
```bash
sudo nano /etc/systemd/system/discord-adr-bot.service
```

#### 服務檔案內容
```ini
[Unit]
Description=Discord ADR Bot v1.5
After=network.target

[Service]
Type=simple
User=discordbot
WorkingDirectory=/home/discordbot/Discord ADR bot v1.5
Environment=PATH=/home/discordbot/Discord ADR bot v1.5/venv/bin
ExecStart=/home/discordbot/Discord ADR bot v1.5/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 啟動服務
```bash
# 重新載入 systemd
sudo systemctl daemon-reload

# 啟用服務
sudo systemctl enable discord-adr-bot

# 啟動服務
sudo systemctl start discord-adr-bot

# 檢查狀態
sudo systemctl status discord-adr-bot

# 查看日誌
sudo journalctl -u discord-adr-bot -f
```

### 4. 使用 Supervisor 管理

#### 安裝 Supervisor
```bash
sudo apt install supervisor
```

#### 建立配置檔案
```bash
sudo nano /etc/supervisor/conf.d/discord-adr-bot.conf
```

#### 配置檔案內容
```ini
[program:discord-adr-bot]
command=/home/discordbot/Discord ADR bot v1.5/venv/bin/python main.py
directory=/home/discordbot/Discord ADR bot v1.5
user=discordbot
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/discord-adr-bot.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
```

#### 啟動服務
```bash
# 重新載入配置
sudo supervisorctl reread
sudo supervisorctl update

# 啟動服務
sudo supervisorctl start discord-adr-bot

# 檢查狀態
sudo supervisorctl status discord-adr-bot
```

## 🐳 容器化部署

### 1. Docker 部署

#### 建立 Dockerfile
```dockerfile
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴檔案
COPY requirement.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirement.txt

# 複製專案檔案
COPY . .

# 建立必要目錄
RUN mkdir -p logs dbs data fonts

# 設定環境變數
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 暴露端口 (如果需要)
EXPOSE 8000

# 啟動命令
CMD ["python", "main.py"]
```

#### 建立 docker-compose.yml
```yaml
version: '3.8'

services:
  discord-bot:
    build: .
    container_name: discord-adr-bot
    restart: unless-stopped
    environment:
      - DISCORD_TOKEN=${DISCORD_TOKEN}
      - DISCORD_GUILD_ID=${DISCORD_GUILD_ID}
      - ENVIRONMENT=production
    volumes:
      - ./logs:/app/logs
      - ./dbs:/app/dbs
      - ./data:/app/data
    networks:
      - bot-network

networks:
  bot-network:
    driver: bridge
```

#### 建立 .dockerignore
```
venv/
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
.env
.env.*
logs/
dbs/
.git/
.gitignore
README.md
CHANGELOG.md
```

#### 部署命令
```bash
# 建立映像
docker build -t discord-adr-bot:v1.5 .

# 使用 docker-compose 部署
docker-compose up -d

# 查看日誌
docker-compose logs -f

# 停止服務
docker-compose down
```

### 2. Kubernetes 部署

#### 建立 ConfigMap
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: discord-bot-config
data:
  config.py: |
    # 配置內容
```

#### 建立 Secret
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: discord-bot-secrets
type: Opaque
data:
  DISCORD_TOKEN: <base64-encoded-token>
  DISCORD_GUILD_ID: <base64-encoded-guild-id>
```

#### 建立 Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: discord-adr-bot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: discord-adr-bot
  template:
    metadata:
      labels:
        app: discord-adr-bot
    spec:
      containers:
      - name: discord-bot
        image: discord-adr-bot:v1.5
        env:
        - name: DISCORD_TOKEN
          valueFrom:
            secretKeyRef:
              name: discord-bot-secrets
              key: DISCORD_TOKEN
        - name: DISCORD_GUILD_ID
          valueFrom:
            secretKeyRef:
              name: discord-bot-secrets
              key: DISCORD_GUILD_ID
        volumeMounts:
        - name: logs
          mountPath: /app/logs
        - name: dbs
          mountPath: /app/dbs
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: discord-bot-logs-pvc
      - name: dbs
        persistentVolumeClaim:
          claimName: discord-bot-dbs-pvc
```

## 📊 監控與維護

### 1. 日誌監控

#### 設定日誌輪轉
```bash
# 建立 logrotate 配置
sudo nano /etc/logrotate.d/discord-adr-bot
```

```conf
/home/discordbot/Discord ADR bot v1.5/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 discordbot discordbot
    postrotate
        systemctl reload discord-adr-bot
    endscript
}
```

#### 監控腳本
```bash
#!/bin/bash
# 建立監控腳本
cat > monitor.sh << 'EOF'
#!/bin/bash

LOG_FILE="/home/discordbot/Discord ADR bot v1.5/logs/main_error.log"
ALERT_EMAIL="admin@example.com"

# 檢查錯誤數量
ERROR_COUNT=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")

if [ "$ERROR_COUNT" -gt 10 ]; then
    echo "警告：Discord Bot 錯誤數量過多 ($ERROR_COUNT)" | mail -s "Discord Bot 警告" "$ALERT_EMAIL"
fi

# 檢查磁碟空間
DISK_USAGE=$(df /home/discordbot | tail -1 | awk '{print $5}' | sed 's/%//')

if [ "$DISK_USAGE" -gt 80 ]; then
    echo "警告：磁碟空間不足 ($DISK_USAGE%)" | mail -s "Discord Bot 警告" "$ALERT_EMAIL"
fi
EOF

chmod +x monitor.sh
```

### 2. 效能監控

#### 使用 Prometheus + Grafana
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'discord-bot'
    static_configs:
      - targets: ['localhost:8000']
```

#### 自定義指標
```python
from prometheus_client import Counter, Histogram, Gauge

# 定義指標
message_counter = Counter('discord_messages_total', 'Total messages processed')
command_duration = Histogram('discord_command_duration_seconds', 'Command execution time')
active_users = Gauge('discord_active_users', 'Number of active users')
```

### 3. 備份策略

#### 自動備份腳本
```bash
#!/bin/bash
# 建立備份腳本
cat > backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/backup/discord-bot"
DATE=$(date +%Y%m%d_%H%M%S)
SOURCE_DIR="/home/discordbot/Discord ADR bot v1.5"

# 建立備份目錄
mkdir -p "$BACKUP_DIR"

# 備份資料庫
tar -czf "$BACKUP_DIR/dbs_$DATE.tar.gz" -C "$SOURCE_DIR" dbs/

# 備份配置
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C "$SOURCE_DIR" .env* config.py

# 清理舊備份 (保留 30 天)
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete

echo "備份完成：$DATE"
EOF

chmod +x backup.sh
```

#### 設定定時備份
```bash
# 加入 crontab
crontab -e

# 每天凌晨 2 點執行備份
0 2 * * * /home/discordbot/backup.sh
```

## 🔧 故障排除

### 1. 常見問題

#### 機器人無法啟動
```bash
# 檢查日誌
tail -f logs/main_error.log

# 檢查權限
ls -la dbs/ logs/

# 檢查環境變數
echo $DISCORD_TOKEN
```

#### 記憶體使用過高
```bash
# 檢查記憶體使用
ps aux | grep python

# 重啟服務
sudo systemctl restart discord-adr-bot
```

#### 網路連線問題
```bash
# 檢查網路連線
ping discord.com

# 檢查防火牆
sudo ufw status
```

### 2. 效能調優

#### 系統層級
```bash
# 調整檔案描述符限制
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 調整 TCP 參數
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf
sysctl -p
```

#### 應用層級
```python
# 調整資料庫連線池
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 30

# 調整快取大小
CACHE_SIZE = 2000
CACHE_TTL = 3600
```

### 3. 安全建議

#### 防火牆設定
```bash
# 只允許必要端口
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

#### 定期更新
```bash
# 建立更新腳本
cat > update.sh << 'EOF'
#!/bin/bash
cd /home/discordbot/Discord ADR bot v1.6
git pull
source venv/bin/activate
pip install -r requirement.txt
sudo systemctl restart discord-adr-bot
EOF

chmod +x update.sh
```

## 📊 性能監控

### 1. 性能監控儀表板

#### 啟用監控
```bash
# 使用 Discord 斜線指令
/性能監控
```

#### 監控頁面
- **📊 系統概覽**: 整體性能狀態
- **🗄️ 緩存統計**: 緩存系統詳細指標
- **🗃️ 資料庫性能**: 連接池和查詢統計
- **📡 事件匯流排**: 事件處理性能分析
- **💻 系統資源**: 詳細的系統資源監控
- **🚨 性能警報**: 警報和優化建議

### 2. 性能基準

#### 正常範圍
```
CPU使用率: < 70%
記憶體使用率: < 80%
磁碟使用率: < 85%
Bot延遲: < 200ms
緩存命中率: > 80%
查詢成功率: > 99%
```

#### 警告閾值
```
CPU使用率: 70-90%
記憶體使用率: 80-95%
磁碟使用率: 85-98%
Bot延遲: 200-500ms
```

### 3. 代碼品質檢查

#### 執行品質檢查
```bash
# 運行完整品質檢查
python quality_check.py

# 檢查特定組件
python -m pytest tests/unit/test_performance_dashboard.py -v
```

#### 品質報告
```bash
# 查看品質報告
cat quality_report.json

# 檢查測試覆蓋率
python -m pytest --cov=cogs --cov-report=html
```

### 4. 性能優化建議

#### 系統層級優化
```bash
# 增加檔案描述符限制
ulimit -n 65536

# 調整 Python 垃圾回收
export PYTHONOPTIMIZE=1
```

#### 應用層級優化
```python
# 調整緩存設定
CACHE_STRATEGY = "ADAPTIVE"
CACHE_MAX_SIZE = 2000
CACHE_PRELOAD_ENABLED = True

# 調整資料庫連接池
DB_POOL_SIZE = 10
DB_POOL_STRATEGY = "ADAPTIVE"
DB_PREWARMING_ENABLED = True

# 調整事件處理
EVENT_BATCH_SIZE = 50
EVENT_COMPRESSION_ENABLED = True
EVENT_WORKERS = 4
```

---

## 📞 支援

### 聯絡方式
- **GitHub Issues**: 提交問題報告
- **Discord**: 加入支援伺服器
- **Email**: 發送詳細報告

### 文件資源
- [README.md](README.md) - 專案介紹
- [CHANGELOG.md](CHANGELOG.md) - 更新日誌
- [README_ERROR_HANDLING.md](README_ERROR_HANDLING.md) - 錯誤處理指南

---

**注意事項**：
- 部署前請備份重要資料
- 定期檢查系統資源使用
- 保持系統與依賴套件更新
- 監控機器人運行狀態 