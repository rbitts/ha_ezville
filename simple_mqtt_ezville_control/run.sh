#!/bin/sh

# 리팩토링된 버전 사용 (기본)
PY_FILE="ezville_refactored.py"

# 기존 버전을 사용하려면 아래 주석을 해제하세요
# PY_FILE="ezville.py"

# start server
echo "[Info] Start simple_mqtt_ezville_control (Refactored Version)"

python -u /$PY_FILE
