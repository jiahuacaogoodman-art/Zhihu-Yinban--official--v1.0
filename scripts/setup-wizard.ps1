#Requires -Version 5.1
<#
.SYNOPSIS
    智护银伴 · 图形化配置向导（弹窗手动填）
.DESCRIPTION
    把过去散落在 README 里的终端步骤——
        cp .env.example .env
        openssl rand -hex 32
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        手动改 OLLAMA_MODEL_NAME / LLM_PROVIDER ...
    全部封装成一个 Windows 弹窗。

    面向：试点医院、养老院信息员、不熟悉命令行的部署人员。

    依赖：仅依赖 .NET WinForms（Windows 10/11/Server 自带），不装任何额外组件。

    工作流程：
      1. 读取项目根目录已有的 .env（若有）作为初始值；否则用 .env.example 的占位。
      2. 用户在弹窗里勾选/填写。
      3. 一键生成 AUTH_TOKEN（32 字节 hex）和 PII_ENCRYPTION_KEY（Fernet 兼容的
         44 字符 URL-safe base64），不依赖 Python / openssl。
      4. 一键检测 Ollama 是否在 http://localhost:11434 响应，并尝试列出已安装模型。
      5. 保存时按"key 存在则替换、不存在则追加"写回 .env，未在向导里出现的
         自定义键不会被吃掉。

.PARAMETER NonInteractive
    供自动化测试使用：直接读默认值并写回，不弹窗。手动场景永远不要加这个。
#>

[CmdletBinding()]
param(
    [switch]$NonInteractive
)

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvPath    = Join-Path $ProjectDir '.env'
$EnvExample = Join-Path $ProjectDir '.env.example'

# ──────────────────────────────────────────────────────────────────
# 工具函数：读 / 写 / upsert .env
# 关键约束：保留注释和原顺序，未在 GUI 里管理的 key 原样保留。
# ──────────────────────────────────────────────────────────────────

function Read-EnvFile([string]$Path) {
    $map = [ordered]@{}
    if (-not (Test-Path $Path)) { return $map }
    Get-Content $Path -Encoding UTF8 | ForEach-Object {
        $line = $_
        $trim = $line.Trim()
        if (-not $trim -or $trim.StartsWith('#')) { return }
        $eq = $trim.IndexOf('=')
        if ($eq -lt 1) { return }
        $key = $trim.Substring(0, $eq).Trim()
        $val = $trim.Substring($eq + 1).Trim()
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or
            ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        $map[$key] = $val
    }
    return $map
}

function Save-EnvFile {
    param(
        [string]$Path,
        [hashtable]$Updates
    )

    # 优先在已有 .env 上做 in-place upsert
    $sourceText = if (Test-Path $Path) {
        Get-Content $Path -Raw -Encoding UTF8
    } elseif (Test-Path $EnvExample) {
        Get-Content $EnvExample -Raw -Encoding UTF8
    } else {
        ''
    }

    $appliedKeys = @{}
    $resultLines = New-Object System.Collections.Generic.List[string]

    if ($sourceText) {
        $sourceText -split "`r?`n" | ForEach-Object {
            $line = $_
            $trim = $line.Trim()
            if (-not $trim -or $trim.StartsWith('#')) {
                $resultLines.Add($line) | Out-Null
                return
            }
            $eq = $trim.IndexOf('=')
            if ($eq -lt 1) {
                $resultLines.Add($line) | Out-Null
                return
            }
            $key = $trim.Substring(0, $eq).Trim()
            if ($Updates.ContainsKey($key)) {
                $newVal = [string]$Updates[$key]
                $resultLines.Add("$key=$newVal") | Out-Null
                $appliedKeys[$key] = $true
            } else {
                $resultLines.Add($line) | Out-Null
            }
        }
    }

    # 还没出现过的新 key 追加到末尾
    foreach ($k in $Updates.Keys) {
        if (-not $appliedKeys.ContainsKey($k)) {
            $resultLines.Add("$k=$($Updates[$k])") | Out-Null
        }
    }

    $finalText = ($resultLines -join "`r`n").TrimEnd() + "`r`n"
    # UTF-8 NoBOM，避免 Linux 容器读取时第一行带 BOM 解析失败
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $finalText, $utf8NoBom)
}

