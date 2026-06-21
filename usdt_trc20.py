#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRC20-USDT direct payment scanner backed by SQLite."""

from __future__ import annotations

import time
import sqlite3
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from secrets import randbelow
from typing import Callable, Iterable, Optional


USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRANSFER_METHOD_ID = "a9059cbb"
USDT_DECIMALS = Decimal("1000000")
USDT_SCALE = 1_000_000
DEFAULT_LAST_BLOCK_KEY = "usdt_trc20.last_scanned_block"
DEFAULT_GLOBAL_LAST_BLOCK_KEY = "usdt_trc20.global_last_scanned_block"


@dataclass(frozen=True)
class TronUsdtTransfer:
    """Parsed TRC20-USDT transfer data from one TRON transaction."""

    txid: str
    block_number: int
    from_address: str
    to_address: str
    amount: Decimal
    raw_amount: int
    timestamp: int


def ensure_usdt_tables(cur, conn) -> None:
    """Create tables used by direct TRC20-USDT payments."""
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS usdt_direct_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    out_trade_no TEXT NOT NULL UNIQUE,
    base_amount TEXT NOT NULL,
    pay_amount TEXT NOT NULL,
    monitor_address TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    create_time INTEGER NOT NULL,
    expire_time INTEGER NOT NULL,
    matched_txid TEXT
)
"""
    )
    ensure_usdt_chain_tables(cur, conn)
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_usdt_direct_order "
        "ON usdt_direct_payments(out_trade_no)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_usdt_direct_match "
        "ON usdt_direct_payments(status, monitor_address, pay_amount, expire_time)"
    )
    conn.commit()


def ensure_usdt_chain_tables(cur, conn) -> None:
    """Create shared chain transaction tables and settings."""
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS usdt_chain_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    txid TEXT NOT NULL UNIQUE,
    block_number INTEGER NOT NULL,
    from_address TEXT NOT NULL,
    to_address TEXT NOT NULL,
    amount TEXT NOT NULL,
    raw_amount TEXT NOT NULL,
    tx_time INTEGER NOT NULL,
    create_time INTEGER NOT NULL,
    out_trade_no TEXT
)
"""
    )
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
"""
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_usdt_chain_txid "
        "ON usdt_chain_transactions(txid)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_usdt_chain_match "
        "ON usdt_chain_transactions(to_address, raw_amount, tx_time)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_usdt_chain_tx_time "
        "ON usdt_chain_transactions(tx_time)"
    )
    conn.commit()


def purge_old_chain_transactions(
    cur,
    conn,
    *,
    retention_hours: int,
    vacuum: bool = False,
    vacuum_min_deleted: int = 1000,
) -> int:
    """Delete chain transactions older than retention_hours (by tx_time)."""
    hours = int(retention_hours or 0)
    if hours <= 0:
        return 0

    cutoff_ms = int(time.time() * 1000) - hours * 3600 * 1000
    cur.execute(
        "DELETE FROM usdt_chain_transactions WHERE tx_time < ?",
        (cutoff_ms,),
    )
    deleted = int(cur.rowcount or 0)
    conn.commit()

    if vacuum and deleted >= max(1, int(vacuum_min_deleted or 0)):
        try:
            cur.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            cur.execute("VACUUM;")
            conn.commit()
        except Exception as exc:
            print(f"⚠️ USDT扫链库 VACUUM 失败: {exc}")

    return deleted


def normalize_amount(value) -> Decimal:
    """Normalize an amount to two display decimals for unique order matching."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def fmt_amount(value) -> str:
    """Format Decimal amount without scientific notation."""
    return format(Decimal(str(value)).quantize(Decimal("0.01")), "f")


def fmt_chain_amount(value) -> str:
    """Format a chain amount with USDT's six decimal places."""
    return format(Decimal(str(value)), "f")


def raw_amount_to_text(raw_amount: int) -> str:
    """Convert USDT's integer base units to a fixed six-decimal string."""
    sign = "-" if raw_amount < 0 else ""
    whole, fraction = divmod(abs(int(raw_amount)), USDT_SCALE)
    return f"{sign}{whole}.{fraction:06d}"


def payment_amount_to_raw(value) -> int:
    """Convert an order amount string to USDT base units for exact matching."""
    amount = Decimal(str(value))
    return int((amount * USDT_DECIMALS).to_integral_value())


