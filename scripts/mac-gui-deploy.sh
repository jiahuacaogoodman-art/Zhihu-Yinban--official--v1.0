#!/usr/bin/env bash
# 智护银伴 · macOS 图形化部署向导
#
# 依赖：
#   - macOS 自带 osascript / Terminal / open
#   - Docker Desktop（Docker 部署模式）
#
# 本脚本不直接做成 .app，保持源码仓库可读可改；根目录的
# “配置向导.command” 会调用这里。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

APP_NAME="智护银伴"
ADMIN_URL="http://localhost:8000/"
NURSE_URL="http://localhost:8000/nurse"
HEALTH_URL="http://localhost:8000/health"

cd "$PROJECT_DIR"

if [ "${YINBAN_USE_APPLESCRIPT_WIZARD:-0}" != "1" ] && [ -f "$SCRIPT_DIR/mac_gui_deploy.py" ]; then
    exec python3 "$SCRIPT_DIR/mac_gui_deploy.py" "$@"
fi

die_dialog() {
    local message="$1"
    osascript - "$APP_NAME" "$message" <<'APPLESCRIPT' >/dev/null
on run argv
    display dialog (item 2 of argv) buttons {"知道了"} default button "知道了" with icon stop with title (item 1 of argv)
end run
APPLESCRIPT
    exit 1
}

info_dialog() {
    local message="$1"
    osascript - "$APP_NAME" "$message" <<'APPLESCRIPT' >/dev/null
on run argv
    display dialog (item 2 of argv) buttons {"继续"} default button "继续" with icon note with title (item 1 of argv)
end run
APPLESCRIPT
}

ask_text() {
    local title="$1"
    local message="$2"
    local default_value="${3:-}"
    osascript - "$title" "$message" "$default_value" <<'APPLESCRIPT'
on run argv
    set dialogResult to display dialog (item 2 of argv) default answer (item 3 of argv) buttons {"取消", "继续"} default button "继续" cancel button "取消" with title (item 1 of argv)
    return text returned of dialogResult
end run
APPLESCRIPT
}

ask_secret() {
    local title="$1"
    local message="$2"
    osascript - "$title" "$message" <<'APPLESCRIPT'
on run argv
    set dialogResult to display dialog (item 2 of argv) default answer "" buttons {"取消", "继续"} default button "继续" cancel button "取消" with hidden answer with title (item 1 of argv)
    return text returned of dialogResult
end run
APPLESCRIPT
}

choose_existing_env_action() {
    osascript - "$APP_NAME" <<'APPLESCRIPT'
on run argv
    set choices to {"保留现有 .env，直接启动", "备份现有 .env，重新配置", "取消"}
    set picked to choose from list choices with title (item 1 of argv) with prompt "检测到项目根目录已经存在 .env。请选择接下来怎么做：" default items {"保留现有 .env，直接启动"} OK button name "继续" cancel button name "取消"
    if picked is false then error number -128
    return item 1 of picked
end run
APPLESCRIPT
}

choose_provider() {
    osascript - "$APP_NAME" <<'APPLESCRIPT'
on run argv
    set choices to {"本地 Ollama（Docker 自动下载模型，推荐）", "远程 OpenAI 兼容 API（DeepSeek/vLLM/智谱等）"}
    set picked to choose from list choices with title (item 1 of argv) with prompt "选择 LLM 推理后端：" default items {"本地 Ollama（Docker 自动下载模型，推荐）"} OK button name "继续" cancel button name "取消"
    if picked is false then error number -128
    return item 1 of picked
end run
APPLESCRIPT
}

choose_model() {
    osascript - "$APP_NAME" <<'APPLESCRIPT'
on run argv
    set choices to {"Q3_K_M · 约 3.9 GB · 极省内存", "Q4_K_M · 约 4.8 GB · 默认推荐", "Q5_K_M · 约 5.5 GB · 质量更好", "Q8_0 · 约 8.2 GB · 接近无损", "自定义模型名"}
    set picked to choose from list choices with title (item 1 of argv) with prompt "选择 HuatuoGPT-o1-7B 量化档位：" default items {"Q4_K_M · 约 4.8 GB · 默认推荐"} OK button name "继续" cancel button name "取消"
    if picked is false then error number -128
    return item 1 of picked
end run
APPLESCRIPT
}

generate_token() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
    else
        uuidgen | tr -d '-' | tr '[:upper:]' '[:lower:]'
    fi
}

