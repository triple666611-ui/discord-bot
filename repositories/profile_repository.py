import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg2
from psycopg2.pool import SimpleConnectionPool


@dataclass(slots=True)
class Profile:
    user_id: int
    xp: int
    rep: int
    balance: int


@dataclass(slots=True)
class DailyState:
    last_ts: int | None
    streak_count: int


class ProfileRepository:
    def __init__(self, db_path: Path | None = None):
        # db_path оставлен только для совместимости со старым main.py
        self.db_path = db_path

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL не найден. Добавь PostgreSQL в Railway "
                "и передай переменную окружения DATABASE_URL."
            )

        self.pool = SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=database_url,
        )

        self._setup_db()

    def close(self) -> None:
        if hasattr(self, "pool") and self.pool is not None:
            self.pool.closeall()

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
                    CREATE TABLE IF NOT EXISTS profiles (
                        user_id BIGINT PRIMARY KEY,
                        xp INTEGER NOT NULL DEFAULT 0,
                        rep INTEGER NOT NULL DEFAULT 0,
                        balance INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rep_cooldown (
                        giver_id BIGINT NOT NULL,
                        target_id BIGINT NOT NULL,
                        last_ts BIGINT NOT NULL,
                        PRIMARY KEY (giver_id, target_id)
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_cooldown (
                        user_id BIGINT PRIMARY KEY,
                        last_ts BIGINT NOT NULL,
                        streak_count INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )

                cur.execute(
                    """
                    ALTER TABLE daily_cooldown
                    ADD COLUMN IF NOT EXISTS streak_count INTEGER NOT NULL DEFAULT 0
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_profiles_balance
                    ON profiles (balance DESC, user_id ASC)
                    """
                )

                conn.commit()

    def ensure_profile(self, user_id: int) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO profiles (user_id, xp, rep, balance)
                    VALUES (%s, 0, 0, 0)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id,),
                )
                conn.commit()

    def get_profile(self, user_id: int) -> Profile:
        self.ensure_profile(user_id)

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, xp, rep, balance
                    FROM profiles
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()

        if row is None:
            return Profile(user_id=user_id, xp=0, rep=0, balance=0)

        return Profile(
            user_id=int(row[0]),
            xp=int(row[1]),
            rep=int(row[2]),
            balance=int(row[3]),
        )

    def save_profile(self, profile: Profile) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO profiles (user_id, xp, rep, balance)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        xp = EXCLUDED.xp,
                        rep = EXCLUDED.rep,
                        balance = EXCLUDED.balance
                    """,
                    (
                        profile.user_id,
                        profile.xp,
                        profile.rep,
                        profile.balance,
                    ),
                )
                conn.commit()

    def get_top_balances(self, limit: int = 10) -> list[tuple[int, int]]:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, balance
                    FROM profiles
                    ORDER BY balance DESC, user_id ASC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

        return [(int(row[0]), int(row[1])) for row in rows]

    def get_rep_ts(self, giver_id: int, target_id: int) -> int | None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT last_ts
                    FROM rep_cooldown
                    WHERE giver_id = %s AND target_id = %s
                    """,
                    (giver_id, target_id),
                )
                row = cur.fetchone()

        return int(row[0]) if row else None

    def set_rep_ts(self, giver_id: int, target_id: int, ts: int) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rep_cooldown (giver_id, target_id, last_ts)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (giver_id, target_id)
                    DO UPDATE SET last_ts = EXCLUDED.last_ts
                    """,
                    (giver_id, target_id, ts),
                )
                conn.commit()

    def get_daily_state(self, user_id: int) -> DailyState:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT last_ts, streak_count
                    FROM daily_cooldown
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()

        if row is None:
            return DailyState(last_ts=None, streak_count=0)

        last_ts = int(row[0]) if row[0] is not None else None
        streak_count = int(row[1]) if row[1] is not None else 0
        return DailyState(last_ts=last_ts, streak_count=streak_count)

    def get_daily_ts(self, user_id: int) -> int | None:
        return self.get_daily_state(user_id).last_ts

    def set_daily_state(self, user_id: int, ts: int, streak_count: int) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO daily_cooldown (user_id, last_ts, streak_count)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        last_ts = EXCLUDED.last_ts,
                        streak_count = EXCLUDED.streak_count
                    """,
                    (user_id, ts, streak_count),
                )
                conn.commit()

    def set_daily_ts(self, user_id: int, ts: int) -> None:
        state = self.get_daily_state(user_id)
        self.set_daily_state(user_id, ts, state.streak_count)

    def reset_daily_state(self, user_id: int) -> None:
        self.set_daily_state(user_id, 0, 0)