# ──────────────────────────────────────────────────────────────────
# 密钥生成（不依赖 Python / openssl）
# AUTH_TOKEN：32 字节随机 hex（64 字符）
# PII_ENCRYPTION_KEY：Fernet 格式 = URL-safe base64(32 bytes) = 44 字符
# ──────────────────────────────────────────────────────────────────

function New-AuthToken {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ($bytes | ForEach-Object { '{0:x2}' -f $_ }) -join ''
}

function New-FernetKey {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $b64 = [Convert]::ToBase64String($bytes)
    # Fernet 用 URL-safe base64：'+'/'/' → '-'/'_'
    return $b64.Replace('+', '-').Replace('/', '_')
}

# ──────────────────────────────────────────────────────────────────
# Ollama 探测
# ──────────────────────────────────────────────────────────────────

function Test-OllamaReachable {
    param([string]$BaseUrl = 'http://localhost:11434')
    try {
        $resp = Invoke-WebRequest -Uri "$BaseUrl/" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Get-OllamaModels {
    param([string]$BaseUrl = 'http://localhost:11434')
    try {
        $resp = Invoke-RestMethod -Uri "$BaseUrl/api/tags" -TimeoutSec 3 -ErrorAction Stop
        if ($resp.models) {
            return @($resp.models | ForEach-Object { $_.name })
        }
    } catch {}
    return @()
}

# ──────────────────────────────────────────────────────────────────
# NonInteractive：仅做"如果 .env 不存在就拷一份并补上空密钥"，不弹窗
# 主要给 CI / 自动化场景用，正常人永远走 GUI 分支。
# ──────────────────────────────────────────────────────────────────
if ($NonInteractive) {
    if (-not (Test-Path $EnvPath) -and (Test-Path $EnvExample)) {
        Copy-Item $EnvExample $EnvPath
    }
    $existing = Read-EnvFile $EnvPath
    $updates = @{}
    if (-not $existing['AUTH_TOKEN'])         { $updates['AUTH_TOKEN'] = New-AuthToken }
    if (-not $existing['PII_ENCRYPTION_KEY']) { $updates['PII_ENCRYPTION_KEY'] = New-FernetKey }
    if ($updates.Count -gt 0) { Save-EnvFile -Path $EnvPath -Updates $updates }
    Write-Host "NonInteractive 模式：.env 已就绪 ($EnvPath)"
    exit 0
}

# ──────────────────────────────────────────────────────────────────
# WinForms GUI
# ──────────────────────────────────────────────────────────────────

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# 读已有值
$existing = Read-EnvFile $EnvPath

# 默认值（已有值优先，没有就用 .env.example 的隐含默认）
$defaults = @{
    AUTH_TOKEN               = $existing['AUTH_TOKEN']
    PII_ENCRYPTION_KEY       = $existing['PII_ENCRYPTION_KEY']
    LLM_PROVIDER             = if ($existing['LLM_PROVIDER']) { $existing['LLM_PROVIDER'] } else { 'ollama' }
    OLLAMA_MODEL_NAME        = if ($existing['OLLAMA_MODEL_NAME']) { $existing['OLLAMA_MODEL_NAME'] } else { 'hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M' }
    OLLAMA_API_URL           = if ($existing['OLLAMA_API_URL']) { $existing['OLLAMA_API_URL'] } else { 'http://localhost:11434/api/generate' }
    OPENAI_API_BASE          = $existing['OPENAI_API_BASE']
    OPENAI_MODEL             = $existing['OPENAI_MODEL']
    OPENAI_API_KEY           = $existing['OPENAI_API_KEY']
    HOST                     = if ($existing['HOST']) { $existing['HOST'] } else { '127.0.0.1' }
    PORT                     = if ($existing['PORT']) { $existing['PORT'] } else { '8000' }
    MAX_UPLOAD_SIZE_MB       = if ($existing['MAX_UPLOAD_SIZE_MB']) { $existing['MAX_UPLOAD_SIZE_MB'] } else { '15' }
    EMBEDDING_ALLOW_DEGRADED = if ($existing['EMBEDDING_ALLOW_DEGRADED']) { $existing['EMBEDDING_ALLOW_DEGRADED'] } else { 'true' }
}

$form = New-Object System.Windows.Forms.Form
$form.Text = '智护银伴 · 配置向导'
$form.Size = New-Object System.Drawing.Size(720, 640)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $true
$form.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 9)

$header = New-Object System.Windows.Forms.Label
$header.Text = '配置 .env 文件 — 填写后点底部 [保存并继续]'
$header.Location = New-Object System.Drawing.Point(15, 12)
$header.Size = New-Object System.Drawing.Size(680, 22)
$header.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 11, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($header)

$pathLabel = New-Object System.Windows.Forms.Label
$pathLabel.Text = "目标文件: $EnvPath"
$pathLabel.Location = New-Object System.Drawing.Point(15, 36)
$pathLabel.Size = New-Object System.Drawing.Size(680, 16)
$pathLabel.ForeColor = [System.Drawing.Color]::DimGray
$form.Controls.Add($pathLabel)

$tabs = New-Object System.Windows.Forms.TabControl
$tabs.Location = New-Object System.Drawing.Point(15, 60)
$tabs.Size = New-Object System.Drawing.Size(680, 480)
$form.Controls.Add($tabs)

# ─────────── Tab 1：安全密钥 ───────────
$tabSecurity = New-Object System.Windows.Forms.TabPage
$tabSecurity.Text = '  1. 安全密钥（必填）  '
$tabs.Controls.Add($tabSecurity)

$lblAuth = New-Object System.Windows.Forms.Label
$lblAuth.Text = '管理员 Token (AUTH_TOKEN)'
$lblAuth.Location = New-Object System.Drawing.Point(15, 18)
$lblAuth.Size = New-Object System.Drawing.Size(640, 18)
$lblAuth.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 9, [System.Drawing.FontStyle]::Bold)
$tabSecurity.Controls.Add($lblAuth)

