# -*- coding: utf-8 -*-
"""
@Time    : 2026/03/08 10:00
@Author  : jiahuaCao
@File    : config.py
@Desc    : 全局配置文件：将所有硬编码的路径、模型名称、URL等集中管理
"""

import os
from pathlib import Path

# --- 基础路径定义 ---
# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- ChromaDB 配置 ---
# 本地持久化存储路径
CHROMA_DB_PATH = os.path.join(BASE_DIR, "local_ehr_db")
# 集合（Collection）名称
CHROMA_COLLECTION_NAME = "elderly_ehr"

# --- 病历照片与 OCR 档案配置 ---
# 原始病历照片、OCR 文本均保存在本地目录，不上传云端。
EHR_UPLOAD_DIR = os.path.join(BASE_DIR, "local_ehr_uploads")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
ALLOWED_UPLOAD_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# --- Embedding 模型配置 ---
# 使用轻量级、高效的中文向量模型，确保在无 GPU 环境下也能流畅运行
# 备选模型: 'shibing624/text2vec-base-chinese'
EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5")
# 建议在支持 CUDA 的环境中将设备设为 'cuda'
EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")
# 可选：指向本地已下载的模型目录，跳过网络下载
# 例如：/models/bge-small-zh-v1.5
EMBEDDING_MODEL_LOCAL_PATH: str = os.getenv("EMBEDDING_MODEL_LOCAL_PATH", "")
# 是否允许 embedding 加载失败时降级启动（RAG 功能不可用，但基础 LLM 仍可用）
# 设为 "true" / "1" / "yes" 允许降级；默认 "true" 允许降级启动
EMBEDDING_ALLOW_DEGRADED: bool = os.getenv(
    "EMBEDDING_ALLOW_DEGRADED", "true"
).strip().lower() in {"true", "1", "yes"}

# 完全禁用 embedding 模型加载（API-only 部署 / 无 GPU / 受限网络场景）
# 设为 true 时：
#   - 不会 import sentence_transformers / torch / transformers
#   - 启动时不下载也不加载任何 embedding 模型
#   - RAG 检索仍能跑，但向量函数退化成确定性哈希向量（仅用于 ChromaDB 写入约束，
#     不参与语义召回；新前端会按 patient_id 过滤已经够用，受限部署可以接受）
# 适用：requirements-api.txt 这类不装 torch 的轻量部署。
EMBEDDING_DISABLED: bool = os.getenv(
    "EMBEDDING_DISABLED", "false"
).strip().lower() in {"true", "1", "yes"}

# --- 大语言模型 (LLM) 配置 ---
# 项目支持两种 provider：
#   - "ollama"  本地 Ollama（默认，向后兼容）
#   - "openai"  任何 OpenAI 兼容协议端点（vLLM / TGI / SGLang / DeepSeek / 智谱 / Qwen 等）
# 切换不需要改代码，只需要改 .env：
#     LLM_PROVIDER=openai
#     OPENAI_API_BASE=http://gpu-host:8000/v1
#     OPENAI_MODEL=Qwen/Qwen2.5-7B-Instruct
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

# 全 provider 共用的请求超时（秒）。生成长任务卡建议 ≥ 180s。
LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "180"))

# --- Ollama provider 配置 ---
# Ollama 服务的 API 地址（支持通过环境变量指向远程 Ollama 实例）
OLLAMA_API_URL: str = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
# 本地运行的模型名称（可通过 .env 切换为 qwen2.5:3b 等替代模型）
OLLAMA_MODEL_NAME: str = os.getenv("OLLAMA_MODEL_NAME", "huatuo_o1_7b")

# --- OpenAI 兼容 provider 配置 ---
# OPENAI_API_BASE：兼容端点的根，**不要**带 /chat/completions 后缀。
#   vLLM:        http://gpu-host:8000/v1
#   TGI:         http://gpu-host:8080/v1
#   llama.cpp:   http://localhost:8080/v1
#   DeepSeek:    https://api.deepseek.com/v1
#   智谱:        https://open.bigmodel.cn/api/paas/v4
# OPENAI_API_KEY：可选；自建服务通常留空，云端 API 必填。
# OPENAI_MODEL：模型名，对应 vLLM 的 --served-model-name 或云端模型 ID。
OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "")

# --- 鉴权配置 ---
# AUTH_TOKEN：所有 /api/* 和 /uploads/* 请求必须携带请求头 X-Auth-Token: <token>。
# 生产部署时务必通过环境变量设置一个长随机字符串（推荐 32+ 字符）。
# 留空 / 不设置 → 鉴权关闭（仅供开发环境，生产环境禁止留空）。
AUTH_TOKEN: str = os.getenv("AUTH_TOKEN", "")

# --- 微信支付配置 ---
# 微信支付 V3 API 参数。全部留空时系统自动进入"模拟模式"（可正常测试流程但不会真正扣款）。
# 生产环境需到微信商户平台申请并填入以下参数。
WECHAT_PAY_MCH_ID: str = os.getenv("WECHAT_PAY_MCH_ID", "")            # 商户号
WECHAT_PAY_APP_ID: str = os.getenv("WECHAT_PAY_APP_ID", "")            # 公众号/小程序 AppID
WECHAT_PAY_API_KEY_V3: str = os.getenv("WECHAT_PAY_API_KEY_V3", "")    # APIv3 密钥（32字节）
WECHAT_PAY_SERIAL_NO: str = os.getenv("WECHAT_PAY_SERIAL_NO", "")      # 商户API证书序列号
WECHAT_PAY_PRIVATE_KEY_PATH: str = os.getenv("WECHAT_PAY_PRIVATE_KEY_PATH", "")  # 商户私钥文件路径
WECHAT_PAY_NOTIFY_URL: str = os.getenv("WECHAT_PAY_NOTIFY_URL", "")    # 支付回调通知地址

# --- PII 字段加密 ---
# 高敏感字段（id_card / emergency_phone 等）写入 ChromaDB 前 Fernet 对称加密。
# 留空 → 加密关闭（仅限开发/测试环境，生产必须设置）。
# 生成密钥：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
PII_ENCRYPTION_KEY: str = os.getenv("PII_ENCRYPTION_KEY", "")

# --- RAG Prompt 模板 ---
# 设计一个结构化的 Prompt，清晰地分离背景信息和当前问题，引导模型进行有效思考
RAG_PROMPT_TEMPLATE = (
    "你是一位经验丰富的智能护理助手，请严格根据以下信息进行分析和提供建议。\n"
    "--- 既往病史与用药记录 ---\n"
    "{retrieved_context}\n"
    "--------------------------\n"
    "--- 当前突发症状描述 ---\n"
    "{symptom}\n"
    "--------------------------\n"
    "任务要求：请综合上述所有信息，特别是患者的既往病史和过敏史，为护理人员提供一个安全、分步骤的初步处置建议。"
    "你的回答应清晰、严谨、可操作，并明确指出何时应立即联系医生。"
)
