# -*- coding: utf-8 -*-
"""
@File    : app/services/branching.py
@Desc    : Multi-tenant Schema preparation (branch_id + version_id)

PR#6 of the high-availability roadmap. Adds two columns to every business
table now, so future multi-院区 (branch) consolidation has a Schema base
without forcing a big-bang migration later.

Two columns:
  branch_id   TEXT NOT NULL DEFAULT 'main'
              Identifies which 院区 (branch / 加盟分店) the row belongs to.
              Single-院 deployments stay on 'main' forever; routers do
              NOT filter by branch_id yet (that lands in the multi-tenant
              router PR). The column is purely Schema preparation.

  version_id  INTEGER NOT NULL DEFAULT 1
              Optimistic-lock version. Every UPDATE will eventually be
              "WHERE version_id = ?  ... SET version_id = version_id + 1".
              Stays at 1 until the optimistic-lock middleware lands.
              Append-only / immutable tables skip this column - bumping
              a version on rows that are never updated is misleading.

Why this is its own module
  Six stores have nearly identical migration boilerplate. Centralizing
  here means one place to test idempotency, one place to fix the
  inevitable "ALTER TABLE ADD COLUMN doesn't support IF NOT EXISTS"
  papercut, and one place to bump defaults later.

Why we don't gate behind PRAGMA user_version here
  Each store has its own user_version counter (only care_store uses it
  today, and even there for migrations unrelated to branching). Adding
  cross-store coordination would be over-engineering for what is a
  single-shot, idempotent ALTER TABLE per column.

Idempotency guarantee
  ensure_branching_columns() can be called repeatedly. After the first
  call, subsequent calls do nothing - the column-existence probe via
  PRAGMA table_info short-circuits.
"""
from __future__ import annotations

import sqlite3
from typing import Iterable

from loguru import logger


BRANCH_ID_DEFAULT = "main"
INITIAL_VERSION = 1

# 列定义。集中放这里,以后调整默认值只改一处。
# NOT NULL DEFAULT 让 ALTER TABLE 给老行立即拿到合法值,不会触发约束错误。
_BRANCH_COLUMN_DECL = f"TEXT NOT NULL DEFAULT '{BRANCH_ID_DEFAULT}'"
_VERSION_COLUMN_DECL = f"INTEGER NOT NULL DEFAULT {INITIAL_VERSION}"


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """读 PRAGMA table_info 列表。表不存在时返回空 set。"""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] if isinstance(r, sqlite3.Row) else r[1] for r in rows}


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, decl: str,
) -> bool:
    """
    幂等加列。返回 True 表示真的新加了,False 表示列已存在。
    SQLite 的 ALTER TABLE ADD COLUMN 不支持 IF NOT EXISTS,只能先 PRAGMA 自检。
    """
    if column in _existing_columns(conn, table):
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    return True


def ensure_branching_columns(
    conn: sqlite3.Connection,
    *,
    full: Iterable[str],
    branch_only: Iterable[str] = (),
) -> dict[str, list[str]]:
    """
    给 SQLite 库里的指定表幂等地加 branch_id (+ version_id) 列 + 索引。

    Args:
      conn: 已打开的 SQLite 连接。事务由调用方控制——本函数不开 BEGIN。
            （store 已经把 _init_db 包在 connect() 的 autocommit 上下文里，
            ALTER TABLE 自身就是 DDL,在 SQLite 里隐式提交,不需要外面 BEGIN。）
      full: 需要 branch_id + version_id 两列的表名列表（mutable 业务实体）。
      branch_only: 只需要 branch_id 一列的表（append-only / 不可变事件流）。

    Returns:
      {
        "added_branch_id": [...],     # 真正新加了 branch_id 的表
        "added_version_id": [...],    # 真正新加了 version_id 的表
        "skipped_missing_table": [...]  # 表本身不存在(老库还没建到这张),被跳过
      }

    边界:
      · 同名列已存在时不重复加
      · 表不存在时只 log warning 后继续(让"新部署在第一次启动时还没建完表"
        这种竞态不阻塞 store 初始化)
      · 给每个加了 branch_id 的表创建 idx_<table>_branch 索引(IF NOT EXISTS)
        —— 索引在这里建而不是在 store 的 _CREATE_SQL 里建,是因为老库走
        CREATE TABLE IF NOT EXISTS 跳过新列,然后 CREATE INDEX 会立即报
        "no such column",必须先 ALTER TABLE ADD COLUMN 再建索引。
    """
    added_branch: list[str] = []
    added_version: list[str] = []
    skipped: list[str] = []

    full_list = list(full)
    branch_list = list(branch_only)

    # full 同时加两列
    for table in full_list:
        cols = _existing_columns(conn, table)
        if not cols:
            skipped.append(table)
            continue
        if _add_column_if_missing(conn, table, "branch_id", _BRANCH_COLUMN_DECL):
            added_branch.append(table)
        if _add_column_if_missing(conn, table, "version_id", _VERSION_COLUMN_DECL):
            added_version.append(table)

    # branch_only 只加 branch_id
    for table in branch_list:
        cols = _existing_columns(conn, table)
        if not cols:
            skipped.append(table)
            continue
        if _add_column_if_missing(conn, table, "branch_id", _BRANCH_COLUMN_DECL):
            added_branch.append(table)

    # ── branch_id 索引 ──
    # 列加好之后才能建索引。对全部 full + branch_only 表统一走一遍
    # IF NOT EXISTS,新库已经有索引就 no-op,老库刚加的列会拿到索引。
    for table in (*full_list, *branch_list):
        cols = _existing_columns(conn, table)
        if "branch_id" not in cols:
            # 表不存在 / 列加失败,跳过
            continue
        idx_name = f"idx_{table}_branch"
        try:
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}(branch_id)"
            )
        except sqlite3.OperationalError as e:
            logger.warning(f"branching: 创建索引 {idx_name} 失败: {e}")

    if added_branch or added_version:
        logger.info(
            f"branching: 添加 branch_id 到 {added_branch or '∅'}, "
            f"version_id 到 {added_version or '∅'}"
        )
    if skipped:
        logger.debug(f"branching: 跳过不存在的表 {skipped}")

    return {
        "added_branch_id": added_branch,
        "added_version_id": added_version,
        "skipped_missing_table": skipped,
    }


__all__ = [
    "BRANCH_ID_DEFAULT",
    "INITIAL_VERSION",
    "ensure_branching_columns",
]
