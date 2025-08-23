#!/bin/bash

# 啟動 Discord ADR bot，使用虛擬環境
cd "$(dirname "$0")"

# 啟用 venv
source venv/bin/activate

# 啟動主程式
python main.py
