# -*- coding: utf-8 -*-
"""
@File    : app/services/file_store.py
@Desc    : 内容寻址 (Content-Addressable) 文件存储

为什么要这层
  原 OCR 上传直接 `open(path, "wb").write(content)` 落到 local_ehr_uploads/<pid>/photos/
  虽然用 uuid 防了同名覆盖，但有 3 个隐患：
    1) 没有完整性校验。冷备恢复后无法判断文件是否在传输过程中损坏。
    2) 同一份病历照片被两个老人上传 = 两份磁盘副本，浪费空间。
    3) 文件名一旦改、目录结构一旦换，所有老 metadata 里的 file_path 全失效。

  本模块提供 CAS（Content-Addressable Storage）布局：
    local_ehr_uploads/sha/<aa>/<bb>/<full_sha>.<ext>
                          ↑↑   ↑↑
                          头2位 第3-4位（避免单目录爆量，~ 65k 桶上限）

  关键性质：
    · 文件名 = 内容 sha256 → 同内容只存一份（自动 dedup）
    · 写入是原子的（先写 .tmp 再 rename）
    · put() 返回 (sha256, path)，调用方把 sha 存进 metadata，
      未来恢复 / 同步只需校验 sha 即可证明完整性
    · ext 单独保留，让 StaticFiles 还能根据扩展名设 content-type

后向兼容
  · 老的 <pid>/photos/<doc_id>.<ext> 物理文件不动；新上传走 CAS 路径
  · ehr.py 同时把 sha256 存进 metadata，老记录没有这个字段，UI 不展示也不算错
  · 相对 file_url 仍然走 /uploads/，只是物理 path 形态不同：
      /uploads/sha/aa/bb/<sha>.jpg
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


# ── 常量 ──────────────────────────────────────────────
_SHA_PREFIX = "sha"
_BUCKET_DEPTH = 2          # 用 sha 头 2 字节作为一级桶，第 3-4 字节作为二级桶
_BUCKET_LEN = 2            # 每级桶 2 个 hex 字符 → 256 个桶 / 级


@dataclass(frozen=True)
class StoredFile:
    """put() 的返回值。所有调用方都应保存 sha256 以便后续校验。"""

    sha256: str
    path: Path           # 绝对路径（/app/local_ehr_uploads/sha/aa/bb/xxx.jpg）
    rel_url: str         # 相对 /uploads 的 URL（/uploads/sha/aa/bb/xxx.jpg）
    size: int
    deduped: bool        # True = 同 sha 文件已存在，本次未实际写盘


class FileStore:
    """
    CAS 文件仓。所有方法都是同步的；上层 async 路由用 asyncio.to_thread
    把 put() 丢到线程池跑（写大文件 + sha256 计算约 10-50 ms / 1 MB）。
    """

    def __init__(self, root: str | Path, *, url_prefix: str = "/uploads"):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        # 提前建好 sha 顶层目录，避免每次 put() 多 1 次 mkdir 系统调用
        (self._root / _SHA_PREFIX).mkdir(parents=True, exist_ok=True)
        self._url_prefix = url_prefix.rstrip("/")

    # ── 内部工具 ──────────────────────────────────────
    @staticmethod
    def _bucket_for(sha: str) -> tuple[str, str]:
        """sha → (一级桶, 二级桶)，每级 2 个 hex 字符。"""
        if len(sha) < _BUCKET_DEPTH * _BUCKET_LEN:
            raise ValueError(f"sha 太短: {sha}")
        return sha[:_BUCKET_LEN], sha[_BUCKET_LEN:_BUCKET_LEN * 2]

    def _path_for(self, sha: str, ext: str) -> Path:
        a, b = self._bucket_for(sha)
        ext = ext.lower()
        if ext and not ext.startswith("."):
            ext = "." + ext
        return self._root / _SHA_PREFIX / a / b / f"{sha}{ext}"

    def _rel_url_for(self, abs_path: Path) -> str:
        rel = abs_path.relative_to(self._root).as_posix()
        return f"{self._url_prefix}/{rel}"

    # ── 公开 API ──────────────────────────────────────
    def put(self, content: bytes, *, suffix: str = "") -> StoredFile:
        """
        把 bytes 写入 CAS 仓。如果同 sha 文件已存在，直接复用。

        suffix 是包含点的扩展名（"jpg" / ".jpg" / 空都接受），用来保留
        StaticFiles 的 content-type 嗅探能力。

        原子性：
          先写 <abs_path>.<random>.tmp，再 os.replace 到目标路径。
          多个 worker 同时写同一份内容时，最后一个 replace 胜出，但
          因为内容字节一致，结果相同——这是 CAS 的天然性质。
        """
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError("content 必须是 bytes")
        sha = hashlib.sha256(content).hexdigest()
        abs_path = self._path_for(sha, suffix)

        # dedup 检查
        if abs_path.exists() and abs_path.stat().st_size == len(content):
            logger.debug(f"FileStore.put: dedup hit sha={sha[:12]}… size={len(content)}")
            return StoredFile(
                sha256=sha,
                path=abs_path,
                rel_url=self._rel_url_for(abs_path),
                size=len(content),
                deduped=True,
            )

        abs_path.parent.mkdir(parents=True, exist_ok=True)
        # 用 NamedTemporaryFile 在同目录下生成 tmp，确保 replace 是同 fs
        # （跨设备 rename 会失败）
        fd, tmp_str = tempfile.mkstemp(
            prefix=abs_path.name + ".",
            suffix=".tmp",
            dir=str(abs_path.parent),
        )
        tmp_path = Path(tmp_str)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
                f.flush()
                # fsync 给硬盘老化场景多一层保险（cron 备份不会被半写文件污染）
                os.fsync(f.fileno())
            os.replace(tmp_path, abs_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        logger.debug(f"FileStore.put: wrote sha={sha[:12]}… size={len(content)} → {abs_path}")
        return StoredFile(
            sha256=sha,
            path=abs_path,
            rel_url=self._rel_url_for(abs_path),
            size=len(content),
            deduped=False,
        )

    def get(self, sha: str, suffix: str = "") -> Path | None:
        """根据 sha 查找文件路径；不存在返回 None。"""
        path = self._path_for(sha, suffix)
        return path if path.exists() else None

    def verify(self, sha: str, suffix: str = "") -> bool:
        """
        重新读取文件并校验 sha256，用于备份恢复后做体检。
        sha 不匹配 = 文件已损坏。
        """
        path = self._path_for(sha, suffix)
        if not path.exists():
            return False
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest() == sha

    def delete(self, sha: str, suffix: str = "") -> bool:
        """
        从 CAS 删除文件。**调用方必须确保没有别的引用**——CAS 不维护
        引用计数，删错文件会让所有引用同 sha 的记录全部失效。

        本项目的策略：物理文件只在该 sha 不再被任何 EHR 记录引用时才删
        （由 ehr.py 的删除流程负责判断）。这里只是底层操作。
        """
        path = self._path_for(sha, suffix)
        if not path.exists():
            return False
        path.unlink()
        # 桶为空时顺便清理空目录，避免 .git / rsync 看到一堆空 aa/bb/
        try:
            path.parent.rmdir()
            path.parent.parent.rmdir()
        except OSError:
            pass
        return True

    def stats(self) -> dict:
        """返回仓库的体积 / 文件数，给监控面板和备份脚本用。"""
        sha_root = self._root / _SHA_PREFIX
        total_files = 0
        total_bytes = 0
        for p in sha_root.rglob("*"):
            if p.is_file() and not p.name.endswith(".tmp"):
                total_files += 1
                total_bytes += p.stat().st_size
        return {
            "root": str(self._root),
            "files": total_files,
            "bytes": total_bytes,
        }


# ── 全局 singleton（与 audit_log / billing_store 风格一致） ──
_file_store: FileStore | None = None
_file_store_path: Path | None = None


def get_file_store(root: str | Path | None = None) -> FileStore:
    """
    获取全局 FileStore 实例（首次调用时初始化）。

    root 默认按 EHR_UPLOAD_DIR 配置；测试可以传 tmp_path。
    """
    global _file_store, _file_store_path
    if _file_store is not None and (root is None or Path(root) == _file_store_path):
        return _file_store
    if root is None:
        from app.core.config import EHR_UPLOAD_DIR
        root = EHR_UPLOAD_DIR
    _file_store_path = Path(root)
    _file_store = FileStore(_file_store_path)
    return _file_store


def reset_file_store() -> None:
    """仅测试用：清空 singleton 引用。"""
    global _file_store, _file_store_path
    _file_store = None
    _file_store_path = None


__all__ = [
    "FileStore",
    "StoredFile",
    "get_file_store",
    "reset_file_store",
]
