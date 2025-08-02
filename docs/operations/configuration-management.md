# 配置管理指南

## 概述

Discord ROAS Bot v2.1 採用現代化的配置管理系統，支援多來源配置、環境變數覆蓋、配置驗證和熱重載。本指南涵蓋所有配置選項和管理最佳實踐。

## 配置系統架構

### 配置層級（優先級由高到低）

1. **命令列參數** - 最高優先級
2. **環境變數** - 運行時配置
3. **配置文件** (.env, config.yaml) - 靜態配置
4. **預設值** - 程式碼內建預設值

### 配置文件位置

```
/opt/discord-bot/
├── .env                    # 基礎環境配置
├── .env.production         # 生產環境配置
├── .env.development        # 開發環境配置
├── config.yaml             # YAML 格式配置（可選）
└── configs/                # 分模組配置目錄
    ├── discord.yaml
    ├── database.yaml
    ├── achievement.yaml
    └── security.yaml
```

## 核心配置項目

### Discord Bot 配置

```env
# 必要配置
TOKEN=your_discord_bot_token                    # Discord Bot Token
GUILD_ID=123456789012345678                     # 主要伺服器 ID

# 可選配置
APPLICATION_ID=987654321098765432               # Discord 應用程式 ID
CLIENT_SECRET=your_client_secret                # OAuth2 客戶端密鑰
COMMAND_PREFIX=!                                # 傳統指令前綴（備用）
```

### 環境與除錯配置

```env
# 環境設定
ENVIRONMENT=production                          # production|staging|development
DEBUG=false                                     # 除錯模式開關
LOG_LEVEL=INFO                                  # DEBUG|INFO|WARNING|ERROR|CRITICAL

# 開發工具
PROFILING_ENABLED=false                         # 效能分析
METRICS_COLLECTION=true                         # 指標收集
```

### 資料庫配置

```env
# SQLite 配置
DATABASE_URL=sqlite:///data/databases/bot.db    # 主資料庫路徑
DB_POOL_SIZE=20                                 # 連線池大小
DB_QUERY_TIMEOUT=30                             # 查詢超時（秒）
DB_WAL_MODE=true                                # WAL 模式啟用

# 備份配置
DB_BACKUP_ENABLED=true                          # 自動備份
DB_BACKUP_INTERVAL=3600                         # 備份間隔（秒）
DB_BACKUP_RETENTION=7                           # 備份保留天數
```

### 安全配置

```env
# 速率限制
SECURITY_RATE_LIMIT_ENABLED=true               # 速率限制啟用
RATE_LIMIT_PER_SECOND=10                       # 每秒請求數
RATE_LIMIT_BURST=20                            # 突發請求上限
RATE_LIMIT_WINDOW=60                           # 限制視窗（秒）

# 認證與授權
AUTH_REQUIRED=true                             # 認證需求
ADMIN_ROLE_ID=123456789012345678              # 管理員角色 ID
MODERATOR_ROLE_IDS=123,456,789                # 版主角色 ID 列表

# 資料保護
ENCRYPT_SENSITIVE_DATA=true                    # 敏感資料加密
LOG_SENSITIVE_DATA=false                       # 禁止記錄敏感資料
```

### 快取配置

```env
# 記憶體快取
CACHE_ENABLED=true                             # 快取啟用
CACHE_TTL=300                                  # 快取存活時間（秒）
CACHE_MAX_SIZE=1000                            # 快取最大項目數
CACHE_CLEANUP_INTERVAL=600                     # 清理間隔（秒）

# Redis 配置（可選）
REDIS_URL=redis://localhost:6379/0            # Redis 連線 URL
REDIS_PASSWORD=your_redis_password             # Redis 密碼
```

### 監控配置

```env
# 健康檢查
MONITORING_ENABLED=true                        # 監控啟用
HEALTH_CHECK_PORT=8080                         # 健康檢查埠
HEALTH_CHECK_PATH=/health                      # 健康檢查路徑

# 指標收集
METRICS_ENABLED=true                           # 指標收集
METRICS_PORT=9090                              # 指標暴露埠
METRICS_INTERVAL=60                            # 收集間隔（秒）

# 日誌配置
LOG_FILE_PATH=data/logs/bot.log               # 日誌文件路徑
LOG_ROTATION_SIZE=10MB                         # 日誌輪轉大小
LOG_RETENTION_DAYS=30                          # 日誌保留天數
LOG_FORMAT=json                                # 日誌格式：json|text
```

## 模組特定配置

### 成就系統配置

```yaml
# config/achievement.yaml
achievement:
  enabled: true
  cache_duration: 300                          # 成就快取時間
  notification:
    enabled: true
    channel_id: null                           # 通知頻道（null = DM）
    mention_role: false                        # 是否提及角色
  leaderboard:
    max_entries: 100                           # 排行榜最大條目
    update_interval: 3600                      # 更新間隔
  badge_generation:
    enabled: true
    image_format: png                          # 圖片格式
    cache_path: data/cache/badges              # 徽章快取路徑
```

### 活動追蹤配置

