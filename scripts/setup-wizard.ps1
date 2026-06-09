#Requires -Version 5.1
[CmdletBinding()]
param([switch]$NonInteractive)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvPath = Join-Path $ProjectDir '.env'
$EnvExample = Join-Path $ProjectDir '.env.example'

function New-Token {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

function Ensure-Env {
    if (-not (Test-Path $EnvPath)) {
        if (Test-Path $EnvExample) { Copy-Item $EnvExample $EnvPath -Force }
        else { New-Item -ItemType File -Path $EnvPath -Force | Out-Null }
    }
}

function Read-Env {
    Ensure-Env
    $map = @{}
    Get-Content $EnvPath -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') { $map[$matches[1]] = $matches[2] }
    }
    $map
}

function Get-EnvDefault($Map, $Key, $Default) {
    if ($Map.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Map[$Key])) { return $Map[$Key] }
    return $Default
}

function Write-Env($Values) {
    Ensure-Env
    $lines = @(Get-Content $EnvPath -ErrorAction SilentlyContinue)
    $seen = @{}
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ($line -match '^\s*([^#=\s]+)\s*=') {
            $key = $matches[1]
            if ($Values.ContainsKey($key)) { $out.Add("$key=$($Values[$key])"); $seen[$key] = $true }
            else { $out.Add($line) }
        } else { $out.Add($line) }
    }
    foreach ($key in $Values.Keys) { if (-not $seen.ContainsKey($key)) { $out.Add("$key=$($Values[$key])") } }
    $enc = New-Object System.Text.UTF8Encoding($true)
    [System.IO.File]::WriteAllLines($EnvPath, $out.ToArray(), $enc)
}

$env = Read-Env
$auth = Get-EnvDefault $env 'AUTH_TOKEN' (New-Token)
$secret = Get-EnvDefault $env 'SECRET_KEY' $auth
$model = Get-EnvDefault $env 'OLLAMA_MODEL' 'huatuo_o1_7b'
$port = Get-EnvDefault $env 'APP_PORT' '8000'
$ollamaUrl = Get-EnvDefault $env 'OLLAMA_BASE_URL' 'http://ollama:11434'

if ($NonInteractive) {
    Write-Env @{ AUTH_TOKEN=$auth; SECRET_KEY=$secret; JWT_SECRET=$secret; OLLAMA_MODEL=$model; OLLAMA_MODEL_NAME=$model; LLM_MODEL=$model; OLLAMA_BASE_URL=$ollamaUrl; APP_PORT=$port; AUDIT_LOG_ENABLED='true'; PII_MASK_ENABLED='true' }
    Write-Host "Saved $EnvPath"
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Zhihu Yinban Setup Wizard'
$form.Size = New-Object System.Drawing.Size -ArgumentList 680, 430
$form.StartPosition = 'CenterScreen'
$form.Font = [System.Drawing.Font]::new('Microsoft YaHei UI', [single]9)

$title = New-Object System.Windows.Forms.Label
$title.Text = 'Zhihu Yinban local setup'
$title.Location = New-Object System.Drawing.Point -ArgumentList 16, 16
$title.Size = New-Object System.Drawing.Size -ArgumentList 620, 24
$title.Font = [System.Drawing.Font]::new('Microsoft YaHei UI', [single]11, [System.Drawing.FontStyle]::Bold)
$form.Controls.Add($title)

function AddLabel($text, $y) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $text
    $l.Location = New-Object System.Drawing.Point -ArgumentList 18, $y
    $l.Size = New-Object System.Drawing.Size -ArgumentList 170, 22
    $form.Controls.Add($l)
    $l
}
function AddBox($text, $y) {
    $b = New-Object System.Windows.Forms.TextBox
    $b.Text = $text
    $b.Location = New-Object System.Drawing.Point -ArgumentList 190, $y
    $b.Size = New-Object System.Drawing.Size -ArgumentList 360, 24
    $form.Controls.Add($b)
    $b
}

AddLabel 'AUTH_TOKEN' 62 | Out-Null
$txtAuth = AddBox $auth 58
$txtAuth.Font = [System.Drawing.Font]::new('Consolas', [single]9)
$btnToken = New-Object System.Windows.Forms.Button
$btnToken.Text = 'Generate'
$btnToken.Location = New-Object System.Drawing.Point -ArgumentList 560, 56
$btnToken.Size = New-Object System.Drawing.Size -ArgumentList 82, 28
$btnToken.Add_Click({ $txtAuth.Text = New-Token })
$form.Controls.Add($btnToken)

AddLabel 'APP_PORT' 102 | Out-Null
$txtPort = AddBox $port 98
AddLabel 'OLLAMA_BASE_URL' 142 | Out-Null
$txtOllamaUrl = AddBox $ollamaUrl 138
AddLabel 'OLLAMA_MODEL' 182 | Out-Null
$txtModel = AddBox $model 178

$status = New-Object System.Windows.Forms.Label
$status.Text = "Target: $EnvPath"
$status.Location = New-Object System.Drawing.Point -ArgumentList 18, 230
$status.Size = New-Object System.Drawing.Size -ArgumentList 620, 60
$form.Controls.Add($status)

$btnTest = New-Object System.Windows.Forms.Button
$btnTest.Text = 'Test Ollama'
$btnTest.Location = New-Object System.Drawing.Point -ArgumentList 320, 320
$btnTest.Size = New-Object System.Drawing.Size -ArgumentList 100, 32
$btnTest.Add_Click({
    $url = $txtOllamaUrl.Text.Trim()
    if ($url -match '://ollama(:|/|$)') { $url = 'http://localhost:11434' }
    $url = $url.TrimEnd('/') + '/api/tags'
    try { Invoke-RestMethod -Uri $url -TimeoutSec 3 -ErrorAction Stop | Out-Null; $status.Text = 'Ollama is reachable.' }
    catch { $status.Text = "Ollama is not reachable: $url" }
})
$form.Controls.Add($btnTest)

$btnSave = New-Object System.Windows.Forms.Button
$btnSave.Text = 'Save .env'
$btnSave.Location = New-Object System.Drawing.Point -ArgumentList 430, 320
$btnSave.Size = New-Object System.Drawing.Size -ArgumentList 100, 32
$btnSave.Add_Click({
    $p = 0
    if (-not [int]::TryParse($txtPort.Text.Trim(), [ref]$p) -or $p -lt 1 -or $p -gt 65535) {
        [System.Windows.Forms.MessageBox]::Show('APP_PORT must be 1-65535.', 'Invalid config', 'OK', 'Warning') | Out-Null
        return
    }
    $token = $txtAuth.Text.Trim()
    $m = $txtModel.Text.Trim()
    Write-Env @{ AUTH_TOKEN=$token; SECRET_KEY=$token; JWT_SECRET=$token; OLLAMA_MODEL=$m; OLLAMA_MODEL_NAME=$m; LLM_MODEL=$m; OLLAMA_BASE_URL=$txtOllamaUrl.Text.Trim(); APP_PORT=$txtPort.Text.Trim(); AUDIT_LOG_ENABLED='true'; PII_MASK_ENABLED='true' }
    [System.Windows.Forms.MessageBox]::Show("Saved $EnvPath", 'Saved', 'OK', 'Information') | Out-Null
    $form.Close()
})
$form.Controls.Add($btnSave)

$btnCancel = New-Object System.Windows.Forms.Button
$btnCancel.Text = 'Cancel'
$btnCancel.Location = New-Object System.Drawing.Point -ArgumentList 540, 320
$btnCancel.Size = New-Object System.Drawing.Size -ArgumentList 100, 32
$btnCancel.Add_Click({ $form.Close() })
$form.Controls.Add($btnCancel)

[void]$form.ShowDialog()