generate_fernet_key() {
    python3 - <<'PY'
import os, base64
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
}

compose_command() {
    if docker compose version >/dev/null 2>&1; then
        printf 'docker compose'
    elif command -v docker-compose >/dev/null 2>&1; then
        printf 'docker-compose'
    else
        return 1
    fi
}

shell_quote() {
    printf '%q' "$1"
}

launch_terminal() {
    local command_text="$1"
    osascript - "$command_text" <<'APPLESCRIPT'
on run argv
    tell application "Terminal"
        activate
        do script (item 1 of argv)
    end tell
end run
APPLESCRIPT
}

open_install_help() {
    osascript - "$APP_NAME" <<'APPLESCRIPT' >/dev/null
on run argv
    set answer to display dialog "未检测到 Docker。macOS 图形部署推荐使用 Docker Desktop。\n\n点击“打开下载页”会打开 Docker Desktop 安装页面。" buttons {"取消", "打开下载页"} default button "打开下载页" cancel button "取消" with icon caution with title (item 1 of argv)
    if button returned of answer is "打开下载页" then
        open location "https://docs.docker.com/desktop/install/mac-install/"
    end if
end run
APPLESCRIPT
}

ensure_macos_and_docker() {
    if [ "$(uname -s)" != "Darwin" ]; then
        die_dialog "这个图形化部署向导只面向 macOS。Linux 请运行 scripts/setup.sh，Windows 请双击 启动智护银伴.bat。"
    fi
    if ! command -v osascript >/dev/null 2>&1; then
        printf '未找到 osascript，无法显示 macOS 图形向导。\n' >&2
        exit 1
    fi
    if ! command -v docker >/dev/null 2>&1; then
        open_install_help
        exit 1
    fi
    if ! docker info >/dev/null 2>&1; then
        osascript - "$APP_NAME" <<'APPLESCRIPT' >/dev/null
on run argv
    display dialog "Docker Desktop 尚未运行。\n\n请先打开 Docker Desktop，等顶部菜单栏出现 Docker 图标后，再重新运行本向导。" buttons {"知道了"} default button "知道了" with icon caution with title (item 1 of argv)
end run
APPLESCRIPT
        open -a Docker >/dev/null 2>&1 || true
        exit 1
    fi
    if ! compose_command >/dev/null 2>&1; then
        die_dialog "未检测到 Docker Compose。请更新 Docker Desktop，或安装 docker-compose 后重试。"
    fi
}

backup_env_if_needed() {
    if [ -f "$ENV_FILE" ]; then
        local backup="$PROJECT_DIR/.env.backup.$(date +%Y%m%d-%H%M%S)"
        cp "$ENV_FILE" "$backup"
    fi
}

write_env() {
    local provider="$1"
    local auth_token="$2"
    local pii_key="$3"
    local port="$4"
    local ollama_model="$5"
    local openai_base="$6"
    local openai_model="$7"
    local openai_key="$8"

    cat > "$ENV_FILE" <<EOF
# ============================================================
# 智护银伴 · macOS 图形化部署配置
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')
# ============================================================

AUTH_TOKEN=${auth_token}
PII_ENCRYPTION_KEY=${pii_key}

HOST=0.0.0.0
PORT=${port}
WORKERS=1
MAX_UPLOAD_SIZE_MB=15
RELOAD=0

LLM_PROVIDER=${provider}

OLLAMA_MODEL_NAME=${ollama_model}
OLLAMA_API_URL=http://ollama:11434/api/generate

OPENAI_API_BASE=${openai_base}
OPENAI_MODEL=${openai_model}
OPENAI_API_KEY=${openai_key}

EMBEDDING_ALLOW_DEGRADED=true
EMBEDDING_DISABLED=false
ANONYMIZED_TELEMETRY=False

BACKUP_ENABLED=false
SYNC_ENABLED=false
EOF
}

