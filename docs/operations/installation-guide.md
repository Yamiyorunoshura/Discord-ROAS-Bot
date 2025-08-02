# 系統安裝指南

## 概述

本指南將引導您在生產環境中安裝和部署 Discord ROAS Bot v2.0 成就系統。系統採用容器化部署，支援 Docker 和 Docker Compose。

## 系統需求

### 硬體需求
- **CPU**: 2 核心以上 (推薦 4 核心)
- **記憶體**: 4GB RAM 以上 (推薦 8GB)
- **儲存空間**: 20GB 可用空間 (推薦 50GB)
- **網路**: 穩定的互聯網連線

### 軟體需求
- **作業系統**: Ubuntu 20.04 LTS 或更新版本 / CentOS 8+ / Docker 支援的 Linux 發行版
- **Docker**: 20.10+ 版本
- **Docker Compose**: 2.0+ 版本
- **Git**: 2.25+ 版本

## 前置準備

### 1. 系統更新
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

### 2. 安裝 Docker
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 啟用 Docker 服務
sudo systemctl enable docker
sudo systemctl start docker
```

### 3. 安裝 Docker Compose
```bash
# 下載 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# 設置執行權限
sudo chmod +x /usr/local/bin/docker-compose

# 驗證安裝
docker-compose --version
```

### 4. 建立應用程式目錄
```bash
sudo mkdir -p /opt/discord-bot
sudo chown $USER:$USER /opt/discord-bot
cd /opt/discord-bot
```

## 安裝步驟

### 1. 取得原始碼
```bash
# 複製倉庫
git clone https://github.com/your-org/discord-roas-bot.git .

# 切換到指定版本（生產環境建議使用穩定版本）
git checkout v2.0.0
```

### 2. 配置環境變數
```bash
# 複製環境變數範本
cp .env.example .env.production

# 編輯配置文件
nano .env.production
```

必要的環境變數配置：
```env
# Discord Bot 配置
TOKEN=your_discord_bot_token_here
GUILD_ID=your_discord_guild_id

# 環境設定
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# 資料庫配置
DB_POOL_SIZE=20
DB_QUERY_TIMEOUT=30
DATABASE_URL=sqlite:///data/bot.db

# 安全配置
SECURITY_RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_SECOND=10
RATE_LIMIT_BURST=20

# 監控配置
MONITORING_ENABLED=true
HEALTH_CHECK_PORT=8080

# 快取配置
CACHE_TTL=300
CACHE_MAX_SIZE=1000
```

### 3. 設定資料存儲
```bash
# 建立資料目錄
mkdir -p data/databases
mkdir -p data/logs
mkdir -p data/backups

# 設定權限
chmod 755 data/
chmod 755 data/databases/
chmod 755 data/logs/
chmod 755 data/backups/
```

### 4. 部署應用程式
```bash
# 建置並啟動服務
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d

# 檢查服務狀態
docker-compose ps
```

### 5. 驗證安裝
```bash
# 檢查容器狀態
docker-compose logs -f discord-bot

# 檢查健康狀態
curl http://localhost:8080/health

# 測試 Bot 回應
# 在 Discord 中執行 /ping 指令測試
```

## 資料庫初始化

### 自動初始化
系統啟動時會自動檢查並初始化資料庫：
```bash
# 檢查初始化日誌
docker-compose logs discord-bot | grep "Database initialized"
```

### 手動初始化（如需要）
```bash
# 進入容器執行初始化
docker-compose exec discord-bot python -m src.core.database --init

# 驗證資料庫結構
docker-compose exec discord-bot python -m src.core.database --check
```

## SSL/TLS 配置（可選）

如需要 HTTPS 支援，可以配置反向代理：

### 使用 Nginx
```bash
# 安裝 Nginx
sudo apt install nginx -y

# 創建配置文件
sudo nano /etc/nginx/sites-available/discord-bot
```

Nginx 配置範例：
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# 啟用配置
sudo ln -s /etc/nginx/sites-available/discord-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 防火牆配置

```bash
# Ubuntu UFW
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw allow 8080/tcp    # 健康檢查 (內部使用)
sudo ufw enable

# CentOS/RHEL firewalld
sudo firewall-cmd --permanent --add-port=22/tcp
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload
```

## 服務管理

### 啟動服務
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d
```

### 停止服務
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
```

### 重啟服務
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml restart
```

### 查看日誌
```bash
# 即時日誌
docker-compose logs -f

# 特定服務日誌
docker-compose logs -f discord-bot

# 限制日誌行數
docker-compose logs --tail=100 discord-bot
```

## 系統服務設定（自動啟動）

### 創建 systemd 服務
```bash
sudo nano /etc/systemd/system/discord-bot.service
```

```ini
[Unit]
Description=Discord ROAS Bot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/discord-bot
ExecStart=/usr/local/bin/docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
User=discord-bot
Group=discord-bot

[Install]
WantedBy=multi-user.target
```

```bash
# 啟用服務
sudo systemctl daemon-reload
sudo systemctl enable discord-bot.service
sudo systemctl start discord-bot.service

# 檢查服務狀態
sudo systemctl status discord-bot.service
```

## 驗證安裝成功

### 1. 檢查系統狀態
```bash
# 檢查容器狀態
docker-compose ps

# 檢查系統資源
docker stats

# 檢查健康狀態
curl http://localhost:8080/health
```

### 2. 功能測試
- 在 Discord 中執行 `/ping` 測試基本連線
- 執行 `/achievement list` 測試成就系統
- 檢查日誌確認無錯誤訊息

### 3. 效能檢查
```bash
# 檢查記憶體使用
docker stats --no-stream

# 檢查磁碟空間
df -h

# 檢查網路連線
netstat -tlnp | grep 8080
```

## 故障排除

### 常見問題

1. **容器無法啟動**
   ```bash
   # 檢查日誌
   docker-compose logs discord-bot
   
   # 檢查配置
   docker-compose config
   ```

2. **Discord Bot 離線**
   ```bash
   # 檢查 token 配置
   grep TOKEN .env.production
   
   # 重啟服務
   docker-compose restart discord-bot
   ```

3. **資料庫連線問題**
   ```bash
   # 檢查資料庫文件權限
   ls -la data/databases/
   
   # 檢查資料庫連線
   docker-compose exec discord-bot python -c "from src.core.database import get_database; print('Database OK')"
   ```

4. **記憶體不足**
   ```bash
   # 檢查記憶體使用
   free -h
   docker stats
   
   # 調整 Docker 記憶體限制
   # 編輯 docker-compose.prod.yml 中的 mem_limit 設定
   ```

### 日誌收集
```bash
# 收集系統資訊用於故障排除
bash scripts/collect-system-info.sh > system-info.txt
```

## 下一步

安裝完成後，請參考：
- [配置管理指南](configuration-management.md) - 進階配置選項
- [監控和警報設定](monitoring-setup.md) - 系統監控配置
- [備份和恢復程序](backup-restore.md) - 資料保護設定
- [故障排除手冊](troubleshooting.md) - 常見問題解決

## 支援

如遇到安裝問題，請：
1. 檢查 [故障排除手冊](troubleshooting.md)
2. 查看 [系統需求](../architecture/infrastructure-and-deployment.md)
3. 聯繫技術支援團隊

---

**版本**: 2.0.0  
**最後更新**: 2025-08-01  
**作者**: 開發團隊