def create_direct_payment(cur, conn, out_trade_no: str, base_amount, config: dict, timeout_seconds: int) -> dict:
    """Create one pending direct payment with a unique TRC20-USDT amount."""
    monitor_address = (config.get("monitor_address") or "").strip()
    if not monitor_address:
        raise ValueError("USDT直付收款地址未配置")

    now_ts = int(time.time())
    expire_time = now_ts + int(timeout_seconds)
    pay_amount = _generate_unique_pay_amount(cur, base_amount, monitor_address, now_ts)

    cur.execute(
        """
INSERT OR REPLACE INTO usdt_direct_payments (
    out_trade_no, base_amount, pay_amount, monitor_address, status,
    create_time, expire_time, matched_txid
) VALUES (?, ?, ?, ?, 'pending', ?, ?, NULL)
""",
        (
            out_trade_no,
            fmt_amount(base_amount),
            fmt_amount(pay_amount),
            monitor_address,
            now_ts,
            expire_time,
        ),
    )
    conn.commit()

    return {
        "out_trade_no": out_trade_no,
        "base_amount": fmt_amount(base_amount),
        "pay_amount": fmt_amount(pay_amount),
        "monitor_address": monitor_address,
        "expire_time": expire_time,
    }


def get_direct_payment(cur, out_trade_no: str) -> Optional[dict]:
    """Read direct payment information for a displayed order."""
    row = cur.execute(
        """
SELECT out_trade_no, base_amount, pay_amount, monitor_address, status,
       create_time, expire_time, matched_txid
FROM usdt_direct_payments
WHERE out_trade_no=?
""",
        (out_trade_no,),
    ).fetchone()
    if not row:
        return None
    return {
        "out_trade_no": row[0],
        "base_amount": row[1],
        "pay_amount": row[2],
        "monitor_address": row[3],
        "status": row[4],
        "create_time": row[5],
        "expire_time": row[6],
        "matched_txid": row[7],
    }


def mark_expired_direct_payments(cur, conn) -> None:
    """Keep the direct-payment table in sync with cancelled orders."""
    cur.execute(
        """
UPDATE usdt_direct_payments
SET status='expired'
WHERE status='pending' AND expire_time < ?
""",
        (int(time.time()),),
    )
    conn.commit()


def scan_and_match_payments(
    cur,
    conn,
    paycfg: dict,
    mark_paid: Callable[[str], None],
    get_setting: Callable[[str, str], str],
    set_setting: Callable[[str, str], None],
) -> int:
    """Scan confirmed TRON blocks and mark matched akabot orders as paid."""
    config = (paycfg or {}).get("usdt_trc20_direct", {})
    if not config.get("enabled", False):
        return 0

    monitor_address = (config.get("monitor_address") or "").strip()
    if not monitor_address:
        return 0

    client = _build_tron_client(config)
    latest_block = int(client.get_latest_block()["block_header"]["raw_data"]["number"])
    confirmations = max(0, int(config.get("confirmations", 1) or 1))
    target_block = latest_block - confirmations
    if target_block <= 0:
        return 0

    last_scanned = _get_last_scanned_block(get_setting, config, target_block)
    max_blocks = max(1, int(config.get("max_blocks_per_scan", 20) or 20))
    end_block = min(target_block, last_scanned + max_blocks)
    if end_block <= last_scanned:
        return 0

    matched_count = 0
    for block_number in range(last_scanned + 1, end_block + 1):
        block = client.get_block(block_number)
        for transfer in parse_usdt_transfers(block, client):
            if transfer.to_address != monitor_address:
                continue
            _save_transfer(cur, conn, transfer)
            out_trade_no = _match_transfer_to_order(cur, conn, transfer)
            if out_trade_no:
                mark_paid(out_trade_no)
                matched_count += 1
        set_setting(DEFAULT_LAST_BLOCK_KEY, str(block_number))

    return matched_count


def scan_chain_to_store(
    cur,
    conn,
    config: dict,
    get_setting: Callable[[str, str], str],
    set_setting: Callable[[str, str], None],
) -> int:
    """Scan TRON once and write all TRC20-USDT transfers to a shared store."""
    if not config.get("enabled", True):
        return 0

    client = _build_tron_client(config)
    latest_block = int(client.get_latest_block()["block_header"]["raw_data"]["number"])
    confirmations = max(0, int(config.get("confirmations", 1) or 1))
    target_block = latest_block - confirmations
    if target_block <= 0:
        return 0

    last_scanned = _get_last_scanned_block(
        get_setting,
        {**config, "start_block_key": DEFAULT_GLOBAL_LAST_BLOCK_KEY},
        target_block,
    )
    max_blocks = max(1, int(config.get("max_blocks_per_scan", 20) or 20))
    end_block = min(target_block, last_scanned + max_blocks)
    if end_block <= last_scanned:
        return 0

    saved_count = 0
    for block_number in range(last_scanned + 1, end_block + 1):
        block = client.get_block(block_number)
        for transfer in parse_usdt_transfers(block, client):
            saved_count += _save_transfer(cur, conn, transfer)
        set_setting(DEFAULT_GLOBAL_LAST_BLOCK_KEY, str(block_number))

    return saved_count


