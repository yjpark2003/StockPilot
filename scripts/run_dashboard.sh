#!/bin/bash
# 종목 관리 대시보드 구동 스크립트
#
# 사용법:
#   ./scripts/run_dashboard.sh [start|stop|restart|status] [옵션]
#
# 옵션:
#   -p, --port PORT     사용할 포트 (기본: 8001)
#   -H, --host HOST     바인드 주소 (기본: 0.0.0.0)
#   -f, --foreground    포그라운드 실행 (브라우저 자동 실행 안 함, Ctrl+C로 종료)
#   -n, --no-browser    브라우저 자동 실행 비활성화
#   -h, --help          도움말 출력

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/dashboard.log"
PID_FILE="$LOG_DIR/dashboard.pid"

HOST="0.0.0.0"
PORT="8001"
FOREGROUND=0
OPEN_BROWSER=1

if [ -x "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/venv/bin/python"
elif [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

usage() {
    sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        start|stop|restart|status)
            ACTION="$1"
            shift
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -H|--host)
            HOST="$2"
            shift 2
            ;;
        -f|--foreground)
            FOREGROUND=1
            OPEN_BROWSER=0
            shift
            ;;
        -n|--no-browser)
            OPEN_BROWSER=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "알 수 없는 인자: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

ACTION="${ACTION:-start}"
DASHBOARD_URL="http://localhost:${PORT}/dashboard"

server_pid() {
    [ -f "$PID_FILE" ] || return 1
    local pid
    pid="$(cat "$PID_FILE")"
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    echo "$pid"
}

is_running() {
    server_pid > /dev/null 2>&1
}

port_in_use() {
    if command -v ss > /dev/null 2>&1; then
        ss -ltn "sport = :${PORT}" 2>/dev/null | grep -q ":${PORT}"
    else
        curl -s -o /dev/null --max-time 2 "http://localhost:${PORT}/" 2>/dev/null
    fi
}

# WSL2 mirrored 모드(networkingMode=mirrored)에서는 Linux 와 Windows 가 포트
# 공간을 공유한다. 이때 Windows 쪽에 TimeWait 이 남아 있으면 Linux 의 ss 에는
# 아무것도 보이지 않는데도 bind 가 EADDRINUSE 로 실패한다. 그 경우를 잡아내야
# "서버가 죽은 이유"를 사용자에게 설명할 수 있다.
windows_port_in_use() {
    command -v powershell.exe > /dev/null 2>&1 || return 1
    local n
    n="$(timeout 10 powershell.exe -NoProfile -Command \
        "(Get-NetTCPConnection -LocalPort ${PORT} -ErrorAction SilentlyContinue | Measure-Object).Count" \
        2> /dev/null | tr -d '\r[:space:]')"
    [ -n "$n" ] || return 1
    [ "$n" -gt 0 ] 2> /dev/null
}

print_port_conflict_hint() {
    # Linux 쪽에 아무것도 없는데도 bind 가 막혔다면 Windows 측(=mirrored 공유) 문제
    if ! ss -ltn "sport = :${PORT}" 2> /dev/null | grep -q ":${PORT}"; then
        if windows_port_in_use; then
            local n
            n="$(timeout 10 powershell.exe -NoProfile -Command \
                "(Get-NetTCPConnection -LocalPort ${PORT} -ErrorAction SilentlyContinue | Measure-Object).Count" \
                2> /dev/null | tr -d '\r[:space:]')"
            echo "오류: 포트 ${PORT} bind 실패 — Windows 측에서 이미 사용 중입니다." >&2
            echo "  (.wslconfig networkingMode=mirrored 이면 Linux/Windows 가 포트를 공유합니다)" >&2
            echo "  Windows 측 ${PORT} 연결 ${n}개 (대부분 TimeWait). 잠시 후 풀리거나," >&2
            echo "  다른 포트로 실행하세요:  ./scripts/run_dashboard.sh start --port 8001" >&2
            return 0
        fi
    fi
    return 1
}

