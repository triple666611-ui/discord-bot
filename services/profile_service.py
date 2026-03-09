import time

from config import Config
from repositories.profile_repository import Profile, ProfileRepository


class ProfileService:
    def __init__(self, repository: ProfileRepository):
        self.repository = repository
        self._profile_cache: dict[int, Profile] = {}

    def get_profile(self, user_id: int) -> Profile:
        cached = self._profile_cache.get(user_id)
        if cached is not None:
            return cached
        profile = self.repository.get_profile(user_id)
        self._profile_cache[user_id] = profile
        return profile

    def save_profile(self, profile: Profile) -> None:
        self.repository.save_profile(profile)
        self._profile_cache[profile.user_id] = profile

    def add_xp(self, user_id: int, amount: int) -> None:
        profile = self.get_profile(user_id)
        profile.xp = max(0, profile.xp + amount)
        self.save_profile(profile)

    def set_xp(self, user_id: int, xp: int) -> None:
        profile = self.get_profile(user_id)
        profile.xp = max(0, xp)
        self.save_profile(profile)

    def add_rep(self, user_id: int, delta: int) -> None:
        profile = self.get_profile(user_id)
        profile.rep += delta
        self.save_profile(profile)

    def set_rep(self, user_id: int, rep: int) -> None:
        profile = self.get_profile(user_id)
        profile.rep = rep
        self.save_profile(profile)

    def add_balance(self, user_id: int, amount: int) -> int:
        profile = self.get_profile(user_id)
        profile.balance = max(0, profile.balance + amount)
        self.save_profile(profile)
        return profile.balance

    def set_balance(self, user_id: int, amount: int) -> int:
        profile = self.get_profile(user_id)
        profile.balance = max(0, amount)
        self.save_profile(profile)
        return profile.balance

    def get_top_balances(self, limit: int = 10) -> list[tuple[int, int]]:
        return self.repository.get_top_balances(limit=limit)

    def can_rep(self, giver_id: int, target_id: int) -> tuple[bool, int]:
        last_ts = self.repository.get_rep_ts(giver_id, target_id)
        if last_ts is None:
            return True, 0
        now = int(time.time())
        left = Config.ECONOMY.REP_COOLDOWN_SEC - (now - last_ts)
        return left <= 0, max(0, left)

    def set_rep_ts(self, giver_id: int, target_id: int) -> None:
        self.repository.set_rep_ts(giver_id, target_id, int(time.time()))

    def can_claim_daily(self, user_id: int) -> tuple[bool, int]:
        last_ts = self.repository.get_daily_ts(user_id)
        if last_ts is None:
            return True, 0
        now = int(time.time())
        left = Config.ECONOMY.DAILY_COOLDOWN_SEC - (now - last_ts)
        return left <= 0, max(0, left)

    def claim_daily(self, user_id: int) -> int:
        self.repository.set_daily_ts(user_id, int(time.time()))
        return self.add_balance(user_id, Config.ECONOMY.DAILY_REWARD)