def match_payments_from_shared_store(
    cur,
    conn,
    shared_store_path: str,
    mark_paid: Callable[[str], None],
) -> int:
    """Match local pending orders against a shared chain transaction database."""
    if not shared_store_path:
        return 0

    shared_conn = sqlite3.connect(shared_store_path, check_same_thread=False)
    shared_cur = shared_conn.cursor()
    try:
        shared_cur.execute("PRAGMA busy_timeout=5000;")
        ensure_usdt_chain_tables(shared_cur, shared_conn)
        rows = cur.execute(
            """
SELECT p.out_trade_no,
       p.monitor_address,
       p.pay_amount,
       p.create_time,
       p.expire_time
FROM usdt_direct_payments p
JOIN orders o ON o.out_trade_no=p.out_trade_no
WHERE p.status='pending'
  AND o.status='pending'
  AND p.expire_time>=?
ORDER BY p.create_time ASC
""",
            (int(time.time()),),
        ).fetchall()

        matched_count = 0
        for out_trade_no, monitor_address, pay_amount, create_time, expire_time in rows:
            try:
                raw_amount = str(payment_amount_to_raw(pay_amount))
            except Exception:
                continue
            tx_row = shared_cur.execute(
                """
SELECT txid, from_address, amount, raw_amount, tx_time
FROM usdt_chain_transactions
WHERE to_address=?
  AND raw_amount=?
  AND tx_time>=?
  AND tx_time<=?
ORDER BY block_number ASC, id ASC
LIMIT 1
""",
                (
                    monitor_address,
                    raw_amount,
                    int(create_time) * 1000,
                    int(expire_time) * 1000,
                ),
            ).fetchone()
            if not tx_row:
                continue

            txid = tx_row[0]
            cur.execute(
                """
UPDATE usdt_direct_payments
SET status='paid', matched_txid=?
WHERE out_trade_no=? AND status='pending'
""",
                (txid, out_trade_no),
            )
            conn.commit()
            mark_paid(out_trade_no)
            matched_count += 1

        return matched_count
    finally:
        try:
            shared_cur.close()
        except Exception:
            pass
        try:
            shared_conn.close()
        except Exception:
            pass


def parse_usdt_transfers(block: dict, client) -> Iterable[TronUsdtTransfer]:
    """Parse successful TRC20-USDT transfer transactions from a TRON block."""
    transactions = block.get("transactions") or []
    block_number = int(block.get("block_header", {}).get("raw_data", {}).get("number", 0) or 0)

    for trx in transactions:
        # 链上区块里可能存在异常交易，单笔失败不能阻断整块进度。
        try:
            transfer = _parse_usdt_transfer(trx, block_number, client)
        except Exception as exc:
            print(f"⚠️ 跳过异常USDT交易: tx={trx.get('txID', '')} err={exc}")
            continue
        if transfer:
            yield transfer


def _parse_usdt_transfer(trx: dict, block_number: int, client) -> Optional[TronUsdtTransfer]:
    """Parse one successful TRC20-USDT transfer transaction if it matches."""
    if not _is_success_transaction(trx):
        return None
    raw_contracts = trx.get("raw_data", {}).get("contract") or []
    if not raw_contracts:
        return None
    contract = raw_contracts[0]
    if contract.get("type") != "TriggerSmartContract":
        return None

    value = contract.get("parameter", {}).get("value", {})
    data = value.get("data")
    if not data or not data.startswith(TRANSFER_METHOD_ID):
        return None

    contract_address = client.to_base58check_address(value.get("contract_address"))
    if contract_address != USDT_TRC20_CONTRACT:
        return None

    raw_amount = int(data[-64:], 16)
    if raw_amount <= 0:
        return None

    return TronUsdtTransfer(
        txid=trx.get("txID", ""),
        block_number=block_number,
        from_address=client.to_base58check_address(value.get("owner_address")),
        to_address=client.to_base58check_address("41" + data[8:72][-40:]),
        amount=Decimal(raw_amount_to_text(raw_amount)),
        raw_amount=raw_amount,
        timestamp=int(trx.get("raw_data", {}).get("timestamp") or int(time.time() * 1000)),
    )


