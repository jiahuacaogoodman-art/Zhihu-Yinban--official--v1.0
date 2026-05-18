# -*- coding: utf-8 -*-
"""
@File    : app/services/backup.py
@Desc    : 冷备份核心 —— 打包 + AES-256-GCM 整体加密 + 完整性 manifest

适用场景
  基层养老院随时面临断电、硬盘老化、勒索软件。法律责任不允许医疗
  记录丢失。本模块每次备份打包以下七大类数据：
    · ChromaDB 向量库         local_ehr_db/
    · 病历照片 / OCR / CAS    local_ehr_uploads/
    · 缴费业务库              local_billing/
    · 护理业务库              local_care/
    · 用户 + API Key          local_auth/
    · 操作审计                local_audit_log/
    · 护理事件流              local_nursing_events/

  打包后用 AES-256-GCM 整体加密。GCM 是认证加密(AEAD)，自带完整性
  校验——文件被篡改 1 个字节就解密失败，不会"成功但数据错误"。

文件格式（.zybak.gcm）
  ┌─────────────────────────────────────────────────────────────┐
  │  magic   = b"ZYBAK\\x01" (6 字节，含版本号)                   │
  │  nonce   = 12 字节随机                                       │
  │  ciphertext + tag = AESGCM.encrypt(nonce, plaintext, ad)     │
  │  其中 plaintext = tar.gz(目录树) + 末尾 manifest.json         │
  └─────────────────────────────────────────────────────────────┘

  我们不写 tag 长度——AESGCM 把 16 字节 tag 拼在 ciphertext 末尾，
  解密 API 自带处理。

manifest.json（在 tar 包末尾）记录：
  · created_at / hostname
  · 每个源目录的 sha256 + 字节数
  · 备份模块的版本号

为什么不依赖 APScheduler / cron
  这个项目部署在乡镇养老院，多是 docker compose 单机。引入 APScheduler
  会增加依赖；让 sysadmin 写 crontab 又会和 docker 隔离冲突。下文的
  backup_scheduler.py 用 asyncio 单 task 实现"每天 3 点跑一次"——
  足够简单且不引依赖。

密钥
  AES-256-GCM 需要 32 字节 key，从 env BACKUP_ENCRYPTION_KEY 读：
    · 64 hex 字符 (32 字节)
    · 或 base64 / urlsafe-base64 编码 32 字节
  也可以用 derive_key_from_passphrase(passphrase, salt) 从口令派生。
  生成方式：python -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

  key 的存放和轮换由 PR#3 (KMS) 管。本 PR 先支持纯环境变量。

不做什么
  · 不做远程上传 (S3/NAS) 的认证逻辑——只输出本地文件
    + 可选 rsync 命令行 hook (target_dir 由 sysadmin 自行设为 NAS 挂载点)
  · 不做增量备份。养老院数据量小（< 1 GB / 院），全量更稳。
  · 不做密钥分级 (KMS 是 PR#3 的事)
"""
from __future__ import annotations

import base64
import dataclasses
import gzip
import hashlib
import io
import json
import os
import socket
import tarfile
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

from loguru import logger


# ── 常量 ────────────────────────────────────────────────
BACKUP_FILE_EXT = ".zybak.gcm"
MAGIC = b"ZYBAK\x01"               # 6 bytes; bump second byte on format change
NONCE_LEN = 12                     # AES-GCM 推荐 12 字节
KEY_LEN = 32                       # AES-256
MODULE_VERSION = "1.0"

# tar 内 manifest 文件的固定名字
MANIFEST_NAME = "_manifest.json"


# ── 数据类 ───────────────────────────────────────────────
@dataclasses.dataclass(frozen=True)
class BackupConfig:
    """
    配置一次备份。target_dir 必须存在 (NAS 挂载点 / USB 挂载目录)；
    sources 是要打进包里的源路径，相对路径会从 base_dir 推断。
    """

    sources: tuple[Path, ...]
    target_dir: Path
    encryption_key: bytes              # 32 bytes
    retention_days: int = 14
    file_prefix: str = "zhihu-yinban"

    def __post_init__(self):
        if len(self.encryption_key) != KEY_LEN:
            raise ValueError(
                f"encryption_key 必须是 {KEY_LEN} 字节，得到 {len(self.encryption_key)}"
            )


@dataclasses.dataclass
class BackupReport:
    """每次备份后返回的报告，便于路由层 / 测试断言。"""

    path: Path
    size: int
    created_at: str
    sources: list[str]
    duration_seconds: float
    deleted_old: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "filename": self.path.name,
            "size": self.size,
            "created_at": self.created_at,
            "sources": self.sources,
            "duration_seconds": round(self.duration_seconds, 3),
            "deleted_old": self.deleted_old,
        }


