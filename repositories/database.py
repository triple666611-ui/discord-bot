import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Profile:
    user_id: int
    xp: int
    rep: int
    balance: int


class ProfileRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._setup_db()

    def close(self) -> None:
        self.db.close()

    def _setup_db(self) -> None:
        self.db.execute('PRAGMA foreign_keys = ON;')
        self.db.execute('PRAGMA journal_mode = WAL;')
        self.db.execute('PRAGMA synchronous = NORMAL;')
        self.db.execute('CREATE TABLE IF NOT EXISTS profiles (user_id INTEGER PRIMARY KEY, xp INTEGER NOT NULL DEFAULT 0, rep INTEGER NOT NULL DEFAULT 0, balance INTEGER NOT NULL DEFAULT 0)')
        self.db.execute('CREATE TABLE IF NOT EXISTS rep_cooldown (giver_id INTEGER NOT NULL, target_id INTEGER NOT NULL, last_ts INTEGER NOT NULL, PRIMARY KEY (giver_id, target_id))')
        self.db.execute('CREATE TABLE IF NOT EXISTS daily_cooldown (user_id INTEGER PRIMARY KEY, last_ts INTEGER NOT NULL)')
        self.db.commit()

    def ensure_profile(self, user_id: int) -> None:
        self.db.execute('INSERT OR IGNORE INTO profiles (user_id, xp, rep, balance) VALUES (?, 0, 0, 0)', (user_id,))
        self.db.commit()

    def get_profile(self, user_id: int) -> Profile:
        self.ensure_profile(user_id)
        row = self.db.execute('SELECT user_id, xp, rep, balance FROM profiles WHERE user_id = ?', (user_id,)).fetchone()
        return Profile(int(row['user_id']), int(row['xp']), int(row['rep']), int(row['balance']))

    def save_profile(self, profile: Profile) -> None:
        self.db.execute('INSERT INTO profiles (user_id, xp, rep, balance) VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET xp = excluded.xp, rep = excluded.rep, balance = excluded.balance', (profile.user_id, profile.xp, profile.rep, profile.balance))
        self.db.commit()

    def get_top_balances(self, limit: int = 10) -> list[tuple[int, int]]:
        rows = self.db.execute('SELECT user_id, balance FROM profiles ORDER BY balance DESC, user_id ASC LIMIT ?', (limit,)).fetchall()
        return [(int(row['user_id']), int(row['balance'])) for row in rows]

    def get_rep_ts(self, giver_id: int, target_id: int) -> int | None:
        row = self.db.execute('SELECT last_ts FROM rep_cooldown WHERE giver_id = ? AND target_id = ?', (giver_id, target_id)).fetchone()
        return int(row['last_ts']) if row else None

    def set_rep_ts(self, giver_id: int, target_id: int, ts: int) -> None:
        self.db.execute('INSERT INTO rep_cooldown (giver_id, target_id, last_ts) VALUES (?, ?, ?) ON CONFLICT(giver_id, target_id) DO UPDATE SET last_ts = excluded.last_ts', (giver_id, target_id, ts))
        self.db.commit()

    def get_daily_ts(self, user_id: int) -> int | None:
        row = self.db.execute('SELECT last_ts FROM daily_cooldown WHERE user_id = ?', (user_id,)).fetchone()
        return int(row['last_ts']) if row else None

    def set_daily_ts(self, user_id: int, ts: int) -> None:
        self.db.execute('INSERT INTO daily_cooldown (user_id, last_ts) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET last_ts = excluded.last_ts', (user_id, ts))
        self.db.commit()
