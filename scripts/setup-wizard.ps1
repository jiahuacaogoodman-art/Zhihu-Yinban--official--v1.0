#Requires -Version 5.1
[CmdletBinding()]
param([switch]$NonInteractive)

$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvPath = Join-Path $ProjectDir '.env'
$EnvExample = Join-Path $ProjectDir '.env.example'

function New-SetupToken { (([guid]::NewGuid()).ToString('N') + ([guid]::NewGuid()).ToString('N')) }
function New-SetupKey { [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((New-SetupToken).Substring(0,32))).Replace('+','-').Replace('/','_') }

function Ensure-EnvFile {
    if (-not (Test-Path $EnvPath)) {
        if (Test-Path $EnvExample) { Copy-Item $EnvExample $EnvPath -Force } else { New-Item -ItemType File -Path $EnvPath -Force | Out-Null }
    }
}

function Read-EnvMap {
    Ensure-EnvFile
    $map = @{}
    Get-Content $EnvPath -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') { $map[$matches[1]] = $matches[2] }
    }
    return $map
}

function Get-EnvDefault([hashtable]$Map, [string]$Key, [string]$Default) {
    if ($Map.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace([string]$Map[$Key])) { return [string]$Map[$Key] }
    return $Default
}

function Write-EnvValues([hashtable]$Values) {
    Ensure-EnvFile
    $lines = @(Get-Content $EnvPath -ErrorAction SilentlyContinue)
    $seen = @{}
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) {
        if ($line -match '^\s*([^#=\s]+)\s*=') {
            $key = $matches[1]
            if ($Values.ContainsKey($key)) { $out.Add("$key=$($Values[$key])"); $seen[$key] = $true } else { $out.Add($line) }
        } else { $out.Add($line) }
    }
    foreach ($key in $Values.Keys) { if (-not $seen.ContainsKey($key)) { $out.Add("$key=$($Values[$key])") } }
    $utf8bom = New-Object System.Text.UTF8Encoding($true)
    [IO.File]::WriteAllLines($EnvPath, $out.ToArray(), $utf8bom)
}

$envMap = Read-EnvMap
$defaults = @{
    AUTH_TOKEN = Get-EnvDefault $envMap 'AUTH_TOKEN' (New-SetupToken)
    PII_ENCRYPTION_KEY = Get-EnvDefault $envMap 'PII_ENCRYPTION_KEY' (New-SetupKey)
    LLM_PROVIDER = Get-EnvDefault $envMap 'LLM_PROVIDER' 'ollama'
    OLLAMA_MODEL_NAME = Get-EnvDefault $envMap 'OLLAMA_MODEL_NAME' 'hf.co/mradermacher/HuatuoGPT-o1-7B-GGUF:Q4_K_M'
    OLLAMA_API_URL = Get-EnvDefault $envMap 'OLLAMA_API_URL' 'http://localhost:11434/api/generate'
    OPENAI_API_BASE = Get-EnvDefault $envMap 'OPENAI_API_BASE' ''
    OPENAI_MODEL = Get-EnvDefault $envMap 'OPENAI_MODEL' ''
    OPENAI_API_KEY = Get-EnvDefault $envMap 'OPENAI_API_KEY' ''
    HOST = Get-EnvDefault $envMap 'HOST' '127.0.0.1'
    PORT = Get-EnvDefault $envMap 'PORT' '8000'
    EMBEDDING_ALLOW_DEGRADED = Get-EnvDefault $envMap 'EMBEDDING_ALLOW_DEGRADED' 'true'
}

function Save-CurrentConfig { param([hashtable]$Values) Write-EnvValues $Values }

