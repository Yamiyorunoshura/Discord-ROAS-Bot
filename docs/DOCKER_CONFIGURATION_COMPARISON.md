# ROAS Bot Docker配置比較表

## 配置選擇快速參考

| 特性 | Simple | Development | Production |
|------|--------|-------------|------------|
| **配置文件** | `docker-compose.simple.yml` | `docker-compose.dev.yml` | `docker-compose.prod.yml` |
| **主要用途** | 快速開發測試 | 完整功能開發 | 生產部署 |
| **目標用戶** | 新手開發者、快速原型 | 資深開發者、整合測試 | 運維團隊、生產環境 |

## 服務組件對比

### 包含的服務

| 服務 | Simple | Development | Production |
|------|--------|-------------|------------|
| **Discord Bot** | ✅ | ✅ | ✅ |
| **Redis** | ✅ | ✅ | ✅ |
| **Prometheus** | ❌ | ✅ | ❌ |
| **Grafana** | ❌ | ✅ | ❌ |
| **Nginx** | ❌ | ❌ | ✅ |
| **Backup** | ❌ | ❌ | ✅ |

### 監控和可觀測性

| 功能 | Simple | Development | Production |
|------|--------|-------------|------------|
| **基礎健康檢查** | ✅ | ✅ | ✅ |
| **性能監控** | ❌ | ✅ | 外部監控 |
| **視覺化面板** | ❌ | ✅ (Grafana) | 外部監控 |
| **指標收集** | ❌ | ✅ (Prometheus) | 外部監控 |
| **日誌管理** | 基礎 | 完整 | 企業級 |
| **告警機制** | ❌ | ✅ | ✅ |

## 資源使用對比

### 記憶體使用

| 配置 | Discord Bot | Redis | 監控服務 | 總計 |
|------|-------------|-------|----------|------|
| **Simple** | 256M | 150M | - | ~400M |
| **Development** | 384M | 256M | ~576M | ~1.2G |
| **Production** | 1G | 512M | 外部 | ~1.5G+ |

### CPU使用

| 配置 | Discord Bot | Redis | 監控服務 | 總CPU限制 |
|------|-------------|-------|----------|-----------|
| **Simple** | 0.5核 | 0.25核 | - | 0.75核 |
| **Development** | 0.5核 | 0.25核 | 0.6核 | 1.35核 |
| **Production** | 0.5核 | 0.25核 | 外部 | 0.75核+ |

### 啟動時間對比

| 配置 | 預期啟動時間 | 健康檢查時間 | 總就緒時間 |
|------|-------------|-------------|-----------|
| **Simple** | 30-45秒 | 45秒 | ~1.5分鐘 |
| **Development** | 60-90秒 | 60秒 | ~2.5分鐘 |
| **Production** | 90-180秒 | 180秒 | ~5分鐘 |

## 端口映射對比

### Simple配置
- `8000:8000` - Discord Bot健康檢查
- `6379:6379` - Redis服務
- `5678:5678` - 調試端口 (debugpy)

### Development配置
- `8000:8000` - Discord Bot健康檢查
- `6379:6379` - Redis服務
- `9090:9090` - Prometheus Web界面
- `3000:3000` - Grafana面板

### Production配置
- `80:80` - HTTP (Nginx)
- `443:443` - HTTPS (Nginx)
- 內部服務不暴露到主機

## 功能特性對比

### 開發支援

| 功能 | Simple | Development | Production |
|------|--------|-------------|------------|
| **熱重載** | ✅ | ✅ | ❌ |
| **調試支援** | ✅ (debugpy) | ✅ | ❌ |
| **測試環境** | ✅ | ✅ | ❌ |
| **代碼掛載** | ✅ | ✅ | ❌ |
| **開發工具** | 基礎 | 完整 | ❌ |

### 生產準備

| 功能 | Simple | Development | Production |
|------|--------|-------------|------------|
| **SSL/TLS** | ❌ | ❌ | ✅ |
| **自動重啟** | ❌ | ❌ | ✅ |
| **自動備份** | ❌ | ❌ | ✅ |
| **負載均衡** | ❌ | ❌ | ✅ |
| **安全加固** | 基礎 | 基礎 | ✅ |

### 數據持久化

| 功能 | Simple | Development | Production |
|------|--------|-------------|------------|
| **Redis數據** | ✅ | ✅ | ✅ (增強) |
| **應用數據** | ✅ | ✅ | ✅ (備份) |
| **日誌數據** | ✅ | ✅ | ✅ (輪轉) |
| **配置數據** | 本地 | 本地 | 持久化 |
| **監控數據** | ❌ | ✅ | 外部存儲 |

## 使用場景建議

### Simple配置適用於：
- ✅ 新手開發者快速上手
- ✅ 功能原型開發和驗證
- ✅ 資源受限的開發環境
- ✅ 日常功能開發和修改
- ✅ 單元測試和基礎測試
- ❌ 性能測試和壓力測試
- ❌ 完整系統整合測試

### Development配置適用於：
- ✅ 完整功能開發和測試
- ✅ 系統整合測試
- ✅ 性能分析和優化
- ✅ 監控配置開發
- ✅ 生產前完整驗證
- ❌ 資源受限環境
- ❌ 生產環境部署

### Production配置適用於：
- ✅ 生產環境部署
- ✅ 高可用性需求
- ✅ 安全性要求高的環境
- ✅ 大規模用戶服務
- ✅ 長期穩定運行
- ❌ 開發和測試
- ❌ 頻繁代碼修改

## 遷移路徑

### 從Simple到Development
```bash
# 停止Simple環境
docker-compose -f docker-compose.simple.yml down

# 啟動Development環境
docker-compose -f docker-compose.dev.yml up -d

# 訪問監控面板
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
```

### 從Development到Production
```bash
# 停止Development環境
docker-compose -f docker-compose.dev.yml down

# 配置生產環境變數
cp .env.example .env.prod
# 編輯 .env.prod，設置生產環境配置

# 啟動Production環境
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## 性能優化建議

### Simple配置優化
- 使用SSD存儲提升I/O性能
- 調整Redis記憶體分配（如需要）
- 啟用Docker BuildKit加速構建

### Development配置優化
- 分配足夠的系統記憶體（推薦4GB+）
- 使用快速存儲設備
- 調整監控數據收集間隔
- 配置合理的數據保留期限

### Production配置優化
- 使用專用監控解決方案
- 實施適當的備份策略
- 配置SSL證書和安全配置
- 設置負載均衡和故障轉移

## 故障排除快速參考

| 問題類型 | Simple | Development | Production |
|----------|--------|-------------|------------|
| **啟動失敗** | 檢查env變數、端口衝突 | 同左 + 監控服務配置 | 同左 + SSL證書、權限 |
| **性能問題** | 調整資源限制 | 調整監控頻率 | 檢查外部監控 |
| **連接問題** | Redis連接、網路配置 | 同左 + 監控端口 | 同左 + Nginx配置 |
| **數據問題** | 檢查卷掛載 | 同左 + 監控數據 | 同左 + 備份恢復 |

---

*此比較表基於ROAS Bot v2.4.3配置文件編寫。選擇適合的配置文件可以提升開發效率並滿足不同環境的需求。*