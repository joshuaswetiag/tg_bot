import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from bot.db.protocol import utcnow


class SqliteDatabase:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    verified INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    pack_id TEXT NOT NULL,
                    pack_name TEXT NOT NULL,
                    proxy_count INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    trx_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    proxies TEXT,
                    created_at TEXT NOT NULL,
                    approved_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS proxy_stock (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy_line TEXT NOT NULL UNIQUE,
                    used INTEGER DEFAULT 0,
                    order_id INTEGER,
                    added_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proxy_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    proxy_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_proxy_checks_user
                    ON proxy_checks (user_id, created_at);

                INSERT OR IGNORE INTO settings (key, value) VALUES ('maintenance', '0');
                """
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

    def is_maintenance(self) -> bool:
        return self.get_setting("maintenance", "0") == "1"

    def set_maintenance(self, enabled: bool) -> None:
        self.set_setting("maintenance", "1" if enabled else "0")

    def upsert_user(self, user_id: int, username: str | None, first_name: str | None) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username, first_name, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name
                """,
                (user_id, username, first_name, utcnow()),
            )

    def set_user_verified(self, user_id: int, verified: bool = True) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET verified = ? WHERE user_id = ?",
                (1 if verified else 0, user_id),
            )

    def is_user_verified(self, user_id: int) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT verified FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return bool(row and row["verified"])

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_user_ids(self) -> list[int]:
        with self._conn() as conn:
            rows = conn.execute("SELECT user_id FROM users ORDER BY user_id").fetchall()
            return [int(row["user_id"]) for row in rows]

    def create_order(
        self,
        user_id: int,
        pack_id: str,
        pack_name: str,
        proxy_count: int,
        amount: float,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO orders
                    (user_id, pack_id, pack_name, proxy_count, amount, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'awaiting_payment', ?)
                """,
                (user_id, pack_id, pack_name, proxy_count, amount, utcnow()),
            )
            return int(cur.lastrowid)

    def set_order_trx(self, order_id: int, trx_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE orders SET trx_id = ?, status = 'pending_review'
                WHERE id = ?
                """,
                (trx_id, order_id),
            )

    def get_order(self, order_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_user_orders(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM orders WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_pending_orders(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT o.*, u.username, u.first_name
                FROM orders o
                JOIN users u ON u.user_id = o.user_id
                WHERE o.status = 'pending_review'
                ORDER BY o.created_at ASC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def approve_order(self, order_id: int, proxies: list[str]) -> bool:
        proxy_text = "\n".join(proxies)
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE orders
                SET status = 'completed', proxies = ?, approved_at = ?
                WHERE id = ? AND status = 'pending_review'
                """,
                (proxy_text, utcnow(), order_id),
            )
            if cur.rowcount == 0:
                return False
            for proxy in proxies:
                conn.execute(
                    """
                    UPDATE proxy_stock SET used = 1, order_id = ?
                    WHERE proxy_line = ?
                    """,
                    (order_id, proxy),
                )
            return True

    def reject_order(self, order_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE orders SET status = 'rejected'
                WHERE id = ? AND status = 'pending_review'
                """,
                (order_id,),
            )
            return cur.rowcount > 0

    def cancel_order(self, order_id: int, user_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE orders SET status = 'cancelled'
                WHERE id = ? AND user_id = ?
                  AND status IN ('awaiting_payment', 'pending_review')
                """,
                (order_id, user_id),
            )
            return cur.rowcount > 0

    def get_available_proxies(self, count: int) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT proxy_line FROM proxy_stock
                WHERE used = 0
                ORDER BY id ASC LIMIT ?
                """,
                (count,),
            ).fetchall()
            return [r["proxy_line"] for r in rows]

    def add_proxies(self, proxies: list[str]) -> int:
        added = 0
        with self._conn() as conn:
            for proxy in proxies:
                proxy = proxy.strip()
                if not proxy:
                    continue
                try:
                    conn.execute(
                        """
                        INSERT INTO proxy_stock (proxy_line, added_at)
                        VALUES (?, ?)
                        """,
                        (proxy, utcnow()),
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    pass
        return added

    def count_available_proxies(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM proxy_stock WHERE used = 0"
            ).fetchone()
            return int(row["c"])

    def trx_exists(self, trx_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM orders WHERE trx_id = ?", (trx_id,)
            ).fetchone()
            return row is not None

    def get_user_stats(self, user_id: int) -> dict[str, int]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_orders,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN proxy_count ELSE 0 END), 0) AS total_proxies
                FROM orders WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            return {
                "total_orders": int(row["total_orders"]),
                "total_proxies": int(row["total_proxies"]),
            }

    def count_proxy_checks_24h(self, user_id: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c FROM proxy_checks
                WHERE user_id = ?
                  AND created_at >= datetime('now', '-24 hours')
                """,
                (user_id,),
            ).fetchone()
            return int(row["c"])

    def record_proxy_check(self, user_id: int, proxy_count: int) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO proxy_checks (user_id, proxy_count, created_at)
                VALUES (?, ?, ?)
                """,
                (user_id, proxy_count, utcnow()),
            )