$lblAuthHint = New-Object System.Windows.Forms.Label
$lblAuthHint.Text = '首次启动时自动创建的 admin 用户，本 Token 即其 API Key。建议直接点右侧 [生成]。'
$lblAuthHint.Location = New-Object System.Drawing.Point(15, 38)
$lblAuthHint.Size = New-Object System.Drawing.Size(640, 16)
$lblAuthHint.ForeColor = [System.Drawing.Color]::DimGray
$tabSecurity.Controls.Add($lblAuthHint)

$txtAuth = New-Object System.Windows.Forms.TextBox
$txtAuth.Location = New-Object System.Drawing.Point(15, 60)
$txtAuth.Size = New-Object System.Drawing.Size(520, 24)
$txtAuth.Text = $defaults.AUTH_TOKEN
$txtAuth.Font = New-Object System.Drawing.Font('Consolas', 9)
$tabSecurity.Controls.Add($txtAuth)

$btnGenAuth = New-Object System.Windows.Forms.Button
$btnGenAuth.Text = '生成'
$btnGenAuth.Location = New-Object System.Drawing.Point(545, 58)
$btnGenAuth.Size = New-Object System.Drawing.Size(110, 28)
$btnGenAuth.Add_Click({ $txtAuth.Text = New-AuthToken })
$tabSecurity.Controls.Add($btnGenAuth)

$lblPii = New-Object System.Windows.Forms.Label
$lblPii.Text = 'PII 加密密钥 (PII_ENCRYPTION_KEY)'
$lblPii.Location = New-Object System.Drawing.Point(15, 110)
$lblPii.Size = New-Object System.Drawing.Size(640, 18)
$lblPii.Font = New-Object System.Drawing.Font('Microsoft YaHei UI', 9, [System.Drawing.FontStyle]::Bold)
$tabSecurity.Controls.Add($lblPii)

$lblPiiHint = New-Object System.Windows.Forms.Label
$lblPiiHint.Text = '姓名 / 身份证 / 联系方式等 10 个高敏字段写入前会用此密钥加密 (Fernet)。'
$lblPiiHint.Location = New-Object System.Drawing.Point(15, 130)
$lblPiiHint.Size = New-Object System.Drawing.Size(640, 16)
$lblPiiHint.ForeColor = [System.Drawing.Color]::DimGray
$tabSecurity.Controls.Add($lblPiiHint)

