#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""macOS browser-based one-window deployment wizard.

Why browser, not Tkinter:
macOS ships many Python/Tcl/Tk combinations. Some render Tk windows as a blank
white panel. A tiny localhost form is more reliable and still needs no external
dependency. It listens only on 127.0.0.1 and exits after save/deploy.
"""

from __future__ import annotations

import base64
import html
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
DEFAULT_MODEL = "hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M"

MODEL_CHOICES = [
    ("Q3_K_M · 约 3.9 GB · 极省内存", "hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q3_K_M"),
    ("Q4_K_M · 约 4.8 GB · 默认推荐", "hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M"),
    ("Q5_K_M · 约 5.5 GB · 质量更好", "hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q5_K_M"),
    ("Q8_0 · 约 8.2 GB · 接近无损", "hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q8_0"),
    ("自定义模型名", "__custom__"),
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def generate_token() -> str:
    return secrets.token_hex(32)


def generate_fernet_key() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def compose_command() -> str | None:
    docker = shutil.which("docker")
    if docker:
        result = subprocess.run(
            [docker, "compose", "version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return "docker compose"
    if shutil.which("docker-compose"):
        return "docker-compose"
    return None


def apple_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def launch_terminal(command: str) -> None:
    script = (
        'tell application "Terminal"\n'
        "  activate\n"
        f"  do script {apple_quote(command)}\n"
        "end tell\n"
    )
    subprocess.run(["osascript", "-e", script], check=True)


def write_env(
    *,
    provider: str,
    auth_token: str,
    pii_key: str,
    port: str,
    ollama_model: str,
    openai_base: str,
    openai_model: str,
    openai_key: str,
) -> None:
    if ENV_FILE.exists():
        backup = PROJECT_DIR / f".env.backup.{datetime.now():%Y%m%d-%H%M%S}"
        shutil.copy2(ENV_FILE, backup)

    ENV_FILE.write_text(
        f"""# ============================================================
# 智护银伴 · macOS 图形化部署配置
# 生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}
# ============================================================

AUTH_TOKEN={auth_token}
PII_ENCRYPTION_KEY={pii_key}

HOST=0.0.0.0
PORT={port}
WORKERS=1
MAX_UPLOAD_SIZE_MB=15
RELOAD=0

LLM_PROVIDER={provider}

OLLAMA_MODEL_NAME={ollama_model}
OLLAMA_API_URL=http://ollama:11434/api/generate

OPENAI_API_BASE={openai_base}
OPENAI_MODEL={openai_model}
OPENAI_API_KEY={openai_key}

EMBEDDING_ALLOW_DEGRADED=true
EMBEDDING_DISABLED=false
ANONYMIZED_TELEMETRY=False

