# Discord機器人部署配置 - Python 3.13 + uv
# Task ID: T6 - Docker跨平台一鍵啟動腳本開發

# 多階段構建，優化鏡像大小
FROM python:3.13-slim as builder

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴和uv
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    pkg-config \
    libffi-dev \
    curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && rm -rf /var/lib/apt/lists/* \
    && echo 'export PATH="/root/.cargo/bin:$PATH"' >> /root/.bashrc

# 將uv添加到PATH
ENV PATH="/root/.cargo/bin:$PATH"

# 複製專案配置文件
COPY pyproject.toml ./

# 建立虛擬環境並安裝依賴
RUN export PATH="/root/.cargo/bin:$PATH" \
    && /root/.cargo/bin/uv venv venv \
    && . venv/bin/activate \
    && /root/.cargo/bin/uv pip install -e .

# 生產階段
FROM python:3.13-slim

# 創建非root用戶
RUN useradd --create-home --shell /bin/bash app

# 設置工作目錄
WORKDIR /app

# 安裝運行時依賴
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 從builder階段複製虛擬環境
COPY --from=builder /app/venv /app/venv

# 創建必要的目錄
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R app:app /app

# 複製應用程序文件
COPY --chown=app:app . /app/

# 切換到非root用戶
USER app

# 更新PATH以包含虛擬環境
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
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