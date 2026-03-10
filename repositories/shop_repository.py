from __future__ import annotations

import os
import time
from typing import Any

import psycopg2
import psycopg2.extras


class ShopRepository:
    def __init__(self, database_url: str | None = None):
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL не найден. Укажи URL PostgreSQL в переменных окружения.")
        self._setup_db()

    def _connect(self):
        return psycopg2.connect(self.database_url)

    def _setup_db(self) -> None:
        with self._connect() as conn:
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
                        updated_ts BIGINT NOT NULL,
                        PRIMARY KEY (user_id, effect_key)
                    )
                    """
                )
            conn.commit()

    def get_inventory(self, user_id: int) -> dict[str, int]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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

        return {str(row["item_key"]): int(row["quantity"]) for row in rows}

    def add_inventory_item(self, user_id: int, item_key: str, quantity: int = 1) -> None:
        if quantity <= 0:
            return

        with self._connect() as conn:
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

        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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

                current_qty = int(row["quantity"])
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

        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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
            result[str(row["effect_key"])] = {
                "value": row["value"],
                "expires_ts": row["expires_ts"],
                "updated_ts": row["updated_ts"],
            }
        return result

    def get_effect(self, user_id: int, effect_key: str) -> dict[str, Any] | None:
        now_ts = int(time.time())

        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT effect_key, value, expires_ts, updated_ts
                    FROM shop_effects
                    WHERE user_id = %s AND effect_key = %s
                    """,
                    (user_id, effect_key),
                )
                row = cur.fetchone()

                if row is None:
                    return None

                expires_ts = row["expires_ts"]
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
                    "effect_key": row["effect_key"],
                    "value": row["value"],
                    "expires_ts": row["expires_ts"],
                    "updated_ts": row["updated_ts"],
                }

    def set_effect(
        self,
        user_id: int,
        effect_key: str,
        value: str,
        expires_ts: int | None = None,
    ) -> None:
        now_ts = int(time.time())

        with self._connect() as conn:
            with conn.cursor() as cur:
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
        current = self.get_effect(user_id, effect_key)

        if current is None or current.get("expires_ts") is None:
            new_expires_ts = now_ts + duration_seconds
        else:
            current_expires_ts = int(current["expires_ts"])
            base_ts = max(now_ts, current_expires_ts)
            new_expires_ts = base_ts + duration_seconds

        self.set_effect(user_id, effect_key, value, new_expires_ts)
        return new_expires_ts

    def clear_effect(self, user_id: int, effect_key: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM shop_effects
                    WHERE user_id = %s AND effect_key = %s
                    """,
                    (user_id, effect_key),
                )
            conn.commit()