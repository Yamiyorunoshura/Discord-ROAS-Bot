# Discord機器人Docker跨平台部署指南

**任務ID**: T6  
**版本**: 2.4.1  
**更新日期**: 2025-08-23

## 📋 概述

本指南提供Discord機器人的Docker容器化部署方案，支援跨平台一鍵啟動，包含完整的監控和健康檢查功能。

## 🎯 特性

- **跨平台支援**: Windows、macOS、Linux統一部署體驗
- **一鍵啟動**: 智能前置檢查與自動化部署
- **現代技術棧**: Python 3.13 + uv套件管理器
- **監控整合**: 內建Redis、Prometheus、Grafana監控棧
- **健康檢查**: 全面的容器健康狀態監控
- **彈性配置**: 支援開發、生產等多種環境配置

## 📋 系統需求

### 最低需求
- **Docker Engine**: >= 20.10.0
- **Docker Compose**: >= 2.0.0
- **可用記憶體**: >= 2GB
- **磁碟空間**: >= 5GB（包含映像和資料）

### 作業系統支援
- **Windows**: Windows 10/11 + Docker Desktop
- **macOS**: macOS 10.15+ + Docker Desktop  
- **Linux**: Ubuntu 20.04+, CentOS 8+, Debian 11+

## 🚀 快速開始

### 1. 環境準備

#### 複製環境配置檔案
```bash
# 複製環境範本（如果不存在）
cp .env .env.local  # 根據需要調整配置
```

#### 編輯環境變數 (.env)
```bash
# Discord設定
DISCORD_TOKEN=your_bot_token_here
DISCORD_APPLICATION_ID=your_application_id_here

# 環境設定
ENVIRONMENT=development  # development|production
DEBUG=true
LOG_LEVEL=DEBUG         # DEBUG|INFO|WARN|ERROR

# 安全設定
SECRET_KEY=your_secret_key_here
ENCRYPTION_KEY=your_encryption_key_here
```

### 2. 啟動服務

#### Unix/Linux/macOS
```bash
# 基本啟動
./scripts/start.sh

# 詳細模式啟動
./scripts/start.sh -v

# 生產環境啟動
./scripts/start.sh -p prod -v

# 使用自訂環境檔案
./scripts/start.sh -e .env.prod -p prod
```

#### Windows PowerShell
```powershell
# 基本啟動
.\scripts\start.ps1

# 詳細模式啟動
.\scripts\start.ps1 -Verbose

# 生產環境啟動
.\scripts\start.ps1 -Profile prod -Verbose

# 使用自訂環境檔案
.\scripts\start.ps1 -EnvFile .env.prod -Profile prod
```

### 3. 驗證部署

```bash
# 檢查容器健康狀態
./scripts/verify_container_health.sh

# 持續監控模式
./scripts/verify_container_health.sh -c -v

# JSON格式輸出
./scripts/verify_container_health.sh -f json
```

## 📊 服務配置檔案 (Profiles)

### default - 基本服務
僅包含Discord機器人和Redis快取
```bash
./scripts/start.sh -p default
```

### dev - 開發環境
包含開發工具和熱重載功能
```bash
./scripts/start.sh -p dev
```

### prod - 生產環境
完整監控棧，包含Prometheus和Grafana
```bash
./scripts/start.sh -p prod
```

### monitoring - 僅監控服務
僅啟動監控相關服務
```bash
./scripts/start.sh -p monitoring
```

## 🔧 腳本參數說明

### start.sh / start.ps1 參數

| 參數 | Unix | PowerShell | 說明 |
|------|------|------------|------|
| 環境檔案 | `-e, --env-file` | `-EnvFile` | 指定環境變數檔案 |
| 配置檔案 | `-p, --profile` | `-Profile` | 指定Docker Compose profile |
| 詳細輸出 | `-v, --verbose` | `-Verbose` | 顯示詳細執行資訊 |
| 強制重建 | `-f, --force-rebuild` | `-ForceRebuild` | 強制重建Docker映像 |
| 交互模式 | `-i, --interactive` | `-Interactive` | 前台運行（不使用-d） |
| 說明 | `-h, --help` | `-Help` | 顯示使用說明 |

### verify_container_health.sh 參數

| 參數 | 說明 |
|------|------|
| `-p, --profile` | 檢查指定profile的服務 |
| `-f, --format` | 輸出格式：text\|json |
| `-v, --verbose` | 顯示詳細健康資訊 |
| `-c, --continuous` | 持續監控模式 |
| `-i, --interval` | 監控間隔（秒） |
| `-t, --timeout` | 健康檢查超時時間 |

