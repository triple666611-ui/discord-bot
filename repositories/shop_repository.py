from __future__ import annotations

import time
from typing import Any


class ShopRepository:
    def __init__(self, pool):
        self.pool = pool
        self._setup_db()

    def _connect(self):
        return self.pool.getconn()

    def _release(self, conn):
        self.pool.putconn(conn)

    def _setup_db(self) -> None:
        conn = self._connect()
        try:
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

                cur.execute(
                    """
                    UPDATE shop_effects
                    SET updated_ts = %s
                    WHERE updated_ts = 0
                    """,
                    (int(time.time()),),
                )

            conn.commit()
        finally:
            self._release(conn)

    def get_inventory(self, user_id: int) -> dict[str, int]:
        conn = self._connect()
        try:
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
        finally:
            self._release(conn)

    def add_inventory_item(self, user_id: int, item_key: str, quantity: int = 1) -> None:
        if quantity <= 0:
            return

        conn = self._connect()
        try:
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
        finally:
            self._release(conn)

    def consume_inventory_item(self, user_id: int, item_key: str, quantity: int = 1) -> bool:
        if quantity <= 0:
            return False

        conn = self._connect()
        try:
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
        finally:
            self._release(conn)

    def list_effects(self, user_id: int) -> dict[str, dict[str, Any]]:
        conn = self._connect()
        now_ts = int(time.time())

        try:
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
                    """
                    SELECT effect_key, value, expires_ts, updated_ts
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
                    "value": row[1],
                    "expires_ts": row[2],
                    "updated_ts": row[3],
                }
            return result
        finally:
            self._release(conn)

    def get_effect(self, user_id: int, effect_key: str) -> dict[str, Any] | None:
        conn = self._connect()
        now_ts = int(time.time())

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT value, expires_ts, updated_ts
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
                    "value": row[0],
                    "expires_ts": row[1],
                    "updated_ts": row[2],
                }
        finally:
            self._release(conn)

    def set_effect(self, user_id: int, effect_key: str, value: str, expires_ts: int | None = None):
        conn = self._connect()

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shop_effects
                    (user_id, effect_key, effect_value, expires_ts, updated_ts)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, effect_key)
                    DO UPDATE SET
                        effect_value = EXCLUDED.effect_value,
                        expires_ts = EXCLUDED.expires_ts,
                        updated_ts = EXCLUDED.updated_ts
                    """,
                    (
                        user_id,
                        effect_key,
                        value,
                        expires_ts,
                        int(time.time())
                    )
                )

            conn.commit()

        finally:
            self._release(conn)

    def extend_effect(
        self,
        user_id: int,
        effect_key: str,
        value: str,
        duration_seconds: int,
    ) -> int:
        conn = self._connect()
        now_ts = int(time.time())

        try:
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
                    current_expires_ts = int(row[0])
                    base_ts = max(now_ts, current_expires_ts)
                    new_expires_ts = base_ts + duration_seconds

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
        finally:
            self._release(conn)

    def clear_effect(self, user_id: int, effect_key: str) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM shop_effects
                    WHERE user_id = %s AND effect_key = %s
                    """,
                    (user_id, effect_key),
                )
            conn.commit()
        finally:
            self._release(conn)