$txtPii = New-Object System.Windows.Forms.TextBox
$txtPii.Location = New-Object System.Drawing.Point(15, 152)
$txtPii.Size = New-Object System.Drawing.Size(520, 24)
$txtPii.Text = $defaults.PII_ENCRYPTION_KEY
$txtPii.Font = New-Object System.Drawing.Font('Consolas', 9)
$tabSecurity.Controls.Add($txtPii)

$btnGenPii = New-Object System.Windows.Forms.Button
$btnGenPii.Text = '生成'
$btnGenPii.Location = New-Object System.Drawing.Point(545, 150)
$btnGenPii.Size = New-Object System.Drawing.Size(110, 28)
$btnGenPii.Add_Click({ $txtPii.Text = New-FernetKey })
$tabSecurity.Controls.Add($btnGenPii)

$warnPanel = New-Object System.Windows.Forms.Panel
$warnPanel.Location = New-Object System.Drawing.Point(15, 200)
$warnPanel.Size = New-Object System.Drawing.Size(640, 240)
$warnPanel.BackColor = [System.Drawing.Color]::FromArgb(255, 252, 232)
$warnPanel.BorderStyle = 'FixedSingle'
$tabSecurity.Controls.Add($warnPanel)

$lblWarn = New-Object System.Windows.Forms.Label
$lblWarn.Text = "⚠ 重要提示`r`n`r`n• 这两个值一旦确认就必须妥善保管，AUTH_TOKEN 丢了无法登录管理端，PII_ENCRYPTION_KEY 丢了已加密的档案无法解密读出。`r`n`r`n• 强烈建议两项都点 [生成] 让脚本随机生成；不要用 ' admin'、'123456' 这种弱口令。`r`n`r`n• 生成后请立刻把 AUTH_TOKEN 复制到安全位置（密码管理器 / 院方保险柜），第一次部署后这就是您的管理员 Token。`r`n`r`n• 想换 Token？保存退出后，再次运行向导重填即可；管理员 Token 重置后旧 Token 立即失效。"
$lblWarn.Location = New-Object System.Drawing.Point(12, 10)
$lblWarn.Size = New-Object System.Drawing.Size(615, 220)
$lblWarn.ForeColor = [System.Drawing.Color]::FromArgb(133, 77, 14)
$warnPanel.Controls.Add($lblWarn)

# ─────────── Tab 2：LLM 后端 ───────────
$tabLLM = New-Object System.Windows.Forms.TabPage
$tabLLM.Text = '  2. LLM 后端  '
$tabs.Controls.Add($tabLLM)

$grpProvider = New-Object System.Windows.Forms.GroupBox
$grpProvider.Text = '推理后端类型'
$grpProvider.Location = New-Object System.Drawing.Point(15, 15)
$grpProvider.Size = New-Object System.Drawing.Size(640, 70)
$tabLLM.Controls.Add($grpProvider)

$rbOllama = New-Object System.Windows.Forms.RadioButton
$rbOllama.Text = '本地 Ollama（推荐：100% 离线、档案不出院）'
$rbOllama.Location = New-Object System.Drawing.Point(15, 25)
$rbOllama.Size = New-Object System.Drawing.Size(310, 22)
$rbOllama.Checked = ($defaults.LLM_PROVIDER -eq 'ollama')
$grpProvider.Controls.Add($rbOllama)

$rbOpenAI = New-Object System.Windows.Forms.RadioButton
$rbOpenAI.Text = '远程 OpenAI 兼容 API（DeepSeek / 智谱 / 自建 vLLM）'
$rbOpenAI.Location = New-Object System.Drawing.Point(330, 25)
$rbOpenAI.Size = New-Object System.Drawing.Size(300, 22)
$rbOpenAI.Checked = ($defaults.LLM_PROVIDER -eq 'openai')
$grpProvider.Controls.Add($rbOpenAI)

# ── Ollama 子区域 ──
$panelOllama = New-Object System.Windows.Forms.Panel
$panelOllama.Location = New-Object System.Drawing.Point(15, 95)
$panelOllama.Size = New-Object System.Drawing.Size(640, 190)
$tabLLM.Controls.Add($panelOllama)

$lblModel = New-Object System.Windows.Forms.Label
$lblModel.Text = '模型名称 (OLLAMA_MODEL_NAME)'
$lblModel.Location = New-Object System.Drawing.Point(0, 0)
$lblModel.Size = New-Object System.Drawing.Size(640, 18)
$panelOllama.Controls.Add($lblModel)