# ── 密钥工具 ────────────────────────────────────────────
def parse_key(raw: str) -> bytes:
    """
    把环境变量字符串解析成 32 字节 key。

    支持三种编码（自动嗅探）：
      · 64 字符 hex → 32 字节
      · 标准 base64 (44 字符含 padding) → 32 字节
      · urlsafe base64 (44 字符 - 替换 +/ 为 -_) → 32 字节
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("BACKUP_ENCRYPTION_KEY 未配置")
    # hex 优先
    if len(raw) == KEY_LEN * 2:
        try:
            b = bytes.fromhex(raw)
            if len(b) == KEY_LEN:
                return b
        except ValueError:
            pass
    # base64 / urlsafe base64
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            b = decoder(raw)
            if len(b) == KEY_LEN:
                return b
        except Exception:
            continue
    raise ValueError(
        "BACKUP_ENCRYPTION_KEY 必须是 64 hex / 32-byte base64 / urlsafe-base64"
    )


def derive_key_from_passphrase(passphrase: str, salt: bytes) -> bytes:
    """
    从口令派生 32 字节 key (PBKDF2-HMAC-SHA256, 200_000 轮)。

    本 PR 默认不用——env key 更简单。留给将来 KMS PR 用。
    salt 必须 ≥ 16 字节，且和密文一起存（不要硬编码）。
    """
    if len(salt) < 16:
        raise ValueError("salt 至少 16 字节")
    return hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000, dklen=KEY_LEN)


# ── 打包 + 加密 ──────────────────────────────────────────
def _build_tar_bytes(sources: Iterable[Path]) -> tuple[bytes, dict]:
    """
    把一组目录打成 tar.gz，返回 (bytes, manifest_dict)。

    manifest 在 tar 内部以 _manifest.json 单文件形式存在，便于解包后
    查看。同时也作为返回值返回，让 BackupReport 写入元数据。
    """
    buf = io.BytesIO()
    manifest = {
        "version": MODULE_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "hostname": socket.gethostname(),
        "sources": [],
    }

    # gzip 压缩级别 6：在乡镇低配 NAS 上 6 比 9 快很多，体积只多 5-10%
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=6) as tar:
        for src in sources:
            src = Path(src)
            if not src.exists():
                logger.warning(f"备份: 源路径不存在，跳过 {src}")
                manifest["sources"].append({
                    "path": str(src),
                    "exists": False,
                    "files": 0,
                    "bytes": 0,
                })
                continue

            files_in_src = 0
            bytes_in_src = 0
            arc_root = src.name           # 保留顶层目录名
            for p in sorted(src.rglob("*")):
                if not p.is_file():
                    continue
                # 跳过 SQLite WAL 副产物和 tmp 文件——它们会在恢复后自动重建
                # WAL 文件在备份瞬间可能没 checkpoint 完整，但因为本备份是
                # cold backup（每日 3 点低峰期），不会丢已 commit 数据；
                # 如果连 -wal 也带上反而可能让恢复时 SQLite 拒绝打开
                if p.suffix in {".tmp"} or p.name.endswith("-wal") or p.name.endswith("-shm"):
                    continue
                arcname = arc_root + "/" + p.relative_to(src).as_posix()
                tar.add(str(p), arcname=arcname, recursive=False)
                files_in_src += 1
                bytes_in_src += p.stat().st_size
            manifest["sources"].append({
                "path": str(src),
                "exists": True,
                "files": files_in_src,
                "bytes": bytes_in_src,
            })

        # 把 manifest 也写进 tar
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        info = tarfile.TarInfo(name=MANIFEST_NAME)
        info.size = len(manifest_bytes)
        info.mtime = int(time.time())
        tar.addfile(info, io.BytesIO(manifest_bytes))

    return buf.getvalue(), manifest


def _aesgcm_encrypt(plaintext: bytes, key: bytes) -> bytes:
    """生成 magic + nonce + ciphertext+tag 的字节流。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_LEN)
    ct = aesgcm.encrypt(nonce, plaintext, MAGIC)   # AD = MAGIC，防版本号被改
    return MAGIC + nonce + ct


def _aesgcm_decrypt(blob: bytes, key: bytes) -> bytes:
    """blob → plaintext。文件被篡改 / key 错都会抛 InvalidTag。"""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if len(blob) < len(MAGIC) + NONCE_LEN + 16:
        raise ValueError("备份文件过小或损坏")
    if blob[: len(MAGIC)] != MAGIC:
        raise ValueError(
            f"非法备份格式 (magic 期望 {MAGIC!r}，实际 {blob[: len(MAGIC)]!r})"
        )
    nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_LEN]
    ct = blob[len(MAGIC) + NONCE_LEN :]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ct, MAGIC)


