#!/usr/bin/env sh
set -eu

# 获取设备列表，支持从新变量 MOBILE_V4_DEVICES 或旧变量 MOBILE_V4_ADB_CONNECT_ADDR 获取
DEVICES_STR="${MOBILE_V4_DEVICES:-${MOBILE_V4_ADB_CONNECT_ADDR:-}}"
ADB_CONNECT_RETRIES="${MOBILE_V4_ADB_CONNECT_RETRIES:-30}"
ADB_CONNECT_SLEEP_SEC="${MOBILE_V4_ADB_CONNECT_SLEEP_SEC:-1}"

if [ -n "$DEVICES_STR" ]; then
  adb start-server >/dev/null 2>&1 || true

  # 将逗号分隔的设备列表切开并循环连接
  # 使用 tr 将逗号替换为空格进行遍历
  for ADDR in $(echo "$DEVICES_STR" | tr ',' ' '); do
    # 只有包含冒号的地址才需要 adb connect
    if echo "$ADDR" | grep -q ":"; then
      echo "Attempting to connect to $ADDR..."
      i=0
      while [ "$i" -lt "$ADB_CONNECT_RETRIES" ]; do
        if adb connect "$ADDR" >/dev/null 2>&1; then
          # 检查是否真正连接成功且处于 device 状态
          if adb devices | tr -d '\r' | grep -q "^$ADDR[[:space:]]device$"; then
            echo "Successfully connected to $ADDR"
            break
          fi
        fi
        i=$((i + 1))
        sleep "$ADB_CONNECT_SLEEP_SEC"
      done
    else
      echo "Skipping connect for local/physical device: $ADDR"
    fi
  done
fi

exec python -m uvicorn web.server:app --host 0.0.0.0 --port 8000
