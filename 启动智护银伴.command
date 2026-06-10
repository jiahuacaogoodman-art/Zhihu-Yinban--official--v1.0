#!/usr/bin/env bash
# 智护银伴 · macOS 双击启动器
#
# 用法：
#   1. 在 Finder 中双击本文件；
#   2. 或在终端执行：./启动智护银伴.command
#
# 说明：
#   - macOS 不运行 .bat；本文件是对应的 .command 入口。
#   - 默认可打开 macOS 图形化部署向导。
#   - 也可在菜单里选择 Docker、API-only 或裸机后端运行。

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

cd "$PROJECT_DIR" || exit 1

export LANG="${LANG:-zh_CN.UTF-8}"
export LC_CTYPE="${LC_CTYPE:-UTF-8}"

ADMIN_URL="${YINBAN_ADMIN_URL:-http://localhost:8000/}"
NURSE_URL="${YINBAN_NURSE_URL:-http://localhost:8000/nurse}"
HEALTH_URL="${YINBAN_HEALTH_URL:-http://localhost:8000/health}"

print_line() {
    printf '%s\n' '============================================================'
}

pause_window() {
    if [ -t 0 ]; then
        printf '\n按任意键关闭窗口...'
        read -r -n 1 _
        printf '\n'
    fi
}

on_error() {
    code=$?
    if [ "$code" -ne 0 ]; then
        printf '\n启动未完成，退出码：%s\n' "$code"
        printf '请查看上方错误信息，或在终端运行同一命令重试。\n'
        pause_window
    fi
}
trap on_error EXIT

open_browser() {
    if command -v open >/dev/null 2>&1; then
        open "$ADMIN_URL" >/dev/null 2>&1 || true
    fi
}

open_browser_when_ready() {
    (
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
                open_browser
                exit 0
            fi
            sleep 2
        done
    ) &
}

run_checked() {
    "$@"
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        printf '\n命令执行失败：%s\n' "$*"
        exit "$rc"
    fi
}

activate_venv_if_present() {
    if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
        # shellcheck disable=SC1091
        . "$PROJECT_DIR/venv/bin/activate"
        printf '已激活虚拟环境：venv\n'
    elif [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
        # shellcheck disable=SC1091
        . "$PROJECT_DIR/.venv/bin/activate"
        printf '已激活虚拟环境：.venv\n'
    elif [ -f "$PROJECT_DIR/.venv312/bin/activate" ]; then
        # shellcheck disable=SC1091
        . "$PROJECT_DIR/.venv312/bin/activate"
        printf '已激活虚拟环境：.venv312\n'
    else
        printf '未发现 venv/.venv；将使用当前 PATH 中的 Python/uvicorn。\n'
    fi
}

choose_mode() {
    if [ -n "${YINBAN_LAUNCH_MODE:-}" ]; then
        case "$YINBAN_LAUNCH_MODE" in
            gui|wizard) MODE="gui" ;;
            docker|setup) MODE="docker" ;;
            api|api-only|api_only) MODE="api-only" ;;
            local|run) MODE="local" ;;
            browser|open) MODE="browser" ;;
            *) MODE="$YINBAN_LAUNCH_MODE" ;;
        esac
        return
    fi

    print_line
    printf '智护银伴 · macOS 启动器\n'
    print_line
    printf '项目目录：%s\n\n' "$PROJECT_DIR"
    printf '请选择启动方式：\n\n'
    printf '  [1] 图形部署向导（推荐新手，本地浏览器表单）\n'
    printf '  [2] Docker 一键部署/启动（Terminal 交互向导）\n'
    printf '  [3] API-only 本地运行（远程 LLM，需已配置 .env 和依赖）\n'
    printf '  [4] 裸机后端运行（本地 venv + Ollama，适合开发调试）\n'
    printf '  [5] 只打开浏览器（服务已在运行时使用）\n\n'
    printf '选择 [1-5]，默认 1：'
    read -r choice

    case "${choice:-1}" in
        1) MODE="gui" ;;
        2) MODE="docker" ;;
        3) MODE="api-only" ;;
        4) MODE="local" ;;
        5) MODE="browser" ;;
        *) MODE="gui" ;;
    esac
}

MODE=""
choose_mode

case "$MODE" in
    gui)
        print_line
        printf '启动方式：macOS 图形部署向导\n'
        print_line
        run_checked /bin/bash "$PROJECT_DIR/scripts/mac-gui-deploy.sh"
        ;;

    docker)
        print_line
        printf '启动方式：Docker 一键部署/启动\n'
        print_line
        run_checked /bin/bash "$PROJECT_DIR/scripts/setup.sh"
        if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
            printf '\n服务已就绪：%s\n' "$ADMIN_URL"
            printf '护工端：%s\n' "$NURSE_URL"
            open_browser
        else
            printf '\n部署脚本已结束，但暂未探测到健康检查：%s\n' "$HEALTH_URL"
            printf '如模型仍在下载，可稍后手动打开：%s\n' "$ADMIN_URL"
        fi
        pause_window
        ;;

    api-only)
        print_line
        printf '启动方式：API-only 本地运行\n'
        print_line
        if [ ! -f "$PROJECT_DIR/.env" ]; then
            printf '未找到 .env。请先复制 .env.example 并配置远程 LLM：\n'
            printf '  cp .env.example .env\n'
            printf '  设置 LLM_PROVIDER=openai、OPENAI_API_BASE、OPENAI_MODEL、OPENAI_API_KEY\n'
            exit 1
        fi
        activate_venv_if_present
        if ! command -v uvicorn >/dev/null 2>&1; then
            printf '未找到 uvicorn。请先安装轻量依赖：\n'
            printf '  python3 -m venv venv\n'
            printf '  source venv/bin/activate\n'
            printf '  pip install -r requirements-api.txt\n'
            exit 1
        fi
        open_browser_when_ready
        run_checked /bin/bash "$PROJECT_DIR/scripts/run-api-local.sh"
        pause_window
        ;;

    local)
        print_line
        printf '启动方式：裸机后端运行\n'
        print_line
        activate_venv_if_present
        if ! command -v uvicorn >/dev/null 2>&1; then
            printf '未找到 uvicorn。请先安装依赖：\n'
            printf '  python3 -m venv venv\n'
            printf '  source venv/bin/activate\n'
            printf '  pip install -r requirements.txt\n'
            exit 1
        fi
        open_browser_when_ready
        run_checked /bin/bash "$PROJECT_DIR/scripts/run.sh"
        pause_window
        ;;

    browser)
        print_line
        printf '打开浏览器\n'
        print_line
        printf '管理端：%s\n' "$ADMIN_URL"
        printf '护工端：%s\n' "$NURSE_URL"
        open_browser
        pause_window
        ;;

    *)
        printf '未知启动方式：%s\n' "$MODE"
        exit 1
        ;;
esac