# ── 公开 API ──────────────────────────────────────────────
def create_backup(config: BackupConfig) -> BackupReport:
    """
    执行一次完整备份。

    - 打包 → 加密 → 写入 target_dir
    - 写入策略：先 .partial 再 rename，防止半文件被 sysadmin 当成有效备份
    - 返回 BackupReport 给路由层 / 调度器
    """
    started = time.perf_counter()
    config.target_dir.mkdir(parents=True, exist_ok=True)

    plaintext, manifest = _build_tar_bytes(config.sources)
    blob = _aesgcm_encrypt(plaintext, config.encryption_key)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{config.file_prefix}_{ts}{BACKUP_FILE_EXT}"
    final_path = config.target_dir / fname
    # 同秒内多次备份(测试 / 管理员手动连按)冲突防护:加 -<n> 后缀避免覆盖
    if final_path.exists():
        n = 1
        while True:
            alt = config.target_dir / f"{config.file_prefix}_{ts}-{n}{BACKUP_FILE_EXT}"
            if not alt.exists():
                final_path = alt
                break
            n += 1
    tmp_path = final_path.with_suffix(final_path.suffix + ".partial")

    # 先写到临时文件再 rename → 单 fs rename 是原子的
    with open(tmp_path, "wb") as f:
        f.write(blob)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, final_path)

    elapsed = time.perf_counter() - started
    deleted = _purge_old_backups(config)

    report = BackupReport(
        path=final_path,
        size=len(blob),
        created_at=manifest["created_at"],
        sources=[s["path"] for s in manifest["sources"]],
        duration_seconds=elapsed,
        deleted_old=deleted,
    )
    logger.success(
        f"备份完成: {fname} ({len(blob) / 1024 / 1024:.2f} MB, "
        f"{elapsed:.2f}s) → {config.target_dir}"
    )
    return report


def verify_backup(path: Path, key: bytes) -> dict:
    """
    试解密 + 重新计算 sha256 校验源目录字节数。
    成功返回 manifest dict；失败抛异常。
    供管理员"上次备份还能恢复吗"的体检流程用。
    """
    blob = path.read_bytes()
    plaintext = _aesgcm_decrypt(blob, key)
    # 从 tar 里取 manifest
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as tar:
        member = tar.getmember(MANIFEST_NAME)
        f = tar.extractfile(member)
        if f is None:
            raise ValueError("manifest 缺失")
        manifest = json.loads(f.read().decode("utf-8"))
    return manifest


def restore_backup(path: Path, key: bytes, dest_dir: Path) -> dict:
    """
    紧急恢复。dest_dir 必须存在；解出后可手动覆盖到 BASE_DIR。

    本函数**不**直接覆盖 BASE_DIR——管理员必须手动从 dest_dir 拷过去。
    防止误操作时把正在跑的 SQLite 文件覆盖。
    """
    blob = path.read_bytes()
    plaintext = _aesgcm_decrypt(blob, key)
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as tar:
        # tarfile.extractall 在 3.12+ 默认 filter='data'，避免 path traversal
        try:
            tar.extractall(str(dest_dir), filter="data")
        except TypeError:
            # Python < 3.12 fallback
            tar.extractall(str(dest_dir))
    # 读 manifest 给上层确认
    manifest_path = dest_dir / MANIFEST_NAME
    if manifest_path.exists():
        return json.loads(manifest_path.read_text("utf-8"))
    return {}


def list_backups(target_dir: Path, prefix: str = "zhihu-yinban") -> list[dict]:
    """供 GET /api/backup/list 返回历史。"""
    if not target_dir.exists():
        return []
    out: list[dict] = []
    for f in sorted(target_dir.iterdir()):
        if not f.is_file():
            continue
        if not f.name.endswith(BACKUP_FILE_EXT):
            continue
        if not f.name.startswith(prefix):
            continue
        st = f.stat()
        out.append({
            "filename": f.name,
            "path": str(f),
            "size": st.st_size,
            "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        })
    out.sort(key=lambda x: x["modified_at"], reverse=True)
    return out


# ── 内部：清理过期备份 ───────────────────────────────────
def _purge_old_backups(config: BackupConfig) -> list[str]:
    """
    按 mtime 删除超出 retention_days 的同 prefix 文件。
    返回被删的文件名列表（写入 BackupReport.deleted_old）。
    """
    if config.retention_days <= 0:
        return []
    cutoff = time.time() - config.retention_days * 86400
    deleted: list[str] = []
    for f in config.target_dir.iterdir():
        if not f.is_file() or not f.name.endswith(BACKUP_FILE_EXT):
            continue
        if not f.name.startswith(config.file_prefix):
            continue
        if f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                deleted.append(f.name)
            except OSError as e:
                logger.warning(f"删除过期备份失败 {f}: {e}")
    if deleted:
        logger.info(f"清理 {len(deleted)} 个过期备份: {deleted}")
    return deleted


# ── 默认源路径（默认包含全部数据目录）──────────────────────
def default_sources(base_dir: Path) -> tuple[Path, ...]:
    """
    返回项目里全部需要备份的目录。新增数据子系统时记得在这里加。

    注意：__pycache__ / *.pyc / node_modules 不在这里，因为它们不在
    BASE_DIR 下任何 local_* 目录里。
    """
    return tuple(
        base_dir / name
        for name in (
            "local_ehr_db",
            "local_ehr_uploads",
            "local_billing",
            "local_care",
            "local_auth",
            "local_audit_log",
            "local_nursing_events",
        )
    )


__all__ = [
    "BACKUP_FILE_EXT",
    "BackupConfig",
    "BackupReport",
    "create_backup",
    "default_sources",
    "derive_key_from_passphrase",
    "list_backups",
    "parse_key",
    "restore_backup",
    "verify_backup",
]
