from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

from psycopg2.pool import SimpleConnectionPool


class ShopRepository:
    def __init__(self, pool: SimpleConnectionPool):
        self.pool = pool
        self.has_effect_value_column = False
        self.has_value_column = False
        self._setup_db()

    @contextmanager
    def _get_conn(self):
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    def _detect_effect_columns(self, cur) -> None:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'shop_effects'
            """
        )
        columns = {str(row[0]) for row in cur.fetchall()}
        self.has_effect_value_column = 'effect_value' in columns
        self.has_value_column = 'value' in columns

    def _setup_db(self) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS shop_inventory (
                        user_id BIGINT NOT NULL,
                        item_key TEXT NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (user_id, item_key)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS shop_effects (
                        user_id BIGINT NOT NULL,
                        effect_key TEXT NOT NULL,
                        value TEXT,
                        expires_ts BIGINT,
                        updated_ts BIGINT NOT NULL DEFAULT 0,
                        PRIMARY KEY (user_id, effect_key)
                    )
                    """
                )
                cur.execute(
                    """
                    ALTER TABLE shop_effects
                    ADD COLUMN IF NOT EXISTS value TEXT
                    """
                )
                cur.execute(
                    """
                    ALTER TABLE shop_effects
                    ADD COLUMN IF NOT EXISTS expires_ts BIGINT
                    """
                )
                cur.execute(
                    """
                    ALTER TABLE shop_effects
                    ADD COLUMN IF NOT EXISTS updated_ts BIGINT NOT NULL DEFAULT 0
                    """
                )

                self._detect_effect_columns(cur)

                if self.has_effect_value_column and self.has_value_column:
                    cur.execute(
                        """
                        UPDATE shop_effects
                        SET value = effect_value
                        WHERE value IS NULL AND effect_value IS NOT NULL
                        """
                    )

                cur.execute(
                    """
                    UPDATE shop_effects
                    SET updated_ts = %s
                    WHERE updated_ts = 0
                    """,
                    (int(time.time()),),
                )
            conn.commit()

    def _effect_value_expr(self) -> str:
        if self.has_effect_value_column and self.has_value_column:
            return 'COALESCE(value, effect_value)'
        if self.has_effect_value_column:
            return 'effect_value'
        return 'value'

    def get_inventory(self, user_id: int) -> dict[str, int]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT item_key, quantity
                    FROM shop_inventory
                    WHERE user_id = %s AND quantity > 0
                    ORDER BY item_key
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def add_inventory_item(self, user_id: int, item_key: str, quantity: int = 1) -> None:
        if quantity <= 0:
            return

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shop_inventory (user_id, item_key, quantity)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, item_key)
                    DO UPDATE SET quantity = shop_inventory.quantity + EXCLUDED.quantity
                    """,
                    (user_id, item_key, quantity),
                )
            conn.commit()

    def consume_inventory_item(self, user_id: int, item_key: str, quantity: int = 1) -> bool:
        if quantity <= 0:
            return False

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT quantity
                    FROM shop_inventory
                    WHERE user_id = %s AND item_key = %s
                    """,
                    (user_id, item_key),
                )
                row = cur.fetchone()
                if row is None:
                    return False

                current_qty = int(row[0])
                if current_qty < quantity:
                    return False

                new_qty = current_qty - quantity
                if new_qty > 0:
                    cur.execute(
                        """
                        UPDATE shop_inventory
                        SET quantity = %s
                        WHERE user_id = %s AND item_key = %s
                        """,
                        (new_qty, user_id, item_key),
                    )
                else:
                    cur.execute(
                        """
                        DELETE FROM shop_inventory
                        WHERE user_id = %s AND item_key = %s
                        """,
                        (user_id, item_key),
                    )
            conn.commit()
        return True

    def list_effects(self, user_id: int) -> dict[str, dict[str, Any]]:
        now_ts = int(time.time())
        value_expr = self._effect_value_expr()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM shop_effects
                    WHERE user_id = %s
                      AND expires_ts IS NOT NULL
                      AND expires_ts <= %s
                    """,
                    (user_id, now_ts),
                )
                cur.execute(
                    f"""
                    SELECT effect_key, {value_expr} AS effect_value, expires_ts, updated_ts
                    FROM shop_effects
                    WHERE user_id = %s
                    ORDER BY effect_key
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
            conn.commit()

        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            result[str(row[0])] = {
                'value': row[1],
                'expires_ts': row[2],
                'updated_ts': row[3],
            }
        return result

    def get_effect(self, user_id: int, effect_key: str) -> dict[str, Any] | None:
        now_ts = int(time.time())
        value_expr = self._effect_value_expr()
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {value_expr} AS effect_value, expires_ts, updated_ts
                    FROM shop_effects
                    WHERE user_id = %s AND effect_key = %s
                    """,
                    (user_id, effect_key),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                expires_ts = row[1]
                if expires_ts is not None and int(expires_ts) <= now_ts:
                    cur.execute(
                        """
                        DELETE FROM shop_effects
                        WHERE user_id = %s AND effect_key = %s
                        """,
                        (user_id, effect_key),
                    )
                    conn.commit()
                    return None

                return {
                    'value': row[0],
                    'expires_ts': row[1],
                    'updated_ts': row[2],
                }

    def set_effect(
        self,
        user_id: int,
        effect_key: str,
        value: str,
        expires_ts: int | None = None,
    ) -> None:
        now_ts = int(time.time())
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                if self.has_effect_value_column:
                    cur.execute(
                        """
                        INSERT INTO shop_effects (user_id, effect_key, value, effect_value, expires_ts, updated_ts)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, effect_key)
                        DO UPDATE SET
                            value = EXCLUDED.value,
                            effect_value = EXCLUDED.effect_value,
                            expires_ts = EXCLUDED.expires_ts,
                            updated_ts = EXCLUDED.updated_ts
                        """,
                        (user_id, effect_key, value, value, expires_ts, now_ts),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO shop_effects (user_id, effect_key, value, expires_ts, updated_ts)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, effect_key)
                        DO UPDATE SET
                            value = EXCLUDED.value,
                            expires_ts = EXCLUDED.expires_ts,
                            updated_ts = EXCLUDED.updated_ts
                        """,
                        (user_id, effect_key, value, expires_ts, now_ts),
                    )
            conn.commit()

    def extend_effect(
        self,
        user_id: int,
        effect_key: str,
        value: str,
        duration_seconds: int,
    ) -> int:
        now_ts = int(time.time())
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT expires_ts
                    FROM shop_effects
                    WHERE user_id = %s AND effect_key = %s
                    """,
                    (user_id, effect_key),
                )
                row = cur.fetchone()

                if row is None or row[0] is None:
                    new_expires_ts = now_ts + duration_seconds
                else:
                    new_expires_ts = max(now_ts, int(row[0])) + duration_seconds

                if self.has_effect_value_column:
                    cur.execute(
                        """
                        INSERT INTO shop_effects (user_id, effect_key, value, effect_value, expires_ts, updated_ts)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, effect_key)
                        DO UPDATE SET
                            value = EXCLUDED.value,
                            effect_value = EXCLUDED.effect_value,
                            expires_ts = EXCLUDED.expires_ts,
                            updated_ts = EXCLUDED.updated_ts
                        """,
                        (user_id, effect_key, value, value, new_expires_ts, now_ts),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO shop_effects (user_id, effect_key, value, expires_ts, updated_ts)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (user_id, effect_key)
                        DO UPDATE SET
                            value = EXCLUDED.value,
                            expires_ts = EXCLUDED.expires_ts,
                            updated_ts = EXCLUDED.updated_ts
                        """,
                        (user_id, effect_key, value, new_expires_ts, now_ts),
                    )
            conn.commit()
        return new_expires_ts

    def clear_effect(self, user_id: int, effect_key: str) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM shop_effects
                    WHERE user_id = %s AND effect_key = %s
                    """,
                    (user_id, effect_key),
                )
            conn.commit()