$cbModel = New-Object System.Windows.Forms.ComboBox
$cbModel.Location = New-Object System.Drawing.Point(0, 22)
$cbModel.Size = New-Object System.Drawing.Size(520, 24)
$cbModel.DropDownStyle = 'DropDown'
$cbModel.Items.AddRange(@(
    'hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M',
    'hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q3_K_M',
    'hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q5_K_M',
    'hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q8_0',
    'huatuo_o1_7b',
    'qwen2.5:7b',
    'qwen2.5:3b',
    'llama3.1:8b'
))
$cbModel.Text = $defaults.OLLAMA_MODEL_NAME
$panelOllama.Controls.Add($cbModel)

$btnDetect = New-Object System.Windows.Forms.Button
$btnDetect.Text = '检测 Ollama'
$btnDetect.Location = New-Object System.Drawing.Point(530, 20)
$btnDetect.Size = New-Object System.Drawing.Size(110, 28)
$panelOllama.Controls.Add($btnDetect)

$lblApi = New-Object System.Windows.Forms.Label
$lblApi.Text = 'Ollama API 地址 (OLLAMA_API_URL)'
$lblApi.Location = New-Object System.Drawing.Point(0, 60)
$lblApi.Size = New-Object System.Drawing.Size(640, 18)
$panelOllama.Controls.Add($lblApi)

$txtApi = New-Object System.Windows.Forms.TextBox
$txtApi.Location = New-Object System.Drawing.Point(0, 82)
$txtApi.Size = New-Object System.Drawing.Size(640, 24)
$txtApi.Text = $defaults.OLLAMA_API_URL
$panelOllama.Controls.Add($txtApi)

$lblDetectResult = New-Object System.Windows.Forms.Label
$lblDetectResult.Location = New-Object System.Drawing.Point(0, 115)
$lblDetectResult.Size = New-Object System.Drawing.Size(640, 70)
$lblDetectResult.ForeColor = [System.Drawing.Color]::DimGray
$lblDetectResult.Text = '尚未检测。点击 [检测 Ollama] 验证服务是否在线、当前已安装哪些模型。'
$panelOllama.Controls.Add($lblDetectResult)

$btnDetect.Add_Click({
    $lblDetectResult.ForeColor = [System.Drawing.Color]::DimGray
    $lblDetectResult.Text = '正在检测...'
    $form.Refresh()
    if (Test-OllamaReachable) {
        $models = Get-OllamaModels
        if ($models.Count -gt 0) {
            $lblDetectResult.ForeColor = [System.Drawing.Color]::Green
            $lblDetectResult.Text = "Ollama 在线，已安装 $($models.Count) 个模型：`r`n  " + ($models -join "`r`n  ")
        } else {
            $lblDetectResult.ForeColor = [System.Drawing.Color]::DarkOrange
            $lblDetectResult.Text = "Ollama 在线，但还没装任何模型。`r`n请在终端运行: ollama pull $($cbModel.Text)"
        }
    } else {
        $lblDetectResult.ForeColor = [System.Drawing.Color]::Red
        $lblDetectResult.Text = "Ollama 未响应 http://localhost:11434`r`n请先打开 Ollama 应用，或运行: ollama serve"
    }
})

# ── OpenAI 子区域 ──
$panelOpenAI = New-Object System.Windows.Forms.Panel
$panelOpenAI.Location = New-Object System.Drawing.Point(15, 95)
$panelOpenAI.Size = New-Object System.Drawing.Size(640, 280)
$tabLLM.Controls.Add($panelOpenAI)

$lblBase = New-Object System.Windows.Forms.Label
$lblBase.Text = 'API Base URL (OPENAI_API_BASE)'
$lblBase.Location = New-Object System.Drawing.Point(0, 0)
$lblBase.Size = New-Object System.Drawing.Size(640, 18)
$panelOpenAI.Controls.Add($lblBase)

$txtBase = New-Object System.Windows.Forms.TextBox
$txtBase.Location = New-Object System.Drawing.Point(0, 22)
$txtBase.Size = New-Object System.Drawing.Size(640, 24)
$txtBase.Text = $defaults.OPENAI_API_BASE
$panelOpenAI.Controls.Add($txtBase)

