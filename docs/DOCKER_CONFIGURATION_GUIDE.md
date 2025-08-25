# ROAS Bot Docker配置使用指南

## 概述

ROAS Bot v2.4.3 提供三種不同的Docker配置，以滿足不同的開發和部署需求：

- **docker-compose.simple.yml** - 簡化開發環境，僅包含核心服務
- **docker-compose.dev.yml** - 完整開發環境，包含監控和可觀測性
- **docker-compose.prod.yml** - 生產環境配置，包含安全和高可用性

## 配置選擇指南

### 🚀 簡化開發環境 (`docker-compose.simple.yml`)

**適用場景：**
- 日常功能開發和測試
- 快速原型驗證
- 資源受限的開發環境
- 新手開發者快速上手

**包含服務：**
- `discord-bot` - Discord機器人主服務
- `redis` - 快取和會話存儲

**資源使用：**
- 總記憶體：~400MB
- 啟動時間：~45-60秒
- CPU使用：低

**使用方式：**
```bash
# 啟動簡化環境
docker-compose -f docker-compose.simple.yml up

# 後台運行
docker-compose -f docker-compose.simple.yml up -d

# 停止服務
docker-compose -f docker-compose.simple.yml down
```

### 🔧 完整開發環境 (`docker-compose.dev.yml`)

**適用場景：**
- 全功能開發和測試
- 性能分析和監控
- 整合測試和端到端驗證
- 生產前的完整測試

**包含服務：**
- `discord-bot` - Discord機器人主服務
- `redis` - 快取和會話存儲
- `prometheus` - 監控指標收集
- `grafana` - 監控數據視覺化

**資源使用：**
- 總記憶體：~1.2GB
- 啟動時間：~2-3分鐘
- CPU使用：中等

**存取端口：**
- Discord Bot: `http://localhost:8000` (健康檢查)
- Redis: `localhost:6379`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin)

**使用方式：**
```bash
# 啟動完整開發環境
docker-compose -f docker-compose.dev.yml up

# 後台運行
docker-compose -f docker-compose.dev.yml up -d

# 查看服務狀態
docker-compose -f docker-compose.dev.yml ps

# 查看日誌
docker-compose -f docker-compose.dev.yml logs -f discord-bot
```

### 🏭 生產環境 (`docker-compose.prod.yml`)

**適用場景：**
- 生產部署
- 高可用性需求
- 安全性要求高的環境
- 長期運行的服務

**包含服務：**
- `discord-bot` - Discord機器人主服務（高可用配置）
- `redis` - 快取服務（持久化存儲）
- `nginx` - 反向代理和SSL終止
- `backup` - 自動備份服務

**特色功能：**
- SSL/TLS 支援
- 自動備份
- 健康檢查和自動重啟
- 資源限制和優化

## 快速啟動指南

### 前置需求

1. **安裝Docker和Docker Compose**
   ```bash
   # macOS (使用Homebrew)
   brew install docker docker-compose
   
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install docker.io docker-compose
   
   # 驗證安裝
   docker --version
   docker-compose --version
   ```

2. **設置環境變數**
   ```bash
   # 複製環境變數模板
   cp .env.example .env
   
   # 編輯環境變數
   nano .env
   ```
   
   **必須設置的環境變數：**
   ```env
   DISCORD_TOKEN=your_discord_bot_token_here
   GRAFANA_PASSWORD=your_secure_password
   REDIS_PASSWORD=your_redis_password
   ```

### 第一次使用

1. **選擇合適的配置**
   ```bash
   # 新手推薦：簡化環境
   docker-compose -f docker-compose.simple.yml up -d
   
   # 完整功能：開發環境
   docker-compose -f docker-compose.dev.yml up -d
   ```

2. **驗證服務狀態**
   ```bash
   # 查看容器狀態
   docker-compose ps
   
   # 查看健康檢查
   docker-compose -f docker-compose.simple.yml ps
   ```

3. **檢查日誌**
   ```bash
   # 查看所有服務日誌
   docker-compose logs
   
   # 查看特定服務日誌
   docker-compose logs discord-bot
   
   # 實時追蹤日誌
   docker-compose logs -f
   ```

## 開發工作流程

### 日常開發

1. **代碼修改後重新啟動**
   ```bash
   # 重新建置並啟動
   docker-compose -f docker-compose.simple.yml up --build
   
   # 僅重啟特定服務
   docker-compose restart discord-bot
   ```

2. **調試支援**
   簡化環境支援debugpy調試：
   ```bash
   # 啟動時暴露調試端口
   docker-compose -f docker-compose.simple.yml up
   
   # 在IDE中連接到 localhost:5678
   ```

