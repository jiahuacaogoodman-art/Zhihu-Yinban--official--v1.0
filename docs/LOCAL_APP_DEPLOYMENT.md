# 智护银伴 · 本地应用化部署说明

本说明面向试点演示、养老院院内部署和非开发者运维场景。

项目仍然保留 Docker / Uvicorn 等开发者部署方式，但商业化交付时不应要求养老院用户理解 Docker、端口、venv、uvicorn、环境变量等概念。因此新增 Windows 本地启动器和图形化配置向导，把常见部署动作封装成"双击 + 弹窗填写"。

## 一、最简启动方式（推荐给非开发者）

**不需要打开命令行，直接在项目根目录双击：**

```
启动智护银伴.bat
```

第一次启动会自动弹出 **配置向导窗口**，向导分三页填写：

1. **安全密钥**：点 [生成] 按钮自动生成 `AUTH_TOKEN` 和 `PII_ENCRYPTION_KEY`，无需 openssl 或 Python；
2. **LLM 后端**：单选本地 Ollama 或远程 OpenAI 兼容 API；选 Ollama 时可点 [检测] 验证服务和已装模型；
3. **服务参数**：监听地址、端口、上传大小、降级开关。

填完点 [保存并继续]，向导会：

- 把所有配置写入项目根目录 `.env`（保留原有注释，按"存在即替换、不存在则追加"处理，不会吃掉你之前自己加的自定义键）；
- 把生成的 `AUTH_TOKEN` 同时写入根目录 `admin-token.txt`（方便第一次部署时找到管理员 Token，看完请删除）；
- 自动关闭向导，返回启动器；
- 启动器继续后续步骤：装依赖 → 启动后端 → 等健康检查 → 自动打开浏览器。

之后再次双击 `启动智护银伴.bat`，向导**不会**再次弹出（除非删了 .env 或某个关键字段为空）。

### 单独打开配置向导

不想启动服务，只想改配置（换 Token、切 LLM 后端、换端口等）：

```
配置向导.bat
```

双击即可。

## 二、PowerShell 高级用法

熟悉命令行的运维人员仍可直接调用 PowerShell 脚本：

```powershell
# 标准启动（缺配置时自动弹窗）
.\scripts\launch-local.ps1

# 强制弹出配置向导（即使 .env 已经齐全）
.\scripts\launch-local.ps1 -RunWizard

# 自动化场景：禁止任何弹窗（CI / 远程脚本）
.\scripts\launch-local.ps1 -NoWizard

# 单独运行向导
.\scripts\setup-wizard.ps1

# 自动化模式：仅生成缺失的密钥，不弹窗
.\scripts\setup-wizard.ps1 -NonInteractive
```

默认访问地址：

- 管理端：http://127.0.0.1:8000/
- 护工端：http://127.0.0.1:8000/nurse
- 健康检查：http://127.0.0.1:8000/health

第一次进入管理端时，把 `admin-token.txt` 里的 Token 粘贴到顶部输入框即可登录。

## 三、常用参数

### 1. 快速启动，不重复安装依赖

首次启动成功后，后续可以使用：

```powershell
.\scripts\launch-local.ps1 -SkipInstall
```

### 2. 允许没有 Ollama 时启动

只演示入院、床位、护理记录、交接班等非 AI 业务模块时：

```powershell
.\scripts\launch-local.ps1 -AllowNoOllama
```

### 3. 局域网访问

如果需要同一养老院局域网内其他电脑访问：

```powershell
.\scripts\launch-local.ps1 -BindAddress 0.0.0.0
```

然后在其他电脑访问部署机器的局域网 IP，例如：

```text
http://192.168.1.10:8000/
```

注意：需要 Windows 防火墙允许该端口入站访问。

### 4. 修改端口

```powershell
.\scripts\launch-local.ps1 -Port 8010
```

## 四、部署诊断

如果启动失败，先运行：

```powershell
.\scripts\diagnose.ps1 -WriteReport
```

诊断脚本会检查：

- Python / pip / venv；
- 关键文件是否存在；
- `.env` 配置是否存在，并脱敏显示关键项；
- 端口占用；
- Ollama 状态；
- Docker 状态；
- 磁盘空间；
- `/health` 健康检查。

报告会生成在：

```text
logs/diagnose-YYYYMMDD-HHMMSS.txt
```

该报告可直接发给维护人员排查，敏感字段会被脱敏。

## 五、为什么新增本地启动器和图形向导

传统源码部署暴露了过多工程细节：