$lblBaseHint = New-Object System.Windows.Forms.Label
$lblBaseHint.Text = '示例: https://api.deepseek.com/v1  /  https://open.bigmodel.cn/api/paas/v4  /  http://gpu:8000/v1'
$lblBaseHint.Location = New-Object System.Drawing.Point(0, 48)
$lblBaseHint.Size = New-Object System.Drawing.Size(640, 16)
$lblBaseHint.ForeColor = [System.Drawing.Color]::DimGray
$panelOpenAI.Controls.Add($lblBaseHint)

$lblOaiModel = New-Object System.Windows.Forms.Label
$lblOaiModel.Text = '模型名 (OPENAI_MODEL)'
$lblOaiModel.Location = New-Object System.Drawing.Point(0, 75)
$lblOaiModel.Size = New-Object System.Drawing.Size(640, 18)
$panelOpenAI.Controls.Add($lblOaiModel)

$txtOaiModel = New-Object System.Windows.Forms.TextBox
$txtOaiModel.Location = New-Object System.Drawing.Point(0, 97)
$txtOaiModel.Size = New-Object System.Drawing.Size(640, 24)
$txtOaiModel.Text = $defaults.OPENAI_MODEL
$panelOpenAI.Controls.Add($txtOaiModel)

$lblOaiKey = New-Object System.Windows.Forms.Label
$lblOaiKey.Text = 'API Key (OPENAI_API_KEY，自建 vLLM 可留空)'
$lblOaiKey.Location = New-Object System.Drawing.Point(0, 130)
$lblOaiKey.Size = New-Object System.Drawing.Size(640, 18)
$panelOpenAI.Controls.Add($lblOaiKey)

$txtOaiKey = New-Object System.Windows.Forms.TextBox
$txtOaiKey.Location = New-Object System.Drawing.Point(0, 152)
$txtOaiKey.Size = New-Object System.Drawing.Size(640, 24)
$txtOaiKey.Text = $defaults.OPENAI_API_KEY
$txtOaiKey.UseSystemPasswordChar = $true
$panelOpenAI.Controls.Add($txtOaiKey)

$ckShowKey = New-Object System.Windows.Forms.CheckBox
$ckShowKey.Text = '显示明文'
$ckShowKey.Location = New-Object System.Drawing.Point(0, 180)
$ckShowKey.Size = New-Object System.Drawing.Size(120, 22)
$ckShowKey.Add_CheckedChanged({ $txtOaiKey.UseSystemPasswordChar = -not $ckShowKey.Checked })
$panelOpenAI.Controls.Add($ckShowKey)

# 单选切换显示
function Update-LLMPanels {
    $panelOllama.Visible = $rbOllama.Checked
    $panelOpenAI.Visible = $rbOpenAI.Checked
}
$rbOllama.Add_CheckedChanged({ Update-LLMPanels })
$rbOpenAI.Add_CheckedChanged({ Update-LLMPanels })
Update-LLMPanels

# ─────────── Tab 3：服务参数 ───────────
$tabService = New-Object System.Windows.Forms.TabPage
$tabService.Text = '  3. 服务参数  '
$tabs.Controls.Add($tabService)

$lblHost = New-Object System.Windows.Forms.Label
$lblHost.Text = '监听地址 (HOST)'
$lblHost.Location = New-Object System.Drawing.Point(15, 18)
$lblHost.Size = New-Object System.Drawing.Size(300, 18)
$tabService.Controls.Add($lblHost)

$cbHost = New-Object System.Windows.Forms.ComboBox
$cbHost.Location = New-Object System.Drawing.Point(15, 40)
$cbHost.Size = New-Object System.Drawing.Size(300, 24)
$cbHost.DropDownStyle = 'DropDown'
$cbHost.Items.AddRange(@('127.0.0.1', '0.0.0.0'))
$cbHost.Text = $defaults.HOST
$tabService.Controls.Add($cbHost)

$lblHostHint = New-Object System.Windows.Forms.Label
$lblHostHint.Text = '127.0.0.1：仅本机访问；0.0.0.0：开放给局域网内其他设备'
$lblHostHint.Location = New-Object System.Drawing.Point(15, 68)
$lblHostHint.Size = New-Object System.Drawing.Size(640, 18)
$lblHostHint.ForeColor = [System.Drawing.Color]::DimGray
$tabService.Controls.Add($lblHostHint)