3. **測試執行**
   ```bash
   # 進入容器執行測試
   docker-compose exec discord-bot python -m pytest
   
   # 執行特定測試
   docker-compose exec discord-bot python -m pytest tests/test_specific.py
   ```

### 監控和故障排除

1. **健康狀態檢查**
   ```bash
   # 檢查所有服務健康狀態
   docker-compose ps
   
   # 檢查特定服務的詳細狀態
   docker inspect $(docker-compose ps -q discord-bot)
   ```

2. **資源監控**
   ```bash
   # 查看資源使用情況
   docker stats
   
   # 查看特定容器資源使用
   docker stats discord-bot-simple
   ```

3. **訪問監控面板**（開發環境）
   - Grafana: `http://localhost:3000`
   - Prometheus: `http://localhost:9090`

## 性能優化建議

### 簡化環境優化

1. **記憶體優化**
   - Discord Bot: 限制256MB，通常使用128-192MB
   - Redis: 限制150MB，通常使用64-96MB

2. **啟動時間優化**
   - 減少健康檢查頻率
   - 縮短服務間依賴等待時間
   - 使用本地Docker鏡像快取

### 開發環境優化

1. **監控服務調整**
   ```bash
   # 降低Prometheus抓取頻率
   # 編輯 monitoring/prometheus.yml
   scrape_interval: 30s  # 從15s增加到30s
   ```

2. **Grafana優化**
   - 禁用不需要的插件
   - 調整資料刷新間隔
   - 使用輕量級面板配置

## 故障排除

詳細的故障排除指南請參考下一節。

## 配置文件說明

### 環境變數

| 變數名 | 描述 | 必須 | 默認值 |
|--------|------|------|--------|
| `DISCORD_TOKEN` | Discord機器人令牌 | ✅ | - |
| `ENVIRONMENT` | 運行環境 | ❌ | `development` |
| `DEBUG` | 調試模式 | ❌ | `true` |
| `LOG_LEVEL` | 日誌級別 | ❌ | `DEBUG` |
| `REDIS_URL` | Redis連接字符串 | ❌ | `redis://redis:6379/0` |
| `HEALTH_CHECK_PORT` | 健康檢查端口 | ❌ | `8000` |
| `GRAFANA_PASSWORD` | Grafana管理員密碼 | ❌ | `admin` |
| `REDIS_PASSWORD` | Redis密碼（生產環境） | ❌ | - |

### 數據卷說明

| 卷名 | 用途 | 配置文件 |
|------|------|----------|
| `redis_simple_data` | Redis數據持久化 | simple.yml |
| `redis_data` | Redis數據持久化 | dev.yml, prod.yml |
| `prometheus_data` | Prometheus數據存儲 | dev.yml |
| `grafana_data` | Grafana配置和面板 | dev.yml |

### 網路配置

- **simple-network**: 簡化環境專用網路
- **discord-bot-network**: 開發和生產環境網路

所有服務都在同一個內部網路中，可以通過服務名稱互相訪問。

## 升級和遷移

### 從舊版本升級

```bash
# 停止舊版本
docker-compose down

# 拉取最新鏡像
docker-compose pull

# 啟動新版本
docker-compose up -d
```

### 數據備份

```bash
# 備份數據卷
docker run --rm -v roas-bot_redis_simple_data:/data -v $(pwd):/backup alpine tar czf /backup/redis-backup.tar.gz /data

# 恢復數據
docker run --rm -v roas-bot_redis_simple_data:/data -v $(pwd):/backup alpine tar xzf /backup/redis-backup.tar.gz
```

## 最佳實踐

1. **開發流程**
   - 使用簡化環境進行日常開發
   - 定期在完整環境中執行整合測試
   - 提交前在生產環境配置中進行最終驗證

2. **資源管理**
   - 定期清理未使用的Docker鏡像和卷
   - 監控磁碟空間使用
   - 設置合理的日誌輪轉策略

3. **安全考慮**
   - 不要在版本控制中提交環境變數檔案
   - 使用強密碼作為服務密碼
   - 定期更新Docker鏡像以獲得安全補丁

## 支援和幫助

如遇到問題，請按以下順序嘗試解決：

1. 查看本指南的故障排除章節
2. 檢查Docker和系統日誌
3. 參考專案的GitHub Issues
4. 聯繫開發團隊獲得支援

---

*本指南針對ROAS Bot v2.4.3編寫，如有問題請參考故障排除文檔或聯繫開發團隊。*