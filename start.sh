#!/bin/bash
# Prompt Portal 启动脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$SCRIPT_DIR/backend/start.log"
PID_FILE="$SCRIPT_DIR/backend/app.pid"

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Prompt Portal 后端已在运行 (PID: $(cat "$PID_FILE"))"
        return 0
    fi

    echo "启动 Prompt Portal 后端..."
    cd "$SCRIPT_DIR"
    python3 -m backend.main >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2

    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Prompt Portal 后端已启动 (PID: $(cat "$PID_FILE"))"
    else
        echo "启动失败，查看日志: $LOG_FILE"
        return 1
    fi
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "停止 Prompt Portal 后端 (PID: $PID)..."
            kill "$PID"
            rm -f "$PID_FILE"
        else
            echo "进程不存在，清理 PID 文件"
            rm -f "$PID_FILE"
        fi
    else
        echo "未找到 PID 文件"
    fi
}

restart() {
    # 强制杀掉端口占用的进程
    lsof -ti:8768 | xargs kill -9 2>/dev/null
    rm -f "$PID_FILE"
    sleep 1
    start
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Prompt Portal 后端运行中 (PID: $(cat "$PID_FILE"))"
    else
        echo "Prompt Portal 后端未运行"
    fi
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    status)  status ;;
    *)       echo "用法: $0 {start|stop|restart|status}" ;;
esac