open_browser() {
    local url="$1"
    if command -v wslview > /dev/null 2>&1; then
        wslview "$url" > /dev/null 2>&1 &
    elif command -v xdg-open > /dev/null 2>&1; then
        xdg-open "$url" > /dev/null 2>&1 &
    elif command -v explorer.exe > /dev/null 2>&1; then
        explorer.exe "$url" > /dev/null 2>&1 &
    else
        echo "브라우저 실행 도구를 찾을 수 없습니다. 아래 주소로 접속하세요:"
        echo "  $url"
    fi
}

wait_ready() {
    local pid="$1"
    local i
    for i in $(seq 1 30); do
        if curl -s -o /dev/null --max-time 2 "http://localhost:${PORT}/" 2>/dev/null; then
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            return 1
        fi
        sleep 0.5
    done
    return 1
}

print_endpoints() {
    echo "대시보드:  http://localhost:${PORT}/dashboard"
    echo "리포트:   http://localhost:${PORT}/"
    local wsl_ip
    wsl_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [ -n "$wsl_ip" ]; then
        echo "WSL2 IP:   http://${wsl_ip}:${PORT}/dashboard"
    fi
}

do_start() {
    if is_running; then
        echo "이미 실행 중입니다 (PID $(server_pid), 포트 ${PORT})"
        print_endpoints
        return 0
    fi

    if port_in_use; then
        echo "오류: 포트 ${PORT}가 이미 사용 중입니다." >&2
        echo "  --port 옵션으로 다른 포트를 지정하세요." >&2
        return 1
    fi

    # WSL2 mirrored 모드에서는 Windows 측 점유가 ss 에 보이지 않는다.
    # 여기서 먼저 잡아내야 서버를 띄워 놓고 죽는 일이 없다.
    if ! port_in_use && print_port_conflict_hint; then
        return 1
    fi

    mkdir -p "$LOG_DIR"
    echo "$(date): 대시보드 서버 시작 (host=${HOST}, port=${PORT})" >> "$LOG_FILE"

    if [ "$FOREGROUND" -eq 1 ]; then
        echo "대시보드 서버를 포그라운드로 실행합니다. 종료: Ctrl+C"
        cd "$PROJECT_DIR" || return 1
        exec "$PYTHON" main.py server --host "$HOST" --port "$PORT"
    fi

    cd "$PROJECT_DIR" || return 1
    nohup "$PYTHON" main.py server --host "$HOST" --port "$PORT" >> "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"

    if wait_ready "$pid"; then
        echo "대시보드 서버 시작 완료 (PID $pid, 포트 ${PORT})"
        print_endpoints
        [ "$OPEN_BROWSER" -eq 1 ] && open_browser "$DASHBOARD_URL"
        return 0
    fi

    echo "오류: 서버가 정상 응답하지 않습니다. 로그를 확인하세요: $LOG_FILE" >&2
    if grep -q "address already in use" "$LOG_FILE" 2> /dev/null; then
        # bind 실패 원인을 그대로 알려준다 (그래야 사용자가 다음 행동을 안다)
        if ! print_port_conflict_hint; then
            echo "  원인은 포트 ${PORT} 점유입니다. --port 로 다른 포트를 지정하세요." >&2
        fi
    fi
    do_stop > /dev/null 2>&1
    return 1
}

do_stop() {
    if ! is_running; then
        echo "실행 중인 서버가 없습니다."
        rm -f "$PID_FILE"
        return 0
    fi

    local pid
    pid="$(server_pid)"
    kill "$pid" 2>/dev/null
    local i
    for i in $(seq 1 10); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null
    fi

    rm -f "$PID_FILE"
    echo "$(date): 대시보드 서버 중지 (PID $pid)" >> "$LOG_FILE"
    echo "대시보드 서버를 중지했습니다 (PID $pid)."
}

do_status() {
    if is_running; then
        echo "대시보드 서버 실행 중 (PID $(server_pid), 포트 ${PORT})"
        print_endpoints
        return 0
    fi
    echo "대시보드 서버가 실행 중이 아닙니다."
    return 1
}

case "$ACTION" in
    start) do_start ;;
    stop) do_stop ;;
    restart) do_stop; do_start ;;
    status) do_status ;;
esac
