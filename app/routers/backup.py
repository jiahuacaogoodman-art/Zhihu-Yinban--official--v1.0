# -*- coding: utf-8 -*-
"""
@File    : app/routers/backup.py
@Desc    : 冷备份管理 API（admin 专用）

端点
  POST  /api/backup/run                  立即运行一次备份
  GET   /api/backup/list                 列出 target_dir 里所有备份文件
  GET   /api/backup/{filename}/verify    试解密 + 读取 manifest（不真的恢复）
  GET   /api/backup/status               调度器状态 + 上次报告

权限
  全部要求 PERM_USERS_MANAGE (实际上 = admin only)。备份文件含全部 PII，
  不能给护工 / 护士。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from app.middleware.auth import require_permission
from app.services.backup import (
    BACKUP_FILE_EXT,
    list_backups,
    verify_backup,
)
from app.services.backup_scheduler import get_scheduler
from app.services.hot_snapshot import get_snapshotter, SNAPSHOT_SUFFIX
from app.services.permissions import PERM_USERS_MANAGE
from app.services.user_store import User


router = APIRouter()


# ── response schemas ─────────────────────────────────────
class BackupRunResponse(BaseModel):
    code: int = 200
    message: str
    filename: str
    path: str
    size: int
    duration_seconds: float
    created_at: str
    sources: list[str]
    deleted_old: list[str] = Field(default_factory=list)


class BackupListItem(BaseModel):
    filename: str
    path: str
    size: int
    modified_at: str


class BackupListResponse(BaseModel):
    code: int = 200
    total: int
    target_dir: str
    backups: list[BackupListItem]


class BackupVerifyResponse(BaseModel):
    code: int = 200
    valid: bool
    filename: str
    manifest: dict | None = None
    error: str | None = None


class BackupStatusResponse(BaseModel):
    code: int = 200
    enabled: bool
    target_dir: str
    schedule: str
    last_report: dict | None = None
    last_error: str | None = None


# ── 端点 ───────────────────────────────────────────────────
@router.post("/backup/run", response_model=BackupRunResponse, summary="立即运行一次备份")
async def run_backup_now(
    user: User = Depends(require_permission(PERM_USERS_MANAGE)),
):
    scheduler = get_scheduler()
    if scheduler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="备份调度器未初始化（请检查 BACKUP_ENABLED 与 BACKUP_ENCRYPTION_KEY）",
        )
    try:
        report = await scheduler.trigger_now()
    except Exception as e:
        logger.exception(f"手动备份失败: {e}")
        raise HTTPException(status_code=500, detail=f"备份失败: {e}")
    logger.info(f"管理员触发备份: operator={user.username}, file={report.path.name}")
    d = report.to_dict()
    return BackupRunResponse(
        message=f"备份完成: {d['filename']}",
        filename=d["filename"],
        path=d["path"],
        size=d["size"],
        duration_seconds=d["duration_seconds"],
        created_at=d["created_at"],
        sources=d["sources"],
        deleted_old=d["deleted_old"],
    )


@router.get("/backup/list", response_model=BackupListResponse, summary="列出已生成的备份")
async def list_existing_backups(
    user: User = Depends(require_permission(PERM_USERS_MANAGE)),
):
    scheduler = get_scheduler()
    if scheduler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="备份调度器未初始化",
        )
    target = scheduler._opts.target_dir  # type: ignore[attr-defined]
    items = list_backups(target)
    return BackupListResponse(
        total=len(items),
        target_dir=str(target),
        backups=[BackupListItem(**i) for i in items],
    )


@router.get(
    "/backup/{filename}/verify",
    response_model=BackupVerifyResponse,
    summary="试解密 + 校验某份备份",
)
async def verify_existing_backup(
    filename: str,
    user: User = Depends(require_permission(PERM_USERS_MANAGE)),
):
    scheduler = get_scheduler()
    if scheduler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="备份调度器未初始化",
        )
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="非法文件名")
    if not filename.endswith(BACKUP_FILE_EXT):
        raise HTTPException(
            status_code=400,
            detail=f"备份文件后缀必须是 {BACKUP_FILE_EXT}",
        )

    target = scheduler._opts.target_dir          # type: ignore[attr-defined]
    key = scheduler._opts.encryption_key          # type: ignore[attr-defined]
    path = (Path(target) / filename).resolve()
    target_root = Path(target).resolve()
    # 防 path traversal: 必须是 target_dir 下的文件
    try:
        path.relative_to(target_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法路径")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"备份文件不存在: {filename}")

    try:
        manifest = verify_backup(path, key)
        return BackupVerifyResponse(
            valid=True, filename=filename, manifest=manifest,
        )
    except Exception as e:
        # 注意: cryptography.InvalidTag 的 str() 是空字符串。把异常类型也带上,
        # 方便管理员在 UI 上看到具体的失败原因。
        msg = str(e) or e.__class__.__name__
        logger.warning(f"备份校验失败 {filename}: {msg}")
        return BackupVerifyResponse(
            valid=False, filename=filename, manifest=None, error=msg,
        )


@router.get("/backup/status", response_model=BackupStatusResponse, summary="备份调度器状态")
async def backup_status(
    user: User = Depends(require_permission(PERM_USERS_MANAGE)),
):
    scheduler = get_scheduler()
    if scheduler is None:
        return BackupStatusResponse(
            enabled=False,
            target_dir="",
            schedule="(disabled - scheduler not initialized)",
        )
    opts = scheduler._opts                                 # type: ignore[attr-defined]
    last = scheduler.last_report.to_dict() if scheduler.last_report else None
    return BackupStatusResponse(
        enabled=opts.enabled,
        target_dir=str(opts.target_dir),
        schedule=f"daily at {opts.hour:02d}:{opts.minute:02d}",
        last_report=last,
        last_error=scheduler.last_error,
    )


# ============================================================
# 热快照（PR#5）—— 与冷备并列的、< 1 分钟 RPO 保护
# ============================================================
class HotSnapshotItem(BaseModel):
    source: str
    snapshot_path: str
    bytes: int
    duration_seconds: float
    pages_copied: int
    created_at: str


class HotSnapshotStatusResponse(BaseModel):
    code: int = 200
    enabled: bool
    snapshot_dir: str
    interval_seconds: int
    keep_per_source: int
    targets: list[str]
    last_reports: list[HotSnapshotItem]
    last_error: str | None = None


class HotSnapshotRunResponse(BaseModel):
    code: int = 200
    message: str
    snapshots: list[HotSnapshotItem]


@router.post(
    "/backup/hot/run",
    response_model=HotSnapshotRunResponse,
    summary="立即对所有受保护数据库做一次热快照",
)
async def hot_snapshot_run_now(
    user: User = Depends(require_permission(PERM_USERS_MANAGE)),
):
    snap = get_snapshotter()
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="热快照器未初始化（请检查 HOT_SNAPSHOT_ENABLED）",
        )
    try:
        reports = await snap.trigger_now()
    except Exception as e:
        logger.exception(f"热快照失败: {e}")
        raise HTTPException(status_code=500, detail=f"热快照失败: {e}")
    items = [HotSnapshotItem(**r.to_dict()) for r in reports]
    logger.info(
        f"管理员触发热快照: operator={user.username}, "
        f"成功 {len(items)} 个数据库"
    )
    return HotSnapshotRunResponse(
        message=f"已快照 {len(items)} 个数据库",
        snapshots=items,
    )


@router.get(
    "/backup/hot/status",
    response_model=HotSnapshotStatusResponse,
    summary="热快照器状态 + 各库最近一次快照报告",
)
async def hot_snapshot_status(
    user: User = Depends(require_permission(PERM_USERS_MANAGE)),
):
    snap = get_snapshotter()
    if snap is None:
        return HotSnapshotStatusResponse(
            enabled=False,
            snapshot_dir="",
            interval_seconds=0,
            keep_per_source=0,
            targets=[],
            last_reports=[],
        )
    opts = snap.options
    reports = [HotSnapshotItem(**r.to_dict()) for r in snap.all_reports()]
    return HotSnapshotStatusResponse(
        enabled=opts.enabled,
        snapshot_dir=str(opts.snapshot_dir),
        interval_seconds=opts.interval_seconds,
        keep_per_source=opts.keep_per_source,
        targets=[str(t) for t in opts.targets],
        last_reports=reports,
        last_error=snap.last_error,
    )
