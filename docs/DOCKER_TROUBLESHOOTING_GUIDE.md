# Docker配置故障排除指南

## 常見問題快速解決

### 🔥 緊急問題（服務無法啟動）

#### 問題1：容器啟動失敗

**症狀：**
```bash
ERROR: for discord-bot  Container "discord-bot-simple" exited with code 1
```

**診斷步驟：**
```bash
# 1. 查看容器日誌
docker-compose logs discord-bot

# 2. 檢查容器狀態
docker-compose ps

# 3. 檢查系統資源
docker system df
```

**可能原因和解決方案：**

1. **環境變數未設置**
   ```bash
   # 檢查環境變數文件
   cat .env
   
   # 確保DISCORD_TOKEN已設置
   echo $DISCORD_TOKEN
   ```
   
2. **端口衝突**
   ```bash
   # 檢查端口占用
   lsof -i :8000
   lsof -i :6379
   
   # 釋放端口或修改配置
   docker-compose down
   ```

3. **磁碟空間不足**
   ```bash
   # 檢查磁碟空間
   df -h
   
   # 清理Docker資源
   docker system prune -f
   docker volume prune -f
   ```

#### 問題2：Redis連接失敗

**症狀：**
```
ConnectionError: Error connecting to Redis server
```

**解決方案：**
```bash
# 1. 檢查Redis容器狀態
docker-compose ps redis

# 2. 測試Redis連接
docker-compose exec redis redis-cli ping

# 3. 重啟Redis服務
docker-compose restart redis

# 4. 檢查網路連接
docker network ls
docker network inspect roas-bot_simple-network
```

#### 問題3：健康檢查失敗

**症狀：**
```
discord-bot-simple   roas-bot:test-simple   unhealthy
```

**診斷和解決：**
```bash
# 1. 查看健康檢查日誌
docker inspect discord-bot-simple | grep -A 10 "Health"

# 2. 手動執行健康檢查命令
docker-compose exec discord-bot curl -f http://localhost:8000/health

# 3. 檢查應用程式狀態
docker-compose exec discord-bot python -c "import sys; print('Container healthy -', sys.version_info[:2])"

# 4. 調整健康檢查配置
# 編輯docker-compose文件，延長start_period或增加retries
```

### 🔧 配置問題

#### 問題4：建置錯誤

**症狀：**
```
ERROR: failed to build: failed to solve...
```

**解決方案：**

1. **清理建置快取**
   ```bash
   # 清理所有建置快取
   docker builder prune -f
   
   # 重新建置（不使用快取）
   docker-compose build --no-cache discord-bot
   ```

2. **檢查Dockerfile語法**
   ```bash
   # 驗證Dockerfile
   docker build -f Dockerfile.dev . --no-cache
   ```

3. **依賴安裝失敗**
   ```bash
   # 檢查網路連接
   ping pypi.org
   
   # 使用國內鏡像
   # 在Dockerfile中添加：
   # RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
   ```

#### 問題5：權限問題

**症狀：**
```
Permission denied: '/app/data'
PermissionError: [Errno 13]
```

**解決方案：**
```bash
# 1. 檢查目錄權限
ls -la data/ logs/

# 2. 修復權限
sudo chown -R $(whoami):$(whoami) data/ logs/ backups/
chmod -R 755 data/ logs/ backups/

# 3. 確保容器內用戶ID匹配
# 在Dockerfile中檢查用戶設置：
# RUN useradd --create-home --shell /bin/bash --uid 1000 app
```

### 📊 性能問題

#### 問題6：啟動時間過長

**症狀：啟動時間超過5分鐘**

**優化方案：**

1. **檢查資源使用**
   ```bash
   # 監控建置過程
   docker stats
   
   # 檢查系統負載
   top
   htop
   ```

2. **優化策略**
   ```bash
   # 使用簡化環境
   docker-compose -f docker-compose.simple.yml up
   
   # 預先拉取鏡像
   docker-compose pull
   
   # 使用本地鏡像快取
   docker images
   ```

3. **調整健康檢查時間**
   ```yaml
   healthcheck:
     start_period: 30s  # 從60s減少到30s
     interval: 30s      # 從20s增加到30s
   ```

#### 問題7：記憶體不足

**症狀：**
```
OOMKilled
Container killed due to memory limit
```

**解決方案：**
```bash
# 1. 檢查記憶體使用
docker stats --no-stream

# 2. 調整記憶體限制
# 編輯docker-compose文件：
deploy:
  resources:
    limits:
      memory: 512M  # 增加記憶體限制
    reservations:
      memory: 256M

# 3. 優化應用程式記憶體使用
# 檢查應用程式中的記憶體洩漏
docker-compose exec discord-bot python -c "
import psutil
print(f'Memory usage: {psutil.virtual_memory()._asdict()}')
"
```

### 🌐 網路問題

#### 問題8：服務間無法通信

**症狀：**
```
Name or service not known
Connection refused
```

**診斷步驟：**
```bash
# 1. 檢查網路配置
docker network ls
docker network inspect roas-bot_simple-network

# 2. 測試服務間連接
docker-compose exec discord-bot ping redis
docker-compose exec discord-bot nslookup redis

# 3. 檢查端口映射
docker-compose ps
```

**解決方案：**
```bash
# 1. 重新創建網路
docker-compose down
docker network rm roas-bot_simple-network
docker-compose up -d

# 2. 檢查服務名稱配置
# 確保在環境變數中使用正確的服務名稱：
# REDIS_URL=redis://redis:6379/0  # 使用服務名稱'redis'
```

#### 問題9：外部訪問失敗

**症狀：無法從主機訪問容器服務**