## 🌐 存取端點

### 開發環境 (dev profile)
- **Discord機器人**: 自動連接Discord
- **健康檢查**: http://localhost:8000/health
- **Redis**: localhost:6379

### 生產環境 (prod profile)  
- **Discord機器人**: 自動連接Discord
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **Redis**: localhost:6379

## 🔍 監控與日誌

### 查看服務狀態
```bash
# 查看所有服務狀態
docker compose -f docker/compose.yaml --profile default ps

# 查看特定服務日誌
docker compose -f docker/compose.yaml --profile default logs -f discord-bot

# 查看所有服務日誌
docker compose -f docker/compose.yaml --profile default logs -f
```

### 健康檢查
```bash
# 一次性檢查
./scripts/verify_container_health.sh

# 持續監控（每30秒）
./scripts/verify_container_health.sh -c

# JSON格式輸出（適合腳本處理）
./scripts/verify_container_health.sh -f json
```

## 🛠️ 常見操作

### 停止服務
```bash
# Unix/Linux/macOS
docker compose -f docker/compose.yaml --profile default down

# Windows
docker compose -f docker/compose.yaml --profile default down
```

### 重新啟動服務
```bash
# 停止並重新啟動
docker compose -f docker/compose.yaml --profile default restart

# 強制重建並啟動
./scripts/start.sh -f
```

### 查看資源使用
```bash
# 即時資源監控
docker stats

# 查看映像大小
docker images discord-bot
```

### 清理未使用資源
```bash
# 清理停止的容器、未使用的網路和映像
docker system prune

# 清理所有未使用資源（包含volume）
docker system prune -a --volumes
```

## 🐛 故障排查

### 常見問題

#### 1. Docker未運行
**錯誤**: `Cannot connect to the Docker daemon`
**解決方案**: 
- Windows/macOS: 啟動Docker Desktop
- Linux: `sudo systemctl start docker`

#### 2. 端口被佔用
**錯誤**: `Port already in use`
**解決方案**: 
- 檢查端口使用: `netstat -tulpn | grep :8000`
- 停止衝突服務或修改.env中的端口配置

#### 3. 記憶體不足
**錯誤**: 容器啟動失敗或OOM錯誤
**解決方案**:
- 增加Docker Desktop記憶體限制
- 調整docker/compose.yaml中的記憶體限制

#### 4. 環境變數缺失
**錯誤**: `DISCORD_TOKEN not found`
**解決方案**:
- 確認.env檔案存在並包含必要變數
- 檢查環境變數格式（無空格、正確的=號）

### 日誌分析

#### 查看啟動日誌
```bash
# 查看最近100行日誌
docker compose -f docker/compose.yaml --profile default logs --tail 100 discord-bot

# 實時追蹤日誌
docker compose -f docker/compose.yaml --profile default logs -f discord-bot
```

#### 查看錯誤日誌
```bash
# 搜尋錯誤日誌
docker compose logs discord-bot 2>&1 | grep -i error

# 搜尋警告日誌
docker compose logs discord-bot 2>&1 | grep -i warn
```

### 效能監控

#### 即時效能監控
```bash
# 查看容器資源使用
docker stats discord-bot-app

# 查看詳細系統資訊
docker system df
```

#### 健康檢查詳細資訊
```bash
# 查看容器健康檢查歷史
docker inspect discord-bot-app | jq '.[0].State.Health'

# 使用內建健康檢查工具
./scripts/verify_container_health.sh -v
```

## 📋 最佳實踐

### 開發環境
- 使用`dev` profile進行開發
- 啟用詳細日誌輸出 (`LOG_LEVEL=DEBUG`)
- 定期清理未使用的映像和容器

### 生產環境
- 使用`prod` profile
- 設定適當的記憶體和CPU限制
- 定期備份資料和配置
- 設定監控告警

### 安全性
- 定期更新Docker映像
- 使用強密碼和加密密鑰
- 限制容器權限
- 定期檢查安全漏洞

## 📚 參考資源

- [Docker官方文檔](https://docs.docker.com/)
- [Docker Compose文檔](https://docs.docker.com/compose/)
- [Python 3.13新特性](https://docs.python.org/3.13/whatsnew/)
- [uv套件管理器](https://github.com/astral-sh/uv)

## 🆘 技術支援

如遇到問題，請提供以下資訊：
1. 作業系統版本
2. Docker版本 (`docker --version`)
3. 錯誤訊息完整內容
4. 使用的命令和參數
5. 環境變數配置（隱藏敏感資訊）

---

**最後更新**: 2025-08-23  
**維護者**: Discord機器人開發團隊