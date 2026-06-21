#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared TRC20-USDT scanner for multi-bot deployments."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from typing import Any

from usdt_trc20 import (
    ensure_usdt_chain_tables,
    purge_old_chain_transactions,
    scan_chain_to_store,
)


BASE_DIR = os.path.dirname(__file__)
CFG_PATH = os.environ.get("CONFIG_PATH", os.path.join(BASE_DIR, "config.json"))


def strip_json_comments(text: str) -> str:
    """Remove simple JSON comments to keep compatibility with bot.py config."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = []
    for line in text.splitlines():
        in_str = False
        esc = False
        buf = []
        for idx, ch in enumerate(line):
            if ch == '"' and not esc:
                in_str = not in_str
            if not in_str and idx + 1 < len(line) and ch == "/" and line[idx + 1] == "/":
                break
            buf.append(ch)
            esc = ch == "\\" and not esc
            if ch != "\\":
                esc = False
        lines.append("".join(buf).rstrip())
    return "\n".join(lines)


def load_config() -> dict[str, Any]:
    """Load scanner configuration from config.json."""
    with open(CFG_PATH, "r", encoding="utf-8") as file:
        return json.loads(strip_json_comments(file.read()))


def open_shared_store(path: str):
    """Open and initialize the shared SQLite transaction store."""
    if not path:
        raise RuntimeError("USDT_SCAN.shared_store 未配置")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA busy_timeout=5000;")
    ensure_usdt_chain_tables(cur, conn)
    return conn, cur


def get_setting(cur, key: str, default: str = "") -> str:
    """Read a setting from the shared scanner database."""
    row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row and row[0] is not None else default


def set_setting(cur, conn, key: str, value: str) -> None:
    """Write a setting into the shared scanner database."""
    cur.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def build_scan_config(config: dict[str, Any], key_index: int = 0) -> dict[str, Any]:
    """Merge legacy payment config and the new USDT_SCAN section."""
    payment_cfg = (config.get("PAYMENTS") or {}).get("usdt_trc20_direct", {})
    scan_cfg = config.get("USDT_SCAN") or {}
    merged = {**payment_cfg, **scan_cfg}
    merged["enabled"] = True
    merged["_api_key_index"] = key_index
    if "tron_api_keys" not in merged and payment_cfg.get("tron_api_key"):
        merged["tron_api_keys"] = [payment_cfg.get("tron_api_key")]
    return merged


def is_rate_limited(exc: Exception) -> bool:
    """Detect TronGrid 429 errors without depending on requests internals."""
    text = str(exc)
    return "429" in text or "Too Many Requests" in text


def _warn_retention_vs_timeout(config: dict[str, Any], retention_hours: int) -> None:
    """Log when retention is shorter than order timeout plus buffer."""
    payment_cfg = (config.get("PAYMENTS") or {}).get("usdt_trc20_direct", {}) or {}
    try:
        timeout_seconds = int(payment_cfg.get("timeout_seconds", 3600) or 3600)
    except Exception:
        timeout_seconds = 3600
    min_hours = (timeout_seconds + 21600) // 3600
    if retention_hours > 0 and retention_hours * 3600 < timeout_seconds + 21600:
        print(
            f"⚠️ USDT扫链保留期偏短: retention_hours={retention_hours}, "
            f"建议 >= {min_hours}（timeout={timeout_seconds}s + 6h 缓冲）"
        )


def _maybe_purge_chain_store(
    cur,
    conn,
    scan_cfg: dict[str, Any],
    last_cleanup_ts: float,
) -> float:
    """Run retention cleanup when cleanup_interval_hours has elapsed."""
    retention_hours = int(scan_cfg.get("retention_hours", 24) or 0)
    if retention_hours <= 0:
        return last_cleanup_ts

    cleanup_interval_hours = max(
        1,
        int(scan_cfg.get("cleanup_interval_hours", 24) or 24),
    )
    now = time.time()
    if now - last_cleanup_ts < cleanup_interval_hours * 3600:
        return last_cleanup_ts

    vacuum = bool(scan_cfg.get("vacuum_after_cleanup", True))
    try:
        vacuum_min_deleted = int(scan_cfg.get("vacuum_min_deleted", 1000) or 1000)
    except Exception:
        vacuum_min_deleted = 1000

    try:
        deleted = purge_old_chain_transactions(
            cur,
            conn,
            retention_hours=retention_hours,
            vacuum=vacuum,
            vacuum_min_deleted=vacuum_min_deleted,
        )
        if deleted:
            print(
                f"✅ USDT扫链清理: deleted={deleted}, "
                f"retention_hours={retention_hours}"
            )
    except Exception as exc:
        print(f"⚠️ USDT扫链清理失败: {exc}")

    return now


def run_forever() -> None:
    """Run the shared scanner loop."""
    config = load_config()
    scan_cfg = config.get("USDT_SCAN") or {}
    mode = str(scan_cfg.get("mode") or "").strip().lower()
    if mode != "shared_scanner":
        print(f"USDT共享扫链服务未启动：USDT_SCAN.mode={mode or 'unset'}")
        return
    shared_store = scan_cfg.get("shared_store") or "/shared/usdt_chain.db"
    interval = max(5, int(scan_cfg.get("scan_interval_seconds", 30) or 30))
    retention_hours = int(scan_cfg.get("retention_hours", 24) or 0)
    api_keys = scan_cfg.get("tron_api_keys") or [
        ((config.get("PAYMENTS") or {}).get("usdt_trc20_direct", {}) or {}).get("tron_api_key")
    ]
    api_keys = [key for key in api_keys if key]
    key_index = 0
    backoff_seconds = interval
    last_cleanup_ts = 0.0

    conn, cur = open_shared_store(shared_store)
    _warn_retention_vs_timeout(config, retention_hours)
    print(
        f"✅ USDT共享扫链服务启动: store={shared_store}, "
        f"interval={interval}s, retention_hours={retention_hours}"
    )
    try:
        while True:
            try:
                merged_cfg = build_scan_config(config, key_index)
                saved_count = scan_chain_to_store(
                    cur,
                    conn,
                    merged_cfg,
                    lambda key, default="": get_setting(cur, key, default),
                    lambda key, value: set_setting(cur, conn, key, value),
                )
                if saved_count:
                    print(f"✅ USDT共享扫链入库交易数: {saved_count}")
                last_cleanup_ts = _maybe_purge_chain_store(
                    cur,
                    conn,
                    scan_cfg,
                    last_cleanup_ts,
                )
                backoff_seconds = interval
                time.sleep(interval)
            except Exception as exc:
                if is_rate_limited(exc) and api_keys:
                    key_index = (key_index + 1) % len(api_keys)
                    print(f"⚠️ TronGrid限流，切换API key并退避: next_key_index={key_index}, err={exc}")
                else:
                    print(f"⚠️ USDT共享扫链失败: {exc}")
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 300)
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


if __name__ == "__main__":
    run_forever()