```yaml
# config/activity.yaml
activity_meter:
  enabled: true
  tracking:
    messages: true                             # 追蹤訊息
    voice_time: true                          # 追蹤語音時間
    reactions: true                           # 追蹤反應
  scoring:
    message_weight: 1.0                       # 訊息權重
    voice_weight: 2.0                         # 語音權重
    reaction_weight: 0.5                      # 反應權重
  cleanup:
    retention_days: 90                        # 資料保留天數
    cleanup_interval: 86400                   # 清理間隔
```

## 環境特定配置

### 開發環境 (.env.development)

```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
DB_POOL_SIZE=5
CACHE_TTL=60
PROFILING_ENABLED=true
METRICS_COLLECTION=false
```

### 測試環境 (.env.staging)

```env
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=INFO
DB_POOL_SIZE=10
CACHE_TTL=180
RATE_LIMIT_PER_SECOND=20
```

### 生產環境 (.env.production)

```env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
DB_POOL_SIZE=20
CACHE_TTL=300
SECURITY_RATE_LIMIT_ENABLED=true
ENCRYPT_SENSITIVE_DATA=true
```

## 配置管理最佳實踐

### 1. 安全配置管理

```bash
# 設定環境文件權限
chmod 600 .env*
chown discord-bot:discord-bot .env*

# 使用 Docker secrets（推薦）
echo "your_token_here" | docker secret create discord_token -
```

### 2. 配置驗證

```bash
# 驗證配置文件語法
docker-compose config

# 驗證應用程式配置
docker-compose exec discord-bot python -m src.core.config --validate

# 檢查敏感資料洩漏
grep -r "TOKEN\|SECRET\|PASSWORD" .env* || echo "No secrets found in config"
```

### 3. 配置備份

```bash
# 建立配置備份
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env* config.yaml configs/

# 定期備份腳本
cat > backup-config.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/discord-bot/backups/config"
mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/config-$(date +%Y%m%d-%H%M%S).tar.gz" .env* config.yaml configs/
find "$BACKUP_DIR" -name "config-*.tar.gz" -mtime +7 -delete
EOF

chmod +x backup-config.sh
```

### 4. 配置版本控制

```bash
# 建立配置範本（移除敏感資料）
cp .env.production .env.production.template
sed -i 's/TOKEN=.*/TOKEN=your_discord_token_here/' .env.production.template

# Git 忽略敏感配置
echo ".env*" >> .gitignore
echo "!.env.*.template" >> .gitignore
```

## 動態配置管理

### 配置熱重載

```python
# 支援運行時配置更新的項目
SUPPORTED_HOT_RELOAD = [
    'LOG_LEVEL',
    'CACHE_TTL',
    'RATE_LIMIT_PER_SECOND',
    'MONITORING_ENABLED'
]

# 重載配置指令
docker-compose exec discord-bot python -m src.core.config --reload
```

### 配置監控

```bash
# 監控配置文件變更
inotifywait -m .env.production -e modify --format '%w%f %e %T' --timefmt '%Y-%m-%d %H:%M:%S'

# 自動重載服務
cat > config-watcher.sh << 'EOF'
#!/bin/bash
inotifywait -m .env.production -e modify |
while read file event time; do
    echo "$time: $file modified, reloading configuration..."
    docker-compose exec discord-bot python -m src.core.config --reload
done
EOF
```

## 配置故障排除

### 常見配置問題

1. **環境變數未生效**

   ```bash
   # 檢查環境變數載入
   docker-compose exec discord-bot env | grep -E "TOKEN|GUILD_ID|ENVIRONMENT"
   
   # 重新載入環境文件
   docker-compose --env-file .env.production up -d
   ```

2. **配置文件語法錯誤**

   ```bash
   # YAML 語法檢查
   python -c "import yaml; yaml.safe_load(open('config.yaml'))"
   
   # 環境文件檢查
   set -a; source .env.production; set +a
   ```

3. **權限問題**

   ```bash
   # 檢查文件權限
   ls -la .env*
   
   # 修復權限
   chmod 600 .env*
   chown discord-bot:discord-bot .env*
   ```

### 配置除錯工具

```bash
# 匯出當前有效配置（敏感資料已遮蔽）
docker-compose exec discord-bot python -m src.core.config --export-safe

# 比較配置差異
docker-compose exec discord-bot python -m src.core.config --diff .env.staging .env.production

# 配置健康檢查
curl http://localhost:8080/config/health
```

## 配置遷移

### 版本升級配置遷移

```bash
# 配置遷移腳本
python scripts/migrate-config.py --from 1.7 --to 2.0

# 備份舊配置
cp .env .env.v1.7.backup

# 應用新配置格式
python scripts/upgrade-config.py
```

### 配置驗證檢查清單

- [ ] 所有必要環境變數已設定
- [ ] 敏感資料未硬編碼在配置文件中
- [ ] 配置文件權限正確設定 (600)
- [ ] 環境特定配置已分離
- [ ] 配置變更已記錄在變更日誌中
- [ ] 配置備份已建立
- [ ] 配置驗證測試通過

## 參考資源

- [環境變數參考](environment-variables.md) - 完整環境變數列表
- [安全配置指南](../architecture/security.md) - 安全相關配置
- [效能調優指南](performance-tuning.md) - 效能相關配置
- [故障排除手冊](troubleshooting.md) - 配置相關問題解決

---

**版本**: 2.0.0  
**最後更新**: 2025-08-01  
**作者**: 開發團隊