def _generate_unique_pay_amount(cur, base_amount, monitor_address: str, now_ts: int) -> Decimal:
    """Add a small random suffix until the pending direct-payment amount is unique."""
    base = normalize_amount(base_amount)
    for _ in range(200):
        suffix = Decimal(randbelow(50) + 1) / Decimal("100")
        candidate = (base + suffix).quantize(Decimal("0.01"))
        exists = cur.execute(
            """
SELECT 1
FROM usdt_direct_payments
WHERE status='pending'
  AND monitor_address=?
  AND pay_amount=?
  AND expire_time>=?
LIMIT 1
""",
            (monitor_address, fmt_amount(candidate), now_ts),
        ).fetchone()
        if not exists:
            return candidate
    raise RuntimeError("无法生成唯一USDT支付金额")


def _build_tron_client(config: dict):
    """Build a Tron client lazily so normal bot startup does not require tronpy."""
    try:
        from tronpy import Tron
        from tronpy.providers import HTTPProvider
    except ImportError as exc:
        raise RuntimeError("缺少 tronpy 依赖，请先安装 requirements.txt") from exc

    api_keys = config.get("tron_api_keys")
    api_key = None
    if isinstance(api_keys, list) and api_keys:
        index = int(config.get("_api_key_index", 0) or 0) % len(api_keys)
        api_key = api_keys[index]
    if not api_key:
        api_key = config.get("tron_api_key") or config.get("api_key") or None
    if api_key:
        return Tron(HTTPProvider(api_key=[api_key]))
    return Tron()


def _get_last_scanned_block(get_setting: Callable[[str, str], str], config: dict, target_block: int) -> int:
    """Resolve scan start block from settings or config."""
    setting_key = config.get("start_block_key") or DEFAULT_LAST_BLOCK_KEY
    saved = str(get_setting(setting_key, "") or "").strip()
    if saved.isdigit():
        return int(saved)

    configured = str(config.get("start_block", "") or "").strip()
    if configured.isdigit():
        return int(configured)

    return max(0, target_block - 1)


def _is_success_transaction(trx: dict) -> bool:
    """Return True only when TRON marks the transaction as successful."""
    ret_list = trx.get("ret") or []
    if not ret_list:
        return False
    return ret_list[0].get("contractRet") == "SUCCESS"


def _save_transfer(cur, conn, transfer: TronUsdtTransfer) -> int:
    """Persist a chain transaction once for deduplication and audit."""
    cur.execute(
        """
INSERT OR IGNORE INTO usdt_chain_transactions (
    txid, block_number, from_address, to_address, amount, raw_amount,
    tx_time, create_time, out_trade_no
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
""",
        (
            transfer.txid,
            transfer.block_number,
            transfer.from_address,
            transfer.to_address,
            raw_amount_to_text(transfer.raw_amount),
            str(transfer.raw_amount),
            transfer.timestamp,
            int(time.time()),
        ),
    )
    conn.commit()
    return 1 if cur.rowcount == 1 else 0


def _match_transfer_to_order(cur, conn, transfer: TronUsdtTransfer) -> Optional[str]:
    """Match one transfer by exact unique amount and return the order number."""
    rows = cur.execute(
        """
SELECT p.out_trade_no, p.pay_amount
FROM usdt_direct_payments p
JOIN orders o ON o.out_trade_no=p.out_trade_no
WHERE p.status='pending'
  AND o.status='pending'
  AND p.monitor_address=?
  AND p.expire_time>=?
ORDER BY p.create_time ASC
""",
        (transfer.to_address, int(time.time())),
    ).fetchall()
    matched_order = None
    for out_trade_no, pay_amount in rows:
        try:
            if payment_amount_to_raw(pay_amount) == transfer.raw_amount:
                matched_order = out_trade_no
                break
        except Exception:
            continue
    if not matched_order:
        return None

    cur.execute(
        """
UPDATE usdt_direct_payments
SET status='paid', matched_txid=?
WHERE out_trade_no=? AND status='pending'
""",
        (transfer.txid, matched_order),
    )
    cur.execute(
        "UPDATE usdt_chain_transactions SET out_trade_no=? WHERE txid=?",
        (matched_order, transfer.txid),
    )
    conn.commit()

    return matched_order