$lblPort = New-Object System.Windows.Forms.Label
$lblPort.Text = '端口 (PORT)'
$lblPort.Location = New-Object System.Drawing.Point(340, 18)
$lblPort.Size = New-Object System.Drawing.Size(140, 18)
$tabService.Controls.Add($lblPort)

$txtPort = New-Object System.Windows.Forms.TextBox
$txtPort.Location = New-Object System.Drawing.Point(340, 40)
$txtPort.Size = New-Object System.Drawing.Size(140, 24)
$txtPort.Text = $defaults.PORT
$tabService.Controls.Add($txtPort)

$lblUpload = New-Object System.Windows.Forms.Label
$lblUpload.Text = '单张病历照片大小上限 (MB)'
$lblUpload.Location = New-Object System.Drawing.Point(15, 110)
$lblUpload.Size = New-Object System.Drawing.Size(300, 18)
$tabService.Controls.Add($lblUpload)

$txtUpload = New-Object System.Windows.Forms.TextBox
$txtUpload.Location = New-Object System.Drawing.Point(15, 132)
$txtUpload.Size = New-Object System.Drawing.Size(140, 24)
$txtUpload.Text = $defaults.MAX_UPLOAD_SIZE_MB
$tabService.Controls.Add($txtUpload)

$ckDegraded = New-Object System.Windows.Forms.CheckBox
$ckDegraded.Text = '允许降级启动 (EMBEDDING_ALLOW_DEGRADED) — 推荐勾上'
$ckDegraded.Location = New-Object System.Drawing.Point(15, 180)
$ckDegraded.Size = New-Object System.Drawing.Size(640, 22)
$ckDegraded.Checked = ($defaults.EMBEDDING_ALLOW_DEGRADED -eq 'true')
$tabService.Controls.Add($ckDegraded)

$lblDegHint = New-Object System.Windows.Forms.Label
$lblDegHint.Text = '勾选后即使 embedding 模型加载失败，服务也能起来（RAG 不可用，但基础对话可用）。生产环境若要严格模式可关闭。'
$lblDegHint.Location = New-Object System.Drawing.Point(35, 205)
$lblDegHint.Size = New-Object System.Drawing.Size(620, 32)
$lblDegHint.ForeColor = [System.Drawing.Color]::DimGray
$tabService.Controls.Add($lblDegHint)

# ─────────── 底部按钮 ───────────
$btnSave = New-Object System.Windows.Forms.Button
$btnSave.Text = '保存并继续'
$btnSave.Location = New-Object System.Drawing.Point(440, 555)
$btnSave.Size = New-Object System.Drawing.Size(120, 32)
$btnSave.BackColor = [System.Drawing.Color]::FromArgb(16, 185, 129)
$btnSave.ForeColor = [System.Drawing.Color]::White
$btnSave.FlatStyle = 'Flat'
$form.Controls.Add($btnSave)

$btnCancel = New-Object System.Windows.Forms.Button
$btnCancel.Text = '取消'
$btnCancel.Location = New-Object System.Drawing.Point(575, 555)
$btnCancel.Size = New-Object System.Drawing.Size(120, 32)
$form.Controls.Add($btnCancel)