**解決方案：**
```bash
# 1. 檢查端口映射
docker-compose ps

# 2. 檢查防火牆設置
# macOS
sudo pfctl -sr

# Linux
sudo iptables -L

# 3. 測試端口連接
telnet localhost 8000
curl http://localhost:8000/health

# 4. 檢查服務綁定地址
# 確保服務綁定到0.0.0.0而不是127.0.0.1
```

### 📝 日誌和調試

#### 問題10：日誌過多或無日誌

**症狀：日誌文件過大或沒有日誌輸出**

**日誌管理：**
```bash
# 1. 查看日誌大小
du -sh logs/
docker system df

# 2. 清理日誌
# 清理Docker日誌
sudo sh -c "truncate -s 0 /var/lib/docker/containers/*/*-json.log"

# 3. 配置日誌輪轉
# 在docker-compose文件中添加：
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"

# 4. 檢查日誌級別
# 調整LOG_LEVEL環境變數
LOG_LEVEL=INFO  # 從DEBUG改為INFO
```

**調試技巧：**
```bash
# 1. 進入容器調試
docker-compose exec discord-bot bash

# 2. 實時查看日誌
docker-compose logs -f --tail=100 discord-bot

# 3. 檢查應用程式狀態
docker-compose exec discord-bot python -c "
import os
print('Environment:', os.getenv('ENVIRONMENT'))
print('Debug mode:', os.getenv('DEBUG'))
print('Log level:', os.getenv('LOG_LEVEL'))
"
```

## 診斷工具和命令

### 系統診斷腳本

創建診斷腳本以快速檢查系統狀態：

```bash
#!/bin/bash
# 保存為 diagnose.sh

echo "=== Docker系統診斷 ==="
echo "Docker版本:"
docker --version

echo -e "\n磁碟使用:"
docker system df

echo -e "\n容器狀態:"
docker-compose ps

echo -e "\n網路配置:"
docker network ls

echo -e "\n記憶體使用:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

echo -e "\n健康檢查:"
docker inspect $(docker-compose ps -q) --format='{{.Name}}: {{.State.Health.Status}}'

echo -e "\n最近錯誤:"
docker-compose logs --tail=20 | grep -i error
```

### 性能基準測試

```bash
#!/bin/bash
# 保存為 benchmark.sh

echo "=== 性能基準測試 ==="
start_time=$(date +%s)

echo "1. 清理環境..."
docker-compose down -v &>/dev/null

echo "2. 啟動服務..."
docker-compose -f docker-compose.simple.yml up -d

echo "3. 等待服務就緒..."
sleep 30

echo "4. 測試健康檢查..."
if curl -f http://localhost:8000/health &>/dev/null; then
    echo "✅ 健康檢查通過"
else
    echo "❌ 健康檢查失敗"
fi

end_time=$(date +%s)
duration=$((end_time - start_time))

echo "總啟動時間: ${duration}秒"
docker stats --no-stream
```

## 預防措施

### 定期維護

```bash
# 每週執行的維護腳本
#!/bin/bash

# 1. 清理未使用的鏡像
docker image prune -f

# 2. 清理未使用的卷
docker volume prune -f

# 3. 清理網路
docker network prune -f

# 4. 檢查磁碟空間
df -h | grep -E "95%|96%|97%|98%|99%|100%"

# 5. 備份重要數據
docker run --rm -v roas-bot_redis_simple_data:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/redis-backup-$(date +%Y%m%d).tar.gz /data

# 6. 更新鏡像
docker-compose pull
```

### 監控設置

使用開發環境的監控功能：

```bash
# 啟動完整監控環境
docker-compose -f docker-compose.dev.yml up -d

# 訪問監控面板
echo "Grafana: http://localhost:3000 (admin/admin)"
echo "Prometheus: http://localhost:9090"
```

在Grafana中設置告警規則，監控：
- 容器資源使用率
- 應用程式響應時間
- 錯誤率
- 磁碟空間使用

### 備份和恢復

```bash
# 備份配置和數據
tar czf backup-$(date +%Y%m%d).tar.gz \
  docker-compose*.yml \
  Dockerfile* \
  .env \
  data/ \
  logs/

# 恢復
tar xzf backup-YYYYMMDD.tar.gz
```

## 尋求幫助

### 收集診斷資訊

在尋求幫助時，請提供以下資訊：

```bash
# 生成診斷報告
echo "=== 系統資訊 ===" > diagnostic-report.txt
uname -a >> diagnostic-report.txt
docker --version >> diagnostic-report.txt
docker-compose --version >> diagnostic-report.txt

echo -e "\n=== Docker狀態 ===" >> diagnostic-report.txt
docker system df >> diagnostic-report.txt
docker-compose ps >> diagnostic-report.txt

echo -e "\n=== 錯誤日誌 ===" >> diagnostic-report.txt
docker-compose logs --tail=50 >> diagnostic-report.txt

echo -e "\n=== 配置文件 ===" >> diagnostic-report.txt
cat docker-compose*.yml >> diagnostic-report.txt
```

### 常用支援資源

- **官方文檔**: Docker官方文檔和最佳實踐
- **GitHub Issues**: 查看已知問題和解決方案
- **Stack Overflow**: 搜索相關問題和解決方案
- **Discord/Slack**: 社區支援群組

### 報告Bug

報告問題時請包含：
1. 完整的錯誤訊息
2. 使用的配置文件（隱藏敏感資訊）
3. 系統環境資訊
4. 重現步驟
5. 診斷報告

---

*本故障排除指南針對ROAS Bot v2.4.3 Docker配置編寫。如問題持續存在，請聯繫開發團隊。*