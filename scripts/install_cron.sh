#!/bin/bash
# 주간 주식 분석 자동 실행 스크립트
# cron에 등록: 0 18 * * * /path/to/install_cron.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "$(date): 주간 주식 분석 시작" >> "$PROJECT_DIR/logs/cron.log"

cd "$PROJECT_DIR"
python3 scripts/run_analysis.py >> "$PROJECT_DIR/logs/cron.log" 2>&1

echo "$(date): 분석 완료" >> "$PROJECT_DIR/logs/cron.log"