BACKUP_ENABLED=false
SYNC_ENABLED=false
""",
        encoding="utf-8",
    )


def ensure_docker() -> tuple[bool, str]:
    if shutil.which("docker") is None:
        webbrowser.open("https://docs.docker.com/desktop/install/mac-install/")
        return False, "未检测到 Docker。已打开 Docker Desktop 下载页。"
    result = subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        subprocess.run(["open", "-a", "Docker"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return False, "Docker Desktop 尚未运行。已尝试打开 Docker，请等菜单栏出现 Docker 图标后重新提交。"
    if compose_command() is None:
        return False, "未检测到 Docker Compose。请更新 Docker Desktop 后重试。"
    return True, ""


def launch_deploy(provider: str, port: str) -> None:
    compose = compose_command()
    if compose is None:
        raise RuntimeError("未检测到 Docker Compose")

    profile = "--profile ollama" if provider == "ollama" else ""
    admin_url = f"http://localhost:{port}/"
    nurse_url = f"http://localhost:{port}/nurse"
    health_url = f"http://localhost:{port}/health"

    inner = (
        f"cd {shlex.quote(str(PROJECT_DIR))}; "
        "printf '\\n==> 智护银伴 macOS 图形部署\\n'; "
        f"{compose} {profile} up -d --build; "
        "status=$?; "
        "if [ $status -ne 0 ]; then "
        "printf '\\n部署失败，退出码：%s\\n' \"$status\"; "
        "read -r -n 1 -p '按任意键关闭...'; "
        "exit $status; "
        "fi; "
        f"printf '\\n==> 等待健康检查 {health_url}\\n'; "
        "for i in {1..40}; do "
        f"if curl -fsS {shlex.quote(health_url)} >/dev/null 2>&1; then "
        f"printf '\\n服务已就绪：{admin_url}\\n护工端：{nurse_url}\\n'; "
        f"open {shlex.quote(admin_url)}; "
        "break; "
        "fi; "
        "sleep 3; "
        "printf '.'; "
        "done; "
        f"printf '\\n\\n日志命令：{compose} logs -f app\\n停止命令：{compose} down\\n'; "
        "read -r -n 1 -p '按任意键关闭...'"
    )
    launch_terminal("/bin/bash -lc " + shlex.quote(inner))


class WizardHandler(BaseHTTPRequestHandler):
    server_version = "YinbanMacWizard/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/token"):
            self._send_text(generate_token())
            return
        if self.path.startswith("/fernet-key"):
            self._send_text(generate_fernet_key())
            return
        self._send_html(self._form_page())

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = {k: v[-1] for k, v in parse_qs(body, keep_blank_values=True).items()}

        try:
            deploy = form.get("submit") == "deploy"
            action = form.get("env_action", "rewrite")
            existing = read_env(ENV_FILE)

            if action == "keep" and ENV_FILE.exists():
                provider = existing.get("LLM_PROVIDER", "ollama") or "ollama"
                port = existing.get("PORT", "8000") or "8000"
            else:
                provider = form.get("provider", "ollama")
                port = (form.get("port") or "8000").strip()
                if not port.isdigit():
                    raise ValueError("端口必须是数字。")

                auth_token = (form.get("auth_token") or "").strip()
                pii_key = (form.get("pii_key") or "").strip()
                if not auth_token or not pii_key:
                    raise ValueError("管理员 Token 和 PII 加密密钥不能为空。")

                ollama_model = ""
                openai_base = ""
                openai_model = ""
                openai_key = ""
                if provider == "openai":
                    openai_base = (form.get("openai_base") or "").strip()
                    openai_model = (form.get("openai_model") or "").strip()
                    openai_key = (form.get("openai_key") or "").strip()
                    if not openai_base or not openai_model:
                        raise ValueError("远程 API 模式必须填写 API Base 和模型名。")
                else:
                    model_value = form.get("model_choice") or DEFAULT_MODEL
                    if model_value == "__custom__":
                        model_value = (form.get("custom_model") or "").strip()
                    if not model_value:
                        raise ValueError("本地 Ollama 模式必须填写模型名。")
                    ollama_model = model_value

                write_env(
                    provider=provider,
                    auth_token=auth_token,
                    pii_key=pii_key,
                    port=port,
                    ollama_model=ollama_model,
                    openai_base=openai_base,
                    openai_model=openai_model,
                    openai_key=openai_key,
                )

            if deploy:
                ok, message = ensure_docker()
                if not ok:
                    self._send_html(self._message_page("需要处理 Docker", message, error=True))
                    return
                launch_deploy(provider, port)
                self._send_html(
                    self._message_page(
                        "已开始部署",
                        "已打开 Terminal 执行部署命令。首次下载镜像或模型可能需要几分钟。",
                    )
                )
            else:
                self._send_html(self._message_page("已保存配置", f"配置已写入：{ENV_FILE}"))
        except Exception as exc:  # pragma: no cover - shown in browser
            self._send_html(self._message_page("配置失败", str(exc), error=True))
            return

        threading.Thread(target=self._shutdown_later, daemon=True).start()

    def _shutdown_later(self) -> None:
        time.sleep(1)
        self.server.shutdown()

    def _send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, html_text: str) -> None:
        payload = html_text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _form_page(self) -> str:
        env = read_env(ENV_FILE)
        has_env = ENV_FILE.exists()
        provider = env.get("LLM_PROVIDER", "ollama") or "ollama"
        auth_token = env.get("AUTH_TOKEN") or generate_token()
        pii_key = env.get("PII_ENCRYPTION_KEY") or generate_fernet_key()
        port = env.get("PORT", "8000") or "8000"
        current_model = env.get("OLLAMA_MODEL_NAME") or DEFAULT_MODEL

        option_html = []
        custom_selected = True
        for label, value in MODEL_CHOICES:
            selected = ""
            if value == current_model:
                selected = "selected"
                custom_selected = False
            if value == "__custom__" and custom_selected:
                selected = "selected"
            option_html.append(f'<option value="{esc(value)}" {selected}>{esc(label)}</option>')

        env_section = ""
        if has_env:
            env_section = """
            <section>
              <h2>现有配置</h2>
              <label class="radio"><input type="radio" name="env_action" value="keep" checked> 保留现有 .env，直接启动服务</label>
              <label class="radio"><input type="radio" name="env_action" value="rewrite"> 备份现有 .env，并使用下面表单重新生成配置</label>
            </section>
            """
        else:
            env_section = '<input type="hidden" name="env_action" value="rewrite">'

        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>智护银伴 macOS 图形部署</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --line: #dbe3ee;
      --ink: #0f172a;
      --muted: #64748b;
      --brand: #0f766e;
      --brand-2: #0891b2;
      --danger: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.55 -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    }}
    main {{ width: min(980px, calc(100vw - 32px)); margin: 28px auto 40px; }}
    header {{ margin-bottom: 18px; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    .lead {{ margin: 8px 0 0; color: var(--muted); }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 18px;
      margin: 14px 0;
      box-shadow: 0 8px 24px rgba(15, 23, 42, .05);
    }}
    h2 {{ margin: 0 0 14px; font-size: 17px; }}
    .grid {{ display: grid; grid-template-columns: 160px minmax(0, 1fr) auto; gap: 10px; align-items: center; }}
    .grid + .grid {{ margin-top: 10px; }}
    label.label {{ color: var(--muted); }}
    input, select {{
      width: 100%;
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 10px;
      font: inherit;
      background: #fff;
      color: var(--ink);
    }}
    button {{
      min-height: 38px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0 14px;
      font: inherit;
      background: #fff;
      cursor: pointer;
    }}
    button.primary {{ background: var(--brand); color: #fff; border-color: var(--brand); }}
    button.secondary {{ background: #ecfeff; color: #155e75; border-color: #a5f3fc; }}
    .actions {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }}
    .radio {{ display: block; margin: 8px 0; }}
    .radio input {{ width: auto; min-height: auto; margin-right: 8px; }}
    .provider {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .choice {{
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 12px;
      background: #fff;
    }}
    .choice input {{ width: auto; min-height: auto; margin-right: 8px; }}
    .hint {{ color: var(--muted); font-size: 13px; margin-top: 8px; }}
    .hidden {{ display: none; }}
    .danger {{ color: var(--danger); }}
    @media (max-width: 720px) {{
      .grid {{ grid-template-columns: 1fr; }}
      .provider {{ grid-template-columns: 1fr; }}
      .actions {{ flex-direction: column; }}
      button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <h1>智护银伴 macOS 图形部署</h1>
    <p class="lead">在一个页面里完成配置，保存后自动打开 Terminal 执行 Docker Compose 部署。</p>
  </header>
  <form method="post" action="/deploy">
    {env_section}
    <section data-config>
      <h2>安全密钥</h2>
      <div class="grid">
        <label class="label" for="auth_token">管理员 Token</label>
        <input id="auth_token" name="auth_token" value="{esc(auth_token)}" autocomplete="off">
        <button type="button" data-generate="/token" data-target="auth_token">重新生成</button>
      </div>
      <div class="grid">
        <label class="label" for="pii_key">PII 加密密钥</label>
        <input id="pii_key" name="pii_key" value="{esc(pii_key)}" autocomplete="off">
        <button type="button" data-generate="/fernet-key" data-target="pii_key">重新生成</button>
      </div>
      <p class="hint danger">请妥善保存 Token，不要在截图或录屏中泄露。</p>
    </section>
    <section data-config>
      <h2>LLM 推理后端</h2>
      <div class="provider">
        <label class="choice"><input type="radio" name="provider" value="ollama" {"checked" if provider != "openai" else ""}> 本地 Ollama<br><span class="hint">Docker 自动下载 HuatuoGPT-o1-7B。</span></label>
        <label class="choice"><input type="radio" name="provider" value="openai" {"checked" if provider == "openai" else ""}> 远程 OpenAI 兼容 API<br><span class="hint">DeepSeek / vLLM / 智谱等。</span></label>
      </div>
      <div id="ollama_fields">
        <div class="grid" style="margin-top:14px">
          <label class="label" for="model_choice">本地模型</label>
          <select id="model_choice" name="model_choice">{''.join(option_html)}</select>
          <span></span>
        </div>
        <div class="grid" id="custom_model_row">
          <label class="label" for="custom_model">自定义模型名</label>
          <input id="custom_model" name="custom_model" value="{esc(current_model)}">
          <span></span>
        </div>
      </div>
      <div id="openai_fields">
        <div class="grid" style="margin-top:14px">
          <label class="label" for="openai_base">API Base</label>
          <input id="openai_base" name="openai_base" value="{esc(env.get('OPENAI_API_BASE', ''))}" placeholder="https://api.deepseek.com/v1">
          <span></span>
        </div>
        <div class="grid">
          <label class="label" for="openai_model">模型名</label>
          <input id="openai_model" name="openai_model" value="{esc(env.get('OPENAI_MODEL', ''))}" placeholder="deepseek-chat">
          <span></span>
        </div>
        <div class="grid">
          <label class="label" for="openai_key">API Key</label>
          <input id="openai_key" name="openai_key" value="{esc(env.get('OPENAI_API_KEY', ''))}" type="password">
          <span></span>
        </div>
      </div>
    </section>
    <section data-config>
      <h2>服务参数</h2>
      <div class="grid">
        <label class="label" for="port">端口</label>
        <input id="port" name="port" value="{esc(port)}">
        <span></span>
      </div>
      <p class="hint">默认管理端：http://localhost:8000/；护工端：http://localhost:8000/nurse</p>
    </section>
    <div class="actions">
      <button type="submit" name="submit" value="save">保存配置</button>
      <button class="primary" type="submit" name="submit" value="deploy">保存并部署</button>
    </div>
  </form>
</main>
<script>
function sync() {{
  const keep = document.querySelector('input[name="env_action"][value="keep"]')?.checked;
  document.querySelectorAll('[data-config] input, [data-config] select, [data-config] button').forEach(el => {{
    el.disabled = !!keep;
  }});
  const provider = document.querySelector('input[name="provider"]:checked')?.value || 'ollama';
  const openai = provider === 'openai';
  document.getElementById('ollama_fields').classList.toggle('hidden', openai);
  document.getElementById('openai_fields').classList.toggle('hidden', !openai);
  const custom = document.getElementById('model_choice').value === '__custom__';
  document.getElementById('custom_model_row').classList.toggle('hidden', !custom);
}}
document.querySelectorAll('input, select').forEach(el => el.addEventListener('change', sync));
document.querySelectorAll('[data-generate]').forEach(btn => {{
  btn.addEventListener('click', async () => {{
    const text = await fetch(btn.dataset.generate).then(r => r.text());
    document.getElementById(btn.dataset.target).value = text.trim();
  }});
}});
sync();
</script>
</body>
</html>"""

    def _message_page(self, title: str, message: str, *, error: bool = False) -> str:
        tone = "#b91c1c" if error else "#0f766e"
        return f"""<!doctype html>
<html lang="zh-CN">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<body style="margin:0;background:#f6f8fb;font:15px/1.6 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;color:#0f172a">
  <main style="max-width:720px;margin:56px auto;background:#fff;border:1px solid #dbe3ee;border-radius:12px;padding:28px;box-shadow:0 12px 30px rgba(15,23,42,.08)">
    <h1 style="margin:0 0 12px;color:{tone}">{esc(title)}</h1>
    <p style="white-space:pre-wrap">{esc(message)}</p>
    <p style="color:#64748b">可以关闭此页面。</p>
  </main>
</body>
</html>"""


def main() -> None:
    if sys.platform != "darwin":
        print("macOS 图形部署向导只支持 macOS。", file=sys.stderr)
        sys.exit(1)

    server = ThreadingHTTPServer(("127.0.0.1", 0), WizardHandler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"智护银伴 macOS 图形部署向导：{url}")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