$btnExample = New-Object System.Windows.Forms.Button
$btnExample.Text = '查看 .env.example'
$btnExample.Location = New-Object System.Drawing.Point(15, 555)
$btnExample.Size = New-Object System.Drawing.Size(150, 32)
$btnExample.Add_Click({
    if (Test-Path $EnvExample) {
        Start-Process notepad.exe -ArgumentList "`"$EnvExample`""
    } else {
        [System.Windows.Forms.MessageBox]::Show('.env.example 不存在', '提示', 'OK', 'Information') | Out-Null
    }
})
$form.Controls.Add($btnExample)

$saved = $false

$btnSave.Add_Click({
    # 校验
    $errors = @()
    if (-not $txtAuth.Text.Trim())             { $errors += '请填写或生成 AUTH_TOKEN' }
    if (-not $txtPii.Text.Trim())              { $errors += '请填写或生成 PII_ENCRYPTION_KEY' }
    if ($txtPii.Text.Trim() -and $txtPii.Text.Trim().Length -ne 44) {
        $errors += "PII_ENCRYPTION_KEY 必须为 44 字符（当前 $($txtPii.Text.Trim().Length) 字符）。建议点 [生成]。"
    }
    if ($rbOllama.Checked) {
        if (-not $cbModel.Text.Trim())         { $errors += '请填写 OLLAMA_MODEL_NAME' }
        if (-not $txtApi.Text.Trim())          { $errors += '请填写 OLLAMA_API_URL' }
    } else {
        if (-not $txtBase.Text.Trim())         { $errors += '请填写 OPENAI_API_BASE' }
        if (-not $txtOaiModel.Text.Trim())     { $errors += '请填写 OPENAI_MODEL' }
    }
    $portInt = 0
    if (-not [int]::TryParse($txtPort.Text.Trim(), [ref]$portInt) -or $portInt -lt 1 -or $portInt -gt 65535) {
        $errors += '端口必须是 1-65535 之间的整数'
    }

    if ($errors.Count -gt 0) {
        [System.Windows.Forms.MessageBox]::Show(
            ($errors -join "`r`n"),
            '配置不完整',
            'OK',
            'Warning'
        ) | Out-Null
        return
    }

    # 组装 updates
    $updates = @{
        AUTH_TOKEN               = $txtAuth.Text.Trim()
        PII_ENCRYPTION_KEY       = $txtPii.Text.Trim()
        LLM_PROVIDER             = if ($rbOllama.Checked) { 'ollama' } else { 'openai' }
        HOST                     = $cbHost.Text.Trim()
        PORT                     = $txtPort.Text.Trim()
        MAX_UPLOAD_SIZE_MB       = $txtUpload.Text.Trim()
        EMBEDDING_ALLOW_DEGRADED = if ($ckDegraded.Checked) { 'true' } else { 'false' }
    }
    if ($rbOllama.Checked) {
        $updates['OLLAMA_MODEL_NAME'] = $cbModel.Text.Trim()
        $updates['OLLAMA_API_URL']    = $txtApi.Text.Trim()
        # 切到 ollama 时清掉 OpenAI 三件套，避免残留配置误导
        $updates['OPENAI_API_BASE'] = ''
        $updates['OPENAI_MODEL']    = ''
        $updates['OPENAI_API_KEY']  = ''
    } else {
        $updates['OPENAI_API_BASE'] = $txtBase.Text.Trim()
        $updates['OPENAI_MODEL']    = $txtOaiModel.Text.Trim()
        $updates['OPENAI_API_KEY']  = $txtOaiKey.Text.Trim()
    }

    # 保存
    try {
        Save-EnvFile -Path $EnvPath -Updates $updates
        $script:saved = $true

        # 备份 AUTH_TOKEN 到一个独立的醒目文件，方便院方第一次看到管理员 Token
        $tokenBackup = Join-Path $ProjectDir 'admin-token.txt'
        $backupContent = @"
======================================================================
智护银伴 · 管理员 Token (AUTH_TOKEN)
生成时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
======================================================================

$($updates.AUTH_TOKEN)

======================================================================
说明：
1. 这是您的最高权限 Token，等同于"管理员密码"。
2. 第一次打开管理端 (http://$($updates.HOST):$($updates.PORT)/) 时，
   把它粘贴到顶部的 Token 输入框即可登录。
3. 请妥善保管：复制到密码管理器、打印一份放保险柜，等等。
4. 看完请删除本文件，避免泄露。
======================================================================
"@
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tokenBackup, $backupContent, $utf8NoBom)

        [System.Windows.Forms.MessageBox]::Show(
            ".env 已保存到：`r`n  $EnvPath`r`n`r`n管理员 Token 副本已写入：`r`n  $tokenBackup`r`n（妥善保管后请删除）",
            '保存成功',
            'OK',
            'Information'
        ) | Out-Null

        $form.Close()
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            "保存失败: $($_.Exception.Message)",
            '错误',
            'OK',
            'Error'
        ) | Out-Null
    }
})

$btnCancel.Add_Click({ $form.Close() })

# 显示
[void]$form.ShowDialog()

if ($saved) {
    Write-Host "配置已保存到 $EnvPath" -ForegroundColor Green
    exit 0
} else {
    Write-Host "用户取消，未保存。" -ForegroundColor Yellow
    exit 2
}