- 用户要自己创建虚拟环境；
- 自己安装依赖；
- 自己复制 `.env`；
- 自己用 `openssl rand` / Python `Fernet.generate_key()` 生成密钥；
- 自己判断 Ollama 是否启动；
- 自己处理端口占用；
- 自己看日志；
- 自己确认 `/health` 是否正常。

养老院试点场景不应把这些复杂度交给院方。新增 **双击 .bat + 弹窗向导** 的目标是把项目从"GitHub 代码仓库交付"推进到"本地应用化交付"：

> 像装一个普通应用一样：双击启动 → 弹窗填表 → 浏览器自动打开。
> 故障时能一键诊断，联网时再做更新和维护。

## 六、当前边界

本启动器不是完整商业安装包，目前还没有实现：

- ~~首次启动的图形化初始化向导~~ ✅ 已通过 `setup-wizard.ps1` 实现；
- ~~封装成 `.exe`~~ ✅ 已通过 `scripts/build-exe.ps1` 实现（PS2EXE 编译，保留 .bat 兜底）；
- Windows 安装向导（MSI / NSIS 安装包）；
- 桌面快捷方式自动创建；
- 后台服务注册（已有 `install-service.ps1` 走计划任务方案）；
- 自动升级；
- 升级失败回滚；
- 数据备份/恢复图形界面；
- 模型自动下载和校验。

这些应作为后续商业化交付阶段继续补齐。

## 七、打包成 .exe（交付给客户的正式形态）

`.bat` 是为了在没有任何依赖的 Windows 上"双击就能跑"。但商业交付时，黑色 cmd 窗口闪一下不像正式应用，因此项目内置了一键编译脚本，可以把两个 PowerShell 脚本编译成两个独立 `.exe`。

### 7.1 构建

在 Windows 项目根目录（已装 PowerShell 5.1+）执行：

```powershell
.\scripts\build-exe.ps1
```

首次运行会自动 `Install-Module ps2exe -Scope CurrentUser`，之后产出：

```
dist/
├── 智护银伴启动器.exe   (保留控制台，方便看进度)
├── 配置向导.exe         (纯 GUI，无黑框)
├── 启动智护银伴.bat     (兜底)
└── 配置向导.bat         (兜底)
```

可选参数：

```powershell
.\scripts\build-exe.ps1 -Version 1.0.1.0 -OutputDir D:\release
```

### 7.2 自定义图标

把 `.ico` 文件放到 `assets\logo.ico`，重新构建，exe 就会带上自定义图标。不放也能编译，只是用默认图标。

### 7.3 三种入口的对比

| 形态 | 双击启动 | 自定义图标 | 内嵌版本号/公司名 | 体积 | 适用场景 |
|---|---|---|---|---|---|
| `.ps1` | 否（被执行策略拦） | 否 | 否 | 几 KB | 开发者 |
| `.bat` | 是 | 否 | 否 | < 1 KB | 试点演示、兜底 |
| `.exe`（本节） | 是 | 是 | 是 | ~ 100 KB | **正式客户交付** |
| `Setup.exe`（WiX/Inno） | 是 + 安装到 Program Files | 是 | 是 | 几 MB | 大规模分发（后续） |

### 7.4 为什么 .bat 和 .exe 同时保留

- `.bat` 是**源码层**的双击入口，任何拿到代码仓库的人都能立刻跑；
- `.exe` 是**交付层**的双击入口，给到客户的是 `dist/` 里两个 .exe，他们看到的是带图标、带版本号的"正式应用"，不会感知到底下是 PowerShell。

### 7.5 后续可选增强

- **代码签名**：商业交付前对 .exe `signtool sign`，避免 Windows SmartScreen 首次运行拦截；
- **Inno Setup 打包**：把 dist 整个目录 + Python 嵌入式发行版 + Ollama 安装提示打成 `智护银伴-Setup-1.0.exe`，用户一路下一步即可；
- **Tauri 壳子**：把 Web UI 包成原生窗口，关掉浏览器地址栏，体验上彻底变成桌面应用。

## 八、建议后续产品化路线

1. ~~把 `.env` 配置变成图形化向导~~ ✅ 已完成（`setup-wizard.ps1`）；
2. ~~把 `启动智护银伴.bat` + `launch-local.ps1` 进一步打包成单文件 `智护银伴启动器.exe`~~ ✅ 已完成（`scripts/build-exe.ps1`）；
3. 用 Inno Setup / WiX 把 `dist/` 进一步打成 MSI/Setup.exe 安装包，自动建桌面快捷方式、写卸载入口；
4. 增加本地服务守护和自动重启；
5. 增加升级前自动备份；
6. 增加版本回滚；
7. 增加桌面端壳应用，例如 Tauri / Electron；
8. 增加云端轻管控：授权、模板、更新、远程维护。
