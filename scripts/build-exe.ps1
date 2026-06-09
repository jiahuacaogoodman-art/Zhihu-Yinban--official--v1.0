#Requires -Version 5.1
<#
.SYNOPSIS
    智护银伴 · 一键打包 .exe（PS2EXE）
.DESCRIPTION
    把 launch-local.ps1 和 setup-wizard.ps1 编译成两个独立的 Windows 可执行文件：

        dist/智护银伴启动器.exe   ← 双击即启动后端 + 浏览器
        dist/配置向导.exe         ← 双击即弹 GUI 改 .env

    注意：本文件保存为 UTF-8 with BOM，保证 Windows PowerShell 5.1 正确读取中文。
.PARAMETER Version
    写入 EXE 资源段的版本号，默认 1.0.0.0。
.PARAMETER OutputDir
    产物目录，默认 ./dist。
.PARAMETER IconFile
    图标文件路径，默认 ./assets/logo.ico。
.PARAMETER SkipInstallModule
    跳过自动安装 ps2exe。
#>

[CmdletBinding()]
param(
    [string]$Version = '1.0.0.0',
    [string]$OutputDir,
    [string]$IconFile,
    [switch]$SkipInstallModule
)

$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir
if (-not $OutputDir) { $OutputDir = Join-Path $ProjectDir 'dist' }
if (-not $IconFile)  { $IconFile  = Join-Path $ProjectDir 'assets\logo.ico' }

$LauncherSrc = Join-Path $ScriptDir 'launch-local.ps1'
$WizardSrc   = Join-Path $ScriptDir 'setup-wizard.ps1'

if ($PSVersionTable.PSVersion.Major -ge 6 -and -not $IsWindows) {
    throw '本脚本只能在 Windows 上运行（PS2EXE 产出 PE 格式 .exe，非 Windows 无意义）。'
}

Write-Host '智护银伴 · 打包构建' -ForegroundColor White
Write-Host "项目目录: $ProjectDir" -ForegroundColor DarkGray
Write-Host "输出目录: $OutputDir" -ForegroundColor DarkGray
Write-Host "版本号:   $Version" -ForegroundColor DarkGray

if (-not (Test-Path $LauncherSrc)) { throw "找不到源脚本：$LauncherSrc" }
if (-not (Test-Path $WizardSrc))   { throw "找不到源脚本：$WizardSrc" }

if (-not $SkipInstallModule) {
    if (-not (Get-Module -ListAvailable -Name ps2exe)) {
        Write-Host '==> 首次构建：安装 ps2exe 模块（CurrentUser 作用域）...' -ForegroundColor Cyan
        try {
            if (-not (Get-PSRepository -Name PSGallery -ErrorAction SilentlyContinue)) {
                Register-PSRepository -Default -ErrorAction SilentlyContinue
            }
            Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction SilentlyContinue
            Install-Module -Name ps2exe -Scope CurrentUser -Force -AllowClobber
        } catch {
            throw "ps2exe 安装失败：$($_.Exception.Message)。可手动执行：Install-Module ps2exe -Scope CurrentUser"
        }
    }
}
Import-Module ps2exe -ErrorAction Stop

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$useIcon = Test-Path $IconFile
if (-not $useIcon) {
    Write-Host "  (未找到图标 $IconFile，将使用默认图标。要换 logo 时把 .ico 文件放在该路径下重新构建即可。)" -ForegroundColor Yellow
}

$common = @{
    company   = '智护银伴'
    product   = '智护银伴'
    copyright = "(c) $(Get-Date -Format yyyy) 智护银伴项目组"
    version   = $Version
}

function Invoke-PackageOne {
    param(
        [string]$InputFile,
        [string]$OutputFile,
        [string]$Title,
        [string]$Description,
        [switch]$NoConsole
    )

    Write-Host "`n==> 打包 $Title" -ForegroundColor Cyan
    Write-Host "    $InputFile  ->  $OutputFile" -ForegroundColor DarkGray

    $packArgs = @{
        InputFile   = $InputFile
        OutputFile  = $OutputFile
        Title       = $Title
        Description = $Description
        Company     = $common.company
        Product     = $common.product
        Copyright   = $common.copyright
        Version     = $common.version
        STA         = $true
    }
    if ($NoConsole) { $packArgs['NoConsole'] = $true }
    if ($useIcon)   { $packArgs['IconFile']  = $IconFile }

    Invoke-PS2EXE @packArgs | Out-Null

    if (-not (Test-Path $OutputFile)) {
        throw "打包失败：未生成 $OutputFile"
    }
    $size = [math]::Round(((Get-Item $OutputFile).Length / 1KB), 1)
    Write-Host "    OK  $OutputFile  ($size KB)" -ForegroundColor Green
}

Invoke-PackageOne `
    -InputFile   $LauncherSrc `
    -OutputFile  (Join-Path $OutputDir '智护银伴启动器.exe') `
    -Title       '智护银伴启动器' `
    -Description '智护银伴本地应用 - 启动后端服务并打开管理端浏览器'

Invoke-PackageOne `
    -InputFile   $WizardSrc `
    -OutputFile  (Join-Path $OutputDir '配置向导.exe') `
    -Title       '智护银伴 · 配置向导' `
    -Description '智护银伴本地应用 - 图形化配置 .env（一键生成密钥、切换 LLM 后端）' `
    -NoConsole

$batLauncher = Join-Path $ProjectDir '启动智护银伴.bat'
$batWizard   = Join-Path $ProjectDir '配置向导.bat'
if (Test-Path $batLauncher) { Copy-Item $batLauncher $OutputDir -Force }
if (Test-Path $batWizard)   { Copy-Item $batWizard   $OutputDir -Force }

Write-Host "`n构建完成。" -ForegroundColor Green
Write-Host "  输出目录: $OutputDir"
Write-Host '  下一步:'
Write-Host '    1) 把整个 dist/ 文件夹连同项目代码、scripts/、.env.example 一起打 zip 给客户'
Write-Host '    2) 或者用 Inno Setup / WiX 进一步做 MSI / Setup.exe 安装包'
Write-Host '    3) 商业交付前建议给 .exe 做代码签名，避免 SmartScreen 拦截首次运行'
