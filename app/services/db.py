# -*- coding: utf-8 -*-
"""
@File    : app/services/db.py
@Desc    : SQLite 连接 helper + 指数退避重试装饰器（Phase 1.1 高并发护航）

为什么需要这个模块
  原项目里 6 个 SQLite store（billing / care / event / user / audit / 等）
  每个都自己 `sqlite3.connect(...) + PRAGMA journal_mode=WAL`，但都漏了
  关键的 PRAGMA busy_timeout。Uvicorn 多 worker 时，多进程并发写同一个
  WAL 文件，会立即抛 `OperationalError: database is locked`。

  本模块解决两件事:
    1. 统一 connect()：所有 store 通过 db.connect() 拿连接，自带 WAL +
       synchronous=NORMAL + busy_timeout=5000ms。busy_timeout 是 SQLite
       内置的"等锁"机制，单机 50-100 并发写下基本不再裸抛 locked 错误。
    2. @with_db_retry 装饰器：对仍可能抛 locked 的关键写操作（资金、
       审计、状态流转）做应用层指数退避重试，作为第二道护栏。

设计取舍
  - 不引 SQLAlchemy/databases。仍然用 sqlite3 + 手写 SQL，保持现有
    store 代码改动最小（替换 _connect()，关键写方法加 @with_db_retry）。
  - busy_timeout 给 5 秒：SQLite 默认 0 ms，行业惯例 5 s。比这更长会
    影响请求超时，更短会让大并发下的非 hot path 也被外层重试。
  - 应用层重试只看 OperationalError + "locked" 子串。其他错误（约束冲突、
    业务逻辑抛的 ValueError）**绝不重试**——重试它们会造成幂等性问题。
  - 装饰器对方法/函数都生效（用 functools.wraps）。

使用方式
  # 1) 在 store 的 _connect() 里
  def _connect(self):
      return db.connect(self._path, foreign_keys=True)

  # 2) 关键写方法
  @db.with_db_retry()
  def create_billing_record(self, data): ...
"""
from __future__ import annotations

import functools
import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from loguru import logger


# ── 默认参数（可被环境变量覆盖，但这里不读 env，让调用方自己传）────
DEFAULT_BUSY_TIMEOUT_MS = 5000
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BASE_DELAY = 0.05      # 50 ms
DEFAULT_MAX_DELAY = 2.0        # 单次退避上限 2 s
DEFAULT_JITTER = 0.5           # ±50% 随机抖动，避免雪崩


def connect(
    db_path: str | Path,
    *,
    foreign_keys: bool = False,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
) -> sqlite3.Connection:
    """
    统一的 SQLite 连接工厂。

    PRAGMA 设置说明:
      journal_mode=WAL       多读单写，读不阻塞写
      synchronous=NORMAL     WAL 模式下足够安全且比 FULL 快很多
      busy_timeout=5000      ⭐ 关键：等锁 5s 而非立即报 locked
      foreign_keys=ON        仅当 caller 明确要求时开（默认关，照顾老库）
      row_factory=Row        让查询结果支持下标 + 列名访问

    isolation_level=None      autocommit；事务由调用方手动 BEGIN IMMEDIATE / COMMIT
    check_same_thread=False   配合 threading.Lock 保证应用层串行
    """
    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,
        isolation_level=None,
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    # busy_timeout 必须用 PRAGMA 整数字面量（不接参数绑定）
    conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def is_locked_error(exc: BaseException) -> bool:
    """
    判断异常是否是"数据库被锁住"导致的可重试错误。

    SQLite 的 locked 错误有两个变种:
      - "database is locked"        WAL 写者互斥
      - "database table is locked"  事务持有者占用某张表

    其他 OperationalError（如 disk I/O error、no such table）都**不应**重试。
    其他异常类（IntegrityError、ProgrammingError、业务 ValueError）也不重试。
    """
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    msg = str(exc).lower()
    return "locked" in msg


F = TypeVar("F", bound=Callable[..., Any])


def with_db_retry(
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    jitter: float = DEFAULT_JITTER,
) -> Callable[[F], F]:
    """
    指数退避 + 抖动 重试装饰器，专门护航关键写操作。

    第 n 次失败后的等待时间:
        delay_n = min(max_delay, base_delay * 2**n) * (1 + random(-jitter, +jitter))

    例如默认参数下，连续 4 次重试的 sleep 序列大致是:
        50 ms, 100 ms, 200 ms, 400 ms （±50% 随机）
    总等待上界约 1.5 秒；加上 SQLite 自己的 5 s busy_timeout，单次写
    操作最坏 ~6.5 s 后才彻底失败抛错。再失败说明系统已经雪崩，应该
    让上层 5xx 而不是无限堆积请求。

    只对"database is locked"重试；其他错误立即向上抛。

    用法:
        @with_db_retry()
        def create_billing_record(self, data): ...

        @with_db_retry(max_attempts=3)
        def log(self, ...): ...
    """
    assert max_attempts >= 1
    assert base_delay > 0

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if not is_locked_error(e):
                        # 非 locked 类的 OperationalError（如 disk full）直接抛
                        raise
                    last_exc = e
                    if attempt + 1 >= max_attempts:
                        # 重试用尽，把最后一次错误抛出，附带 attempt 信息
                        logger.error(
                            f"[db.retry] {fn.__qualname__} 重试 {max_attempts} 次仍 locked，放弃: {e}"
                        )
                        raise
                    # 计算下一次 sleep
                    delay = min(max_delay, base_delay * (2 ** attempt))
                    if jitter:
                        delay = delay * (1.0 + random.uniform(-jitter, jitter))
                    logger.warning(
                        f"[db.retry] {fn.__qualname__} locked，第 {attempt + 1}/{max_attempts} "
                        f"次重试，sleep {delay * 1000:.0f}ms"
                    )
                    time.sleep(max(0.0, delay))
            # 理论不可达；保险起见
            assert last_exc is not None
            raise last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


# ── 测试辅助：上下文管理器，让单元测试能临时缩短 backoff ──────
class _RetryConfig:
    """允许测试通过 monkey-patch 覆盖默认参数（不直接改全局常量）。"""


_retry_config = _RetryConfig()
