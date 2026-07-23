import os
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from bot.db.protocol import utcnow


class PostgresDatabase:
    """Supabase / PostgreSQL backend for 24/7 cloud deployment."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = psycopg.connect(self.database_url, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS proxy_checks (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            proxy_count INTEGER NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_proxy_checks_user
                        ON proxy_checks (user_id, created_at DESC)
                        """
                    )
                    cur.execute(
                        "INSERT INTO settings (key, value) VALUES ('maintenance', '0') "
                        "ON CONFLICT (key) DO NOTHING"
                    )
        except psycopg.Error:
            raise RuntimeError(
                "Could not connect to PostgreSQL. "
                "Run supabase/schema.sql in Supabase SQL Editor first."
            ) from None

    def _row_to_dict(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if not row:
            return None
        out = dict(row)
        for key in ("verified", "used"):
            if key in out and out[key] is not None:
                out[key] = bool(out[key])
        return out

    def get_setting(self, key: str, default: str = "") -> str:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
                row = cur.fetchone()
                return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """,
                    (key, value),
                )

    def is_maintenance(self) -> bool:
        return self.get_setting("maintenance", "0") == "1"

    def set_maintenance(self, enabled: bool) -> None:
        self.set_setting("maintenance", "1" if enabled else "0")

    def upsert_user(self, user_id: int, username: str | None, first_name: str | None) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, username, first_name, created_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name
                    """,
                    (user_id, username, first_name),
                )

    def set_user_verified(self, user_id: int, verified: bool = True) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET verified = %s WHERE user_id = %s",
                    (verified, user_id),
                )

    def is_user_verified(self, user_id: int) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT verified FROM users WHERE user_id = %s", (user_id,)
                )
                row = cur.fetchone()
                return bool(row and row["verified"])

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
                return self._row_to_dict(cur.fetchone())

    def get_all_user_ids(self) -> list[int]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users ORDER BY user_id")
                return [int(row["user_id"]) for row in cur.fetchall()]

    def create_order(
        self,
        user_id: int,
        pack_id: str,
        pack_name: str,
        proxy_count: int,
        amount: float,
    ) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders
                        (user_id, pack_id, pack_name, proxy_count, amount, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, 'awaiting_payment', NOW())
                    RETURNING id
                    """,
                    (user_id, pack_id, pack_name, proxy_count, amount),
                )
                row = cur.fetchone()
                return int(row["id"])

    def set_order_trx(self, order_id: int, trx_id: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders SET trx_id = %s, status = 'pending_review'
                    WHERE id = %s
                    """,
                    (trx_id, order_id),
                )

    def get_order(self, order_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
                return self._row_to_dict(cur.fetchone())

    def get_user_orders(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM orders WHERE user_id = %s
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    (user_id, limit),
                )
                return [self._row_to_dict(r) for r in cur.fetchall()]

    def get_pending_orders(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT o.*, u.username, u.first_name
                    FROM orders o
                    JOIN users u ON u.user_id = o.user_id
                    WHERE o.status = 'pending_review'
                    ORDER BY o.created_at ASC
                    """
                )
                return [self._row_to_dict(r) for r in cur.fetchall()]

    def approve_order(self, order_id: int, proxies: list[str]) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, status, proxy_count FROM orders
                    WHERE id = %s FOR UPDATE
                    """,
                    (order_id,),
                )
                order = cur.fetchone()
                if not order or order["status"] != "pending_review":
                    return False

                cur.execute(
                    """
                    SELECT id, proxy_line FROM proxy_stock
                    WHERE used = FALSE
                    ORDER BY id ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (order["proxy_count"],),
                )
                rows = cur.fetchall()
                if len(rows) < order["proxy_count"]:
                    return False

                proxy_lines = [r["proxy_line"] for r in rows]
                proxy_ids = [r["id"] for r in rows]
                proxy_text = "\n".join(proxy_lines)

                cur.execute(
                    """
                    UPDATE orders
                    SET status = 'completed', proxies = %s, approved_at = NOW()
                    WHERE id = %s AND status = 'pending_review'
                    """,
                    (proxy_text, order_id),
                )
                if cur.rowcount == 0:
                    return False

                cur.execute(
                    """
                    UPDATE proxy_stock
                    SET used = TRUE, order_id = %s
                    WHERE id = ANY(%s)
                    """,
                    (order_id, proxy_ids),
                )
                proxies.clear()
                proxies.extend(proxy_lines)
                return True

    def reject_order(self, order_id: int) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders SET status = 'rejected'
                    WHERE id = %s AND status = 'pending_review'
                    """,
                    (order_id,),
                )
                return cur.rowcount > 0

    def cancel_order(self, order_id: int, user_id: int) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE orders SET status = 'cancelled'
                    WHERE id = %s AND user_id = %s
                      AND status IN ('awaiting_payment', 'pending_review')
                    """,
                    (order_id, user_id),
                )
                return cur.rowcount > 0

    def get_available_proxies(self, count: int) -> list[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT proxy_line FROM proxy_stock
                    WHERE used = FALSE
                    ORDER BY id ASC LIMIT %s
                    """,
                    (count,),
                )
                return [r["proxy_line"] for r in cur.fetchall()]

    def add_proxies(self, proxies: list[str]) -> int:
        added = 0
        with self._conn() as conn:
            with conn.cursor() as cur:
                for proxy in proxies:
                    proxy = proxy.strip()
                    if not proxy:
                        continue
                    cur.execute(
                        """
                        INSERT INTO proxy_stock (proxy_line, added_at)
                        VALUES (%s, NOW())
                        ON CONFLICT (proxy_line) DO NOTHING
                        RETURNING id
                        """,
                        (proxy,),
                    )
                    if cur.fetchone():
                        added += 1
        return added

    def count_available_proxies(self) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS count FROM proxy_stock WHERE used = FALSE"
                )
                row = cur.fetchone()
                return int(row["count"])

    def trx_exists(self, trx_id: str) -> bool:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 AS ok FROM orders WHERE trx_id = %s", (trx_id,)
                )
                return cur.fetchone() is not None

    def get_user_stats(self, user_id: int) -> dict[str, int]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(CASE WHEN status = 'completed' THEN proxy_count ELSE 0 END), 0) AS total_proxies
                    FROM orders WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                return {
                    "total_orders": int(row["total_orders"]),
                    "total_proxies": int(row["total_proxies"]),
                }

    def count_proxy_checks_24h(self, user_id: int) -> int:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS count FROM proxy_checks
                    WHERE user_id = %s
                      AND created_at >= NOW() - INTERVAL '24 hours'
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                return int(row["count"])

    def record_proxy_check(self, user_id: int, proxy_count: int) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO proxy_checks (user_id, proxy_count, created_at)
                    VALUES (%s, %s, NOW())
                    """,
                    (user_id, proxy_count),
                )