run_deploy_in_terminal() {
    local provider="$1"
    local port="$2"
    local compose_cmd
    compose_cmd="$(compose_command)"
    local project_q
    project_q="$(shell_quote "$PROJECT_DIR")"
    local profile=""
    if [ "$provider" = "ollama" ]; then
        profile="--profile ollama"
    fi

    ADMIN_URL="http://localhost:${port}/"
    NURSE_URL="http://localhost:${port}/nurse"
    HEALTH_URL="http://localhost:${port}/health"

    local inner_cmd
    inner_cmd="cd ${project_q}; printf '\\n==> 智护银伴 macOS 图形部署\\n'; ${compose_cmd} ${profile} up -d --build; status=\$?; if [ \$status -ne 0 ]; then printf '\\n部署失败，退出码：%s\\n' \"\$status\"; read -r -n 1 -p '按任意键关闭...'; exit \$status; fi; printf '\\n==> 等待健康检查 ${HEALTH_URL}\\n'; for i in {1..40}; do if curl -fsS '${HEALTH_URL}' >/dev/null 2>&1; then printf '\\n服务已就绪：${ADMIN_URL}\\n护工端：${NURSE_URL}\\n'; open '${ADMIN_URL}'; break; fi; sleep 3; printf '.'; done; printf '\\n\\n日志命令：${compose_cmd} logs -f app\\n停止命令：${compose_cmd} down\\n'; read -r -n 1 -p '按任意键关闭...'"
    launch_terminal "/bin/bash -lc $(shell_quote "$inner_cmd")"
}

main() {
    ensure_macos_and_docker

    info_dialog "欢迎使用 macOS 图形化部署向导。\n\n接下来会生成 .env 配置，然后在 Terminal 中执行 Docker Compose 部署。"

    local reuse_existing="no"
    if [ -f "$ENV_FILE" ]; then
        local action
        action="$(choose_existing_env_action)"
        case "$action" in
            "保留现有 .env，直接启动")
                reuse_existing="yes"
                ;;
            "备份现有 .env，重新配置")
                backup_env_if_needed
                ;;
            *)
                exit 0
                ;;
        esac
    fi

    local provider="ollama"
    local auth_token=""
    local pii_key=""
    local port="8000"
    local ollama_model="hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M"
    local openai_base=""
    local openai_model=""
    local openai_key=""

    if [ "$reuse_existing" = "no" ]; then
        auth_token="$(generate_token)"
        pii_key="$(generate_fernet_key)"
        port="$(ask_text "服务端口" "请输入后端监听端口。默认 8000。" "8000")"
        if ! [[ "$port" =~ ^[0-9]+$ ]]; then
            die_dialog "端口必须是数字。"
        fi

        local provider_choice
        provider_choice="$(choose_provider)"
        if [[ "$provider_choice" == 远程* ]]; then
            provider="openai"
            ollama_model=""
            openai_base="$(ask_text "远程 LLM 地址" "请输入 OpenAI 兼容 API Base，例如：https://api.deepseek.com/v1" "")"
            openai_model="$(ask_text "远程模型名" "请输入模型名，例如 deepseek-chat 或 Qwen/Qwen2.5-7B-Instruct" "")"
            openai_key="$(ask_secret "API Key" "请输入 API Key。自建无鉴权端点可留空后点继续。")"
            if [ -z "$openai_base" ] || [ -z "$openai_model" ]; then
                die_dialog "远程 LLM 模式必须填写 OPENAI_API_BASE 和 OPENAI_MODEL。"
            fi
        else
            provider="ollama"
            local model_choice
            model_choice="$(choose_model)"
            case "$model_choice" in
                Q3_K_M*) ollama_model="hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q3_K_M" ;;
                Q4_K_M*) ollama_model="hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M" ;;
                Q5_K_M*) ollama_model="hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q5_K_M" ;;
                Q8_0*)   ollama_model="hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q8_0" ;;
                *)       ollama_model="$(ask_text "自定义模型名" "请输入完整 Ollama 模型名。" "qwen2.5:7b")" ;;
            esac
        fi

        write_env "$provider" "$auth_token" "$pii_key" "$port" "$ollama_model" "$openai_base" "$openai_model" "$openai_key"

        info_dialog "配置已写入：\n${ENV_FILE}\n\n管理员 Token 已生成并写入 .env：\n${auth_token}\n\n请妥善保存，不要在截图或录屏中泄露。"
    else
        provider="$(grep '^LLM_PROVIDER=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '\r' || true)"
        [ -z "$provider" ] && provider="ollama"
        port="$(grep '^PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '\r' || true)"
        [ -z "$port" ] && port="8000"
    fi

    info_dialog "配置完成。\n\n接下来会打开 Terminal 执行部署命令，首次启动会下载镜像和模型，可能需要数分钟。"
    run_deploy_in_terminal "$provider" "$port"
}

main "$@"
