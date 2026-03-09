import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from psycopg2.pool import SimpleConnectionPool


@dataclass(slots=True)
class InventoryItem:
    user_id: int
    item_key: str
    quantity: int


class ShopRepository:
    def __init__(self, pool: SimpleConnectionPool):
        self.pool = pool
        self._setup_db()

    @contextmanager
    def _get_conn(self):
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

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
                        effect_value TEXT NOT NULL,
                        expires_ts BIGINT,
                        PRIMARY KEY (user_id, effect_key)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_shop_effects_expires
                    ON shop_effects (expires_ts)
                    """
                )
                conn.commit()

    def add_inventory_item(self, user_id: int, item_key: str, quantity: int = 1) -> None:
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

    def get_inventory(self, user_id: int) -> dict[str, int]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT item_key, quantity
                    FROM shop_inventory
                    WHERE user_id = %s AND quantity > 0
                    ORDER BY item_key ASC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
        return {str(row[0]): int(row[1]) for row in rows}

    def get_item_quantity(self, user_id: int, item_key: str) -> int:
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
        return int(row[0]) if row else 0

    def consume_inventory_item(self, user_id: int, item_key: str, quantity: int = 1) -> bool:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT quantity
                    FROM shop_inventory
                    WHERE user_id = %s AND item_key = %s
                    FOR UPDATE
                    """,
                    (user_id, item_key),
                )
                row = cur.fetchone()
                current = int(row[0]) if row else 0
                if current < quantity:
                    conn.rollback()
                    return False

                new_quantity = current - quantity
                if new_quantity > 0:
                    cur.execute(
                        """
                        UPDATE shop_inventory
                        SET quantity = %s
                        WHERE user_id = %s AND item_key = %s
                        """,
                        (new_quantity, user_id, item_key),
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

    def set_effect(self, user_id: int, effect_key: str, effect_value: str, expires_ts: int | None = None) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO shop_effects (user_id, effect_key, effect_value, expires_ts)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, effect_key)
                    DO UPDATE SET
                        effect_value = EXCLUDED.effect_value,
                        expires_ts = EXCLUDED.expires_ts
                    """,
                    (user_id, effect_key, effect_value, expires_ts),
                )
                conn.commit()

    def extend_effect(self, user_id: int, effect_key: str, effect_value: str, extend_seconds: int) -> int:
        now = int(time.time())
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT expires_ts
                    FROM shop_effects
                    WHERE user_id = %s AND effect_key = %s
                    FOR UPDATE
                    """,
                    (user_id, effect_key),
                )
                row = cur.fetchone()
                current_expires = int(row[0]) if row and row[0] is not None else None
                base_ts = max(now, current_expires or now)
                new_expires = base_ts + extend_seconds
                cur.execute(
                    """
                    INSERT INTO shop_effects (user_id, effect_key, effect_value, expires_ts)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, effect_key)
                    DO UPDATE SET
                        effect_value = EXCLUDED.effect_value,
                        expires_ts = EXCLUDED.expires_ts
                    """,
                    (user_id, effect_key, effect_value, new_expires),
                )
                conn.commit()
                return new_expires

    def get_effect(self, user_id: int, effect_key: str) -> dict[str, Any] | None:
        now = int(time.time())
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT effect_value, expires_ts
                    FROM shop_effects
                    WHERE user_id = %s AND effect_key = %s
                    """,
                    (user_id, effect_key),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                effect_value = str(row[0])
                expires_ts = int(row[1]) if row[1] is not None else None
                if expires_ts is not None and expires_ts <= now:
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
            "value": effect_value,
            "expires_ts": expires_ts,
        }

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

    def list_effects(self, user_id: int) -> dict[str, dict[str, Any]]:
        now = int(time.time())
        effects: dict[str, dict[str, Any]] = {}
        expired: list[str] = []
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT effect_key, effect_value, expires_ts
                    FROM shop_effects
                    WHERE user_id = %s
                    ORDER BY effect_key ASC
                    """,
                    (user_id,),
                )
                rows = cur.fetchall()
                for row in rows:
                    effect_key = str(row[0])
                    effect_value = str(row[1])
                    expires_ts = int(row[2]) if row[2] is not None else None
                    if expires_ts is not None and expires_ts <= now:
                        expired.append(effect_key)
                        continue
                    effects[effect_key] = {
                        "value": effect_value,
                        "expires_ts": expires_ts,
                    }
                if expired:
                    cur.execute(
                        """
                        DELETE FROM shop_effects
                        WHERE user_id = %s AND effect_key = ANY(%s)
                        """,
                        (user_id, expired),
                    )
                    conn.commit()
        return effects
