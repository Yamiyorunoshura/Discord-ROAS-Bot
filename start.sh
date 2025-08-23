#!/bin/bash
# 修復的Docker啟動腳本
# 正確處理環境變量傳遞

echo "🚀 啟動Discord機器人 (Docker模式)"

# 檢查.env檔案
if [ ! -f ".env" ]; then
    echo "❌ 找不到.env檔案"
    exit 1
fi

echo "✅ 載入環境變量..."

# 自動匯出環境變量
set -a && source .env && set +a

echo "📦 開始Docker build和啟動..."

# 使用docker-compose.dev.yml啟動服務
docker compose -f docker-compose.dev.yml --env-file .env up --build -d

echo "📊 檢查容器狀態..."
docker compose -f docker-compose.dev.yml ps

echo "📝 查看最近的日誌..."
docker compose -f docker-compose.dev.yml logs --tail=20

echo "🎉 Discord機器人啟動完成！"
echo "💡 查看即時日誌: docker compose -f docker-compose.dev.yml logs -f"
echo "🛑 停止服務: docker compose -f docker-compose.dev.yml down"