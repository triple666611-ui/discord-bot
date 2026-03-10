from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

from config import Config
from repositories.shop_repository import ShopRepository
from services.profile_service import ProfileService

DAY_SECONDS = 24 * 60 * 60
BLACK_MARKET_DISCOUNT = 0.20


@dataclass(slots=True)
class ShopItem:
    key: str
    name: str
    price: int
    category: str
    description: str
    kind: str


@dataclass(slots=True)
class BlackMarketOffer:
    item: ShopItem
    original_price: int
    discounted_price: int


class ShopService:
    def __init__(self, repository: ShopRepository, profile_service: ProfileService):
        self.repository = repository
        self.profile_service = profile_service
        self._items: dict[str, ShopItem] = {
            "color_profile": ShopItem(
                key="color_profile",
                name="🌈 Цветной профиль",
                price=500,
                category="Косметика",
                description="Открывает яркий цветовой стиль для /profile.",
                kind="cosmetic",
            ),
            "custom_bg": ShopItem(
                key="custom_bg",
                name="🖼 Кастомный фон",
                price=2000,
                category="Косметика",
                description="Открывает альтернативный фон профиля.",
                kind="cosmetic",
            ),
            "vip_frame": ShopItem(
                key="vip_frame",
                name="⭐ VIP рамка",
                price=3000,
                category="Косметика",
                description="Открывает золотую VIP-рамку для профиля.",
                kind="cosmetic",
            ),
            "double_win_token": ShopItem(
                key="double_win_token",
                name="🎲 x2 выигрыш",
                price=400,
                category="Бонусы",
                description="Следующая победа в игре даст удвоенную награду.",
                kind="inventory",
            ),
            "vip_slot_ticket": ShopItem(
                key="vip_slot_ticket",
                name="🎰 VIP слот",
                price=1000,
                category="Бонусы",
                description="Следующий /slots гарантирует минимум двойное совпадение.",
                kind="inventory",
            ),
            "small_case": ShopItem(
                key="small_case",
                name="🎁 Малый кейс",
                price=300,
                category="Кейсы",
                description="Случайная награда: монеты или бонус магазина.",
                kind="case",
            ),
            "big_case": ShopItem(
                key="big_case",
                name="💎 Большой кейс",
                price=1000,
                category="Кейсы",
                description="Крупная случайная награда: монеты, бонусы или косметика.",
                kind="case",
            ),
            "role_vip": ShopItem(
                key="role_vip",
                name="💎 Роль VIP",
                price=3000,
                category="Роли",
                description="Выдаёт серверную роль VIP.",
                kind="role",
            ),
            "role_elite": ShopItem(
                key="role_elite",
                name="👑 Роль Elite",
                price=7000,
                category="Роли",
                description="Выдаёт серверную роль Elite.",
                kind="role",
            ),
            "role_legend": ShopItem(
                key="role_legend",
                name="🌟 Роль Legend",
                price=15000,
                category="Роли",
                description="Выдаёт серверную роль Legend.",
                kind="role",
            ),
            "vip_7d": ShopItem(
                key="vip_7d",
                name="💠 VIP 7 дней",
                price=2500,
                category="Подписка",
                description="+50% к /daily и +20% к выигрышам в играх на 7 дней.",
                kind="subscription",
            ),
            "vip_30d": ShopItem(
                key="vip_30d",
                name="🚀 VIP 30 дней",
                price=8000,
                category="Подписка",
                description="+50% к /daily и +20% к выигрышам в играх на 30 дней.",
                kind="subscription",
            ),
            "tournament_ticket": ShopItem(
                key="tournament_ticket",
                name="🏆 Турнирный билет",
                price=500,
                category="Прочее",
                description="Заготовка под будущие турниры сервера.",
                kind="inventory",
            ),
        }

    def get_catalog(self) -> dict[str, list[ShopItem]]:
        groups: dict[str, list[ShopItem]] = {}
        for item in self._items.values():
            groups.setdefault(item.category, []).append(item)
        for values in groups.values():
            values.sort(key=lambda item: item.price)
        return dict(sorted(groups.items(), key=lambda pair: pair[0]))

    def get_all_items(self) -> list[ShopItem]:
        return sorted(self._items.values(), key=lambda item: (item.category, item.price, item.name))

    def get_item(self, item_key: str) -> ShopItem | None:
        return self._items.get(item_key)

    def get_black_market_offers(self) -> list[BlackMarketOffer]:
        day_index = int(time.time() // DAY_SECONDS)
        seed = f"black-market-{day_index}"
        rng = random.Random(seed)
        pool = self.get_all_items()
        sample_size = min(3, len(pool))
        sampled = rng.sample(pool, k=sample_size)
        sampled.sort(key=lambda offer_item: offer_item.price, reverse=True)

        offers: list[BlackMarketOffer] = []
        for item in sampled:
            discounted = max(1, int(round(item.price * (1 - BLACK_MARKET_DISCOUNT))))
            offers.append(
                BlackMarketOffer(
                    item=item,
                    original_price=item.price,
                    discounted_price=discounted,
                )
            )
        return offers

    def get_black_market_offer(self, item_key: str) -> BlackMarketOffer | None:
        for offer in self.get_black_market_offers():
            if offer.item.key == item_key:
                return offer
        return None

    def get_inventory(self, user_id: int) -> dict[str, int]:
        return self.repository.get_inventory(user_id)

    def list_effects(self, user_id: int) -> dict[str, dict[str, Any]]:
        return self.repository.list_effects(user_id)

    def get_profile_style(self, user_id: int) -> dict[str, str | None]:
        effects = self.repository.list_effects(user_id)
        return {
            "theme": effects.get("profile_theme", {}).get("value"),
            "frame": effects.get("profile_frame", {}).get("value"),
        }

    def has_vip(self, user_id: int) -> bool:
        return self.repository.get_effect(user_id, "vip_subscription") is not None

    def get_daily_reward_amount(self, user_id: int) -> int:
        amount = Config.DAILY_REWARD
        if self.has_vip(user_id):
            amount = int(amount * 1.5)
        return amount

    def claim_daily(self, user_id: int) -> int:
        self.profile_service.repository.set_daily_ts(user_id, int(time.time()))
        reward = self.get_daily_reward_amount(user_id)
        return self.profile_service.add_balance(user_id, reward)

    def apply_game_win_bonus(self, user_id: int, base_win: int) -> tuple[int, list[str]]:
        final_win = base_win
        notes: list[str] = []

        double_effect = self.repository.get_effect(user_id, "double_win_armed")
        if double_effect is not None:
            final_win *= 2
            notes.append("🎲 Сработал бустер x2 выигрыша.")
            self.repository.clear_effect(user_id, "double_win_armed")

        if self.has_vip(user_id):
            boosted = int(final_win * 1.2)
            if boosted > final_win:
                final_win = boosted
                notes.append("💠 VIP дал +20% к выигрышу.")

        return final_win, notes

    def consume_vip_slot_effect(self, user_id: int) -> bool:
        effect = self.repository.get_effect(user_id, "vip_slot_armed")
        if effect is None:
            return False
        self.repository.clear_effect(user_id, "vip_slot_armed")
        return True

    def buy_item(self, user_id: int, item_key: str, *, price_override: int | None = None) -> tuple[bool, str, dict[str, Any]]:
        payload: dict[str, Any] = {}
        item = self.get_item(item_key)
        if item is None:
            return False, "❌ Такой предмет не найден.", payload

        final_price = item.price if price_override is None else price_override
        profile = self.profile_service.get_profile(user_id)
        if profile.balance < final_price:
            return False, f"❌ Недостаточно монет. Нужно **{final_price}** 🪙, у тебя **{profile.balance}** 🪙.", payload

        if item.kind == "cosmetic":
            return self._buy_cosmetic(user_id, item, final_price)
        if item.kind == "inventory":
            return self._buy_inventory(user_id, item, final_price)
        if item.kind == "case":
            return self._open_case(user_id, item, final_price)
        if item.kind == "subscription":
            return self._buy_subscription(user_id, item, final_price)
        if item.kind == "role":
            return self._buy_role(user_id, item, final_price)
        return False, "❌ Этот предмет пока недоступен.", payload

    def buy_black_market_item(self, user_id: int, item_key: str) -> tuple[bool, str, dict[str, Any]]:
        offer = self.get_black_market_offer(item_key)
        if offer is None:
            return False, "❌ Этого предмета сейчас нет на чёрном рынке.", {}

        success, message, details = self.buy_item(user_id, item_key, price_override=offer.discounted_price)
        if success:
            details["original_price"] = offer.original_price
            details["discounted_price"] = offer.discounted_price
            details["discount_percent"] = int(BLACK_MARKET_DISCOUNT * 100)
        return success, message, details

    def _buy_cosmetic(self, user_id: int, item: ShopItem, price: int) -> tuple[bool, str, dict[str, Any]]:
        inventory = self.repository.get_inventory(user_id)
        if inventory.get(item.key, 0) > 0:
            return False, "❌ У тебя уже есть этот косметический предмет.", {}

        new_balance = self.profile_service.add_balance(user_id, -price)
        self.repository.add_inventory_item(user_id, item.key, 1)
        details = {
            "balance": new_balance,
            "item": item,
            "paid_price": price,
        }
        return True, f"✅ Куплено: **{item.name}**. Баланс: **{new_balance}** 🪙.", details

    def _buy_inventory(self, user_id: int, item: ShopItem, price: int) -> tuple[bool, str, dict[str, Any]]:
        new_balance = self.profile_service.add_balance(user_id, -price)
        qty = 2 if item.key == "bm_double_bundle" else 1
        inventory_key = "double_win_token" if item.key == "bm_double_bundle" else item.key
        self.repository.add_inventory_item(user_id, inventory_key, qty)
        details = {
            "balance": new_balance,
            "item": item,
            "quantity": qty,
            "inventory_key": inventory_key,
            "paid_price": price,
        }
        qty_text = f" x{qty}" if qty > 1 else ""
        return True, f"✅ Куплено: **{item.name}{qty_text}**. Баланс: **{new_balance}** 🪙.", details

    def _buy_role(self, user_id: int, item: ShopItem, price: int) -> tuple[bool, str, dict[str, Any]]:
        inventory = self.repository.get_inventory(user_id)
        if inventory.get(item.key, 0) > 0:
            return False, "❌ Эта роль уже куплена для твоего аккаунта.", {}

        role_key_map = {
            "role_vip": Config.SHOP.VIP_ROLE_ID,
            "role_elite": Config.SHOP.ELITE_ROLE_ID,
            "role_legend": Config.SHOP.LEGEND_ROLE_ID,
        }
        role_id = role_key_map.get(item.key, 0)
        if not role_id:
            return False, f"❌ Для **{item.name}** ещё не указан role ID в config.py.", {}

        new_balance = self.profile_service.add_balance(user_id, -price)
        self.repository.add_inventory_item(user_id, item.key, 1)
        return True, f"✅ Покупка роли **{item.name}** оформлена. Баланс: **{new_balance}** 🪙.", {
            "balance": new_balance,
            "item": item,
            "role_id": role_id,
            "paid_price": price,
        }

    def _buy_subscription(self, user_id: int, item: ShopItem, price: int) -> tuple[bool, str, dict[str, Any]]:
        new_balance = self.profile_service.add_balance(user_id, -price)
        extend_days = 7 if item.key == "vip_7d" else 30
        expires_ts = self.repository.extend_effect(
            user_id,
            "vip_subscription",
            item.name,
            extend_days * DAY_SECONDS,
        )
        return True, f"✅ Активирован **{item.name}**. Баланс: **{new_balance}** 🪙.", {
            "balance": new_balance,
            "item": item,
            "expires_ts": expires_ts,
            "paid_price": price,
        }

    def _open_case(self, user_id: int, item: ShopItem, price: int) -> tuple[bool, str, dict[str, Any]]:
        new_balance = self.profile_service.add_balance(user_id, -price)

        rewards_small = (
            ("coins", 120),
            ("coins", 200),
            ("coins", 350),
            ("item", "double_win_token"),
            ("item", "tournament_ticket"),
        )
        rewards_big = (
            ("coins", 600),
            ("coins", 900),
            ("coins", 1500),
            ("item", "double_win_token"),
            ("item", "vip_slot_ticket"),
            ("item", "color_profile"),
            ("item", "vip_frame"),
        )

        if item.key == "small_case":
            reward = random.choice(rewards_small)
        else:
            reward = random.choice(rewards_big)

        details: dict[str, Any] = {
            "balance": new_balance,
            "item": item,
            "paid_price": price,
        }

        if reward[0] == "coins":
            amount = int(reward[1])
            new_balance = self.profile_service.add_balance(user_id, amount)
            details["balance"] = new_balance
            details["reward_text"] = f"**+{amount}** 🪙"
            return True, f"🎁 Открыт **{item.name}**. Награда: **+{amount}** 🪙. Баланс: **{new_balance}** 🪙.", details

        reward_item = self.get_item(str(reward[1]))
        if reward_item is None:
            reward_item = ShopItem(str(reward[1]), str(reward[1]), 0, "Награда", "", "inventory")
        self.repository.add_inventory_item(user_id, reward_item.key, 1)
        details["reward_text"] = reward_item.name
        return True, f"🎁 Открыт **{item.name}**. Ты получил предмет: {reward_item.name}. Баланс: **{new_balance}** 🪙.", details

    def use_item(self, user_id: int, item_key: str) -> tuple[bool, str]:
        inventory = self.repository.get_inventory(user_id)
        if inventory.get(item_key, 0) <= 0:
            return False, "❌ Этого предмета нет в инвентаре."

        if item_key == "color_profile":
            self.repository.set_effect(user_id, "profile_theme", "Цветной профиль")
            return True, "✅ Активирован стиль **Цветной профиль**."

        if item_key == "custom_bg":
            self.repository.set_effect(user_id, "profile_theme", "Кастомный фон")
            return True, "✅ Активирован стиль **Кастомный фон**."

        if item_key == "vip_frame":
            self.repository.set_effect(user_id, "profile_frame", "VIP рамка")
            return True, "✅ Активирована **VIP рамка**."

        if item_key == "double_win_token":
            if not self.repository.consume_inventory_item(user_id, item_key, 1):
                return False, "❌ Не удалось активировать бустер x2."
            self.repository.set_effect(user_id, "double_win_armed", "Следующая победа x2")
            return True, "✅ Следующая победа в игре будет умножена на x2."

        if item_key == "vip_slot_ticket":
            if not self.repository.consume_inventory_item(user_id, item_key, 1):
                return False, "❌ Не удалось активировать VIP слот."
            self.repository.set_effect(user_id, "vip_slot_armed", "VIP слот готов")
            return True, "✅ Следующий /slots гарантирует минимум двойное совпадение."

        if item_key == "tournament_ticket":
            return True, "🎟 Турнирный билет сохранён. Его можно будет использовать, когда появятся турниры."

        if item_key in {"role_vip", "role_elite", "role_legend"}:
            return False, "❌ Роль активируется сразу после покупки и не используется вручную."

        return False, "❌ Этот предмет нельзя использовать вручную."