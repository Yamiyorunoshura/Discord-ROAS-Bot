# Discord機器人部署配置
# Task ID: 11 - 建立文件和部署準備

# 多階段構建，優化鏡像大小
FROM python:3.10-slim as builder

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    pkg-config \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製需求文件
COPY requirements.txt .

# 安裝Python依賴到臨時目錄
RUN pip install --no-cache-dir --user -r requirements.txt

# 生產階段
FROM python:3.10-slim

# 創建非root用戶
RUN useradd --create-home --shell /bin/bash app

# 設置工作目錄
WORKDIR /app

# 安裝運行時依賴
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 從builder階段複製已安裝的依賴
COPY --from=builder /root/.local /home/app/.local

# 創建必要的目錄
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R app:app /app

# 複製應用程序文件
COPY --chown=app:app . /app/

# 切換到非root用戶
USER app

# 更新PATH以包含用戶安裝的包
ENV PATH=/home/app/.local/bin:$PATH

# 設置環境變數
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from core.database_manager import DatabaseManager; \
    async def check(): \
        try: \
            db = DatabaseManager(); \
            await db.initialize(); \
            await db.execute('SELECT 1'); \
            await db.close(); \
            print('healthy'); \
        except Exception as e: \
            print(f'unhealthy: {e}'); \
            exit(1); \
    asyncio.run(check())" || exit 1

# 暴露端口（如果有Web界面）
EXPOSE 8000

# 啟動命令
CMD ["python", "main.py"]