if ($NonInteractive) {
    Save-CurrentConfig $defaults
    Write-Host "Setup complete: $EnvPath" -ForegroundColor Green
    exit 0
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object Windows.Forms.Form
$form.Text = 'Zhihu Yinban Setup Wizard'
$form.Size = New-Object Drawing.Size -ArgumentList 720, 560
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = [Drawing.Font]::new('Microsoft YaHei UI', [single]9)

$title = New-Object Windows.Forms.Label
$title.Text = 'Configure local .env settings'
$title.Location = New-Object Drawing.Point -ArgumentList 18, 14
$title.Size = New-Object Drawing.Size -ArgumentList 660, 24
$title.Font = [Drawing.Font]::new('Microsoft YaHei UI', [single]11, [Drawing.FontStyle]::Bold)
$form.Controls.Add($title)

function Add-Label($Text, $X, $Y) { $l=New-Object Windows.Forms.Label; $l.Text=$Text; $l.Location=New-Object Drawing.Point -ArgumentList $X,$Y; $l.Size=New-Object Drawing.Size -ArgumentList 160,22; $form.Controls.Add($l); $l }
function Add-Box($X,$Y,$W,$Text) { $b=New-Object Windows.Forms.TextBox; $b.Location=New-Object Drawing.Point -ArgumentList $X,$Y; $b.Size=New-Object Drawing.Size -ArgumentList $W,24; $b.Text=$Text; $form.Controls.Add($b); $b }

Add-Label 'AUTH_TOKEN' 20 62 | Out-Null
$txtAuth = Add-Box 190 58 390 $defaults.AUTH_TOKEN
$txtAuth.Font = [Drawing.Font]::new('Consolas', [single]9)
$btnAuth = New-Object Windows.Forms.Button
$btnAuth.Text='Generate'; $btnAuth.Location=New-Object Drawing.Point -ArgumentList 590,56; $btnAuth.Size=New-Object Drawing.Size -ArgumentList 90,28
$btnAuth.Add_Click({ $txtAuth.Text = New-SetupToken })
$form.Controls.Add($btnAuth)

Add-Label 'PII_ENCRYPTION_KEY' 20 100 | Out-Null
$txtPii = Add-Box 190 96 390 $defaults.PII_ENCRYPTION_KEY
$txtPii.Font = [Drawing.Font]::new('Consolas', [single]9)
$btnPii = New-Object Windows.Forms.Button
$btnPii.Text='Generate'; $btnPii.Location=New-Object Drawing.Point -ArgumentList 590,94; $btnPii.Size=New-Object Drawing.Size -ArgumentList 90,28
$btnPii.Add_Click({ $txtPii.Text = New-SetupKey })
$form.Controls.Add($btnPii)

Add-Label 'LLM_PROVIDER' 20 146 | Out-Null
$cmbProvider = New-Object Windows.Forms.ComboBox
$cmbProvider.Location=New-Object Drawing.Point -ArgumentList 190,142; $cmbProvider.Size=New-Object Drawing.Size -ArgumentList 160,24; $cmbProvider.DropDownStyle='DropDownList'
@('ollama','openai','disabled') | ForEach-Object { [void]$cmbProvider.Items.Add($_) }
if ($cmbProvider.Items.Contains($defaults.LLM_PROVIDER)) { $cmbProvider.SelectedItem=$defaults.LLM_PROVIDER } else { $cmbProvider.SelectedIndex=0 }
$form.Controls.Add($cmbProvider)

Add-Label 'OLLAMA_MODEL_NAME' 20 184 | Out-Null
$txtOllamaModel = Add-Box 190 180 390 $defaults.OLLAMA_MODEL_NAME
Add-Label 'OLLAMA_API_URL' 20 222 | Out-Null
$txtOllamaUrl = Add-Box 190 218 390 $defaults.OLLAMA_API_URL
Add-Label 'OPENAI_API_BASE' 20 260 | Out-Null
$txtOpenAIBase = Add-Box 190 256 390 $defaults.OPENAI_API_BASE
Add-Label 'OPENAI_MODEL' 20 298 | Out-Null
$txtOpenAIModel = Add-Box 190 294 390 $defaults.OPENAI_MODEL
Add-Label 'OPENAI_API_KEY' 20 336 | Out-Null
$txtOpenAIKey = Add-Box 190 332 390 $defaults.OPENAI_API_KEY
$txtOpenAIKey.UseSystemPasswordChar = $true
Add-Label 'HOST' 20 374 | Out-Null
$txtHost = Add-Box 190 370 180 $defaults.HOST
Add-Label 'PORT' 390 374 | Out-Null
$txtPort = Add-Box 450 370 130 $defaults.PORT

$status = New-Object Windows.Forms.Label
$status.Text = "Target: $EnvPath"
$status.Location = New-Object Drawing.Point -ArgumentList 20, 420
$status.Size = New-Object Drawing.Size -ArgumentList 660, 28
$form.Controls.Add($status)

$btnSave = New-Object Windows.Forms.Button
$btnSave.Text='Save .env'; $btnSave.Location=New-Object Drawing.Point -ArgumentList 455,470; $btnSave.Size=New-Object Drawing.Size -ArgumentList 105,32
$btnCancel = New-Object Windows.Forms.Button
$btnCancel.Text='Cancel'; $btnCancel.Location=New-Object Drawing.Point -ArgumentList 575,470; $btnCancel.Size=New-Object Drawing.Size -ArgumentList 105,32
$btnCancel.Add_Click({ $form.Close() })
$form.Controls.Add($btnSave); $form.Controls.Add($btnCancel)

$btnSave.Add_Click({
    $p = 0
    if (-not [int]::TryParse($txtPort.Text.Trim(), [ref]$p) -or $p -lt 1 -or $p -gt 65535) { [Windows.Forms.MessageBox]::Show('PORT must be 1-65535.','Invalid config','OK','Warning') | Out-Null; return }
    $values = @{
        AUTH_TOKEN=$txtAuth.Text.Trim(); PII_ENCRYPTION_KEY=$txtPii.Text.Trim(); LLM_PROVIDER=[string]$cmbProvider.SelectedItem;
        OLLAMA_MODEL_NAME=$txtOllamaModel.Text.Trim(); OLLAMA_API_URL=$txtOllamaUrl.Text.Trim(); OPENAI_API_BASE=$txtOpenAIBase.Text.Trim();
        OPENAI_MODEL=$txtOpenAIModel.Text.Trim(); OPENAI_API_KEY=$txtOpenAIKey.Text.Trim(); HOST=$txtHost.Text.Trim(); PORT=$txtPort.Text.Trim();
        EMBEDDING_ALLOW_DEGRADED=$defaults.EMBEDDING_ALLOW_DEGRADED
    }
    try { Save-CurrentConfig $values; [Windows.Forms.MessageBox]::Show("Saved: $EnvPath",'Success','OK','Information') | Out-Null; $form.Close() }
    catch { [Windows.Forms.MessageBox]::Show($_.Exception.Message,'Save failed','OK','Error') | Out-Null }
})

[void]$form.ShowDialog()
