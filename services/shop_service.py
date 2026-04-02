from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any

from config import Config
from repositories.shop_repository import ShopRepository
from services.profile_service import ProfileService

DAY_SECONDS = 24 * 60 * 60

PROFILE_COLOR_PRESETS: dict[str, dict[str, str]] = {
    "violet": {"label": "Violet", "emoji": "🟣"},
    "emerald": {"label": "Emerald", "emoji": "🟢"},
    "ruby": {"label": "Ruby", "emoji": "🔴"},
    "ocean": {"label": "Ocean", "emoji": "🔵"},
    "sunset": {"label": "Sunset", "emoji": "🟠"},
    "gold": {"label": "Gold", "emoji": "🟡"},
    "pink": {"label": "Pink", "emoji": "🌸"},
    "ice": {"label": "Ice", "emoji": "💠"},
}


@dataclass(slots=True)
class ShopItem:
    key: str
    name: str
    price: int
    category: str
    description: str
    kind: str


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

    def get_item(self, item_key: str) -> ShopItem | None:
        if item_key == "black_market_offer":
            return self.get_black_market_offer()
        return self._items.get(item_key)

    def get_black_market_offer(self) -> ShopItem:
        offer_pool = (
            ShopItem(
                key="bm_shadow_frame",
                name="🕶 Теневая рамка",
                price=2200,
                category="Чёрный рынок",
                description="Редкая тёмная рамка профиля только на сегодня.",
                kind="cosmetic",
            ),
            ShopItem(
                key="bm_lucky_case",
                name="🎲 Контрабандный кейс",
                price=850,
                category="Чёрный рынок",
                description="Редкий кейс с повышенным шансом на косметику.",
                kind="case",
            ),
            ShopItem(
                key="bm_double_bundle",
                name="⚡ Пачка x2 бустеров",
                price=700,
                category="Чёрный рынок",
                description="Сразу 2 жетона удвоенного выигрыша.",
                kind="inventory",
            ),
        )
        day_index = int(time.time() // DAY_SECONDS)
        return offer_pool[day_index % len(offer_pool)]

    def get_inventory(self, user_id: int) -> dict[str, int]:
        return self.repository.get_inventory(user_id)

    def get_inventory_display_items(self, user_id: int) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for item_key, qty in self.repository.get_inventory(user_id).items():
            item = self.get_item(item_key)
            items.append(
                {
                    "key": item_key,
                    "quantity": qty,
                    "item": item,
                }
            )
        return items

    def list_effects(self, user_id: int) -> dict[str, dict[str, Any]]:
        return self.repository.list_effects(user_id)

    def get_profile_style(self, user_id: int) -> dict[str, str | None]:
        effects = self.repository.list_effects(user_id)
        return {
            "theme": effects.get("profile_theme", {}).get("value"),
            "frame": effects.get("profile_frame", {}).get("value"),
            "color": effects.get("profile_color", {}).get("value"),
        }

    def get_active_cosmetics(self, user_id: int) -> dict[str, str | None]:
        style = self.get_profile_style(user_id)
        active_theme = None
        active_frame = None

        if style.get("theme") == "color":
            active_theme = "color_profile"
        elif style.get("theme") == "custom_bg":
            active_theme = "custom_bg"

        if style.get("frame") == "vip":
            active_frame = "vip_frame"
        elif style.get("frame") == "shadow":
            active_frame = "bm_shadow_frame"

        return {
            "theme": active_theme,
            "frame": active_frame,
        }

    def get_profile_color_presets(self) -> dict[str, dict[str, str]]:
        return PROFILE_COLOR_PRESETS

    def get_profile_color_label(self, color_key: str | None) -> str:
        if color_key is None:
            return PROFILE_COLOR_PRESETS["violet"]["label"]
        preset = PROFILE_COLOR_PRESETS.get(color_key)
        if preset is None:
            return color_key.replace("_", " ").title()
        return preset["label"]

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

    def buy_item(self, user_id: int, item_key: str) -> tuple[bool, str, dict[str, Any]]:
        payload: dict[str, Any] = {}
        item = self.get_item(item_key)
        if item is None:
            return False, "❌ Такой предмет не найден.", payload

        profile = self.profile_service.get_profile(user_id)
        if profile.balance < item.price:
            return False, f"❌ Недостаточно монет. Нужно **{item.price}** 🪙, у тебя **{profile.balance}** 🪙.", payload

        if item.kind == "cosmetic":
            return self._buy_cosmetic(user_id, item)
        if item.kind == "inventory":
            return self._buy_inventory(user_id, item)
        if item.kind == "case":
            return self._open_case(user_id, item)
        if item.kind == "subscription":
            return self._buy_subscription(user_id, item)
        if item.kind == "role":
            return self._buy_role(user_id, item)
        return False, "❌ Этот предмет пока недоступен.", payload

    def _buy_cosmetic(self, user_id: int, item: ShopItem) -> tuple[bool, str, dict[str, Any]]:
        inventory = self.repository.get_inventory(user_id)
        if inventory.get(item.key, 0) > 0:
            return False, "❌ У тебя уже есть этот косметический предмет.", {}

        new_balance = self.profile_service.add_balance(user_id, -item.price)
        self.repository.add_inventory_item(user_id, item.key, 1)
        details = {
            "balance": new_balance,
            "item": item,
        }
        return True, f"✅ Куплено: **{item.name}**. Баланс: **{new_balance}** 🪙.", details

    def _buy_inventory(self, user_id: int, item: ShopItem) -> tuple[bool, str, dict[str, Any]]:
        new_balance = self.profile_service.add_balance(user_id, -item.price)
        qty = 2 if item.key == "bm_double_bundle" else 1
        inventory_key = "double_win_token" if item.key == "bm_double_bundle" else item.key
        self.repository.add_inventory_item(user_id, inventory_key, qty)
        details = {
            "balance": new_balance,
            "item": item,
            "quantity": qty,
            "inventory_key": inventory_key,
        }
        qty_text = f" x{qty}" if qty > 1 else ""
        return True, f"✅ Куплено: **{item.name}{qty_text}**. Баланс: **{new_balance}** 🪙.", details

    def _buy_role(self, user_id: int, item: ShopItem) -> tuple[bool, str, dict[str, Any]]:
        role_key_map = {
            "role_vip": Config.SHOP.VIP_ROLE_ID,
            "role_elite": Config.SHOP.ELITE_ROLE_ID,
            "role_legend": Config.SHOP.LEGEND_ROLE_ID,
        }
        role_id = role_key_map.get(item.key, 0)
        if not role_id:
            return False, f"❌ Для **{item.name}** ещё не указан role ID в config.py.", {}

        new_balance = self.profile_service.add_balance(user_id, -item.price)
        return True, f"✅ Покупка роли **{item.name}** оформлена. Баланс: **{new_balance}** 🪙.", {
            "balance": new_balance,
            "item": item,
            "role_id": role_id,
        }

    def _buy_subscription(self, user_id: int, item: ShopItem) -> tuple[bool, str, dict[str, Any]]:
        new_balance = self.profile_service.add_balance(user_id, -item.price)
        extend_days = 7 if item.key == "vip_7d" else 30
        expires_ts = self.repository.extend_effect(
            user_id,
            "vip_subscription",
            "active",
            extend_days * DAY_SECONDS,
        )
        return True, f"✅ Активирован **{item.name}**. Баланс: **{new_balance}** 🪙.", {
            "balance": new_balance,
            "item": item,
            "expires_ts": expires_ts,
        }

    def _open_case(self, user_id: int, item: ShopItem) -> tuple[bool, str, dict[str, Any]]:
        new_balance = self.profile_service.add_balance(user_id, -item.price)

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
        rewards_black = (
            ("coins", 500),
            ("coins", 1200),
            ("item", "double_win_token"),
            ("item", "custom_bg"),
            ("item", "vip_frame"),
        )

        if item.key == "small_case":
            reward = random.choice(rewards_small)
        elif item.key == "big_case":
            reward = random.choice(rewards_big)
        else:
            reward = random.choice(rewards_black)

        details: dict[str, Any] = {
            "balance": new_balance,
            "item": item,
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
            self.repository.set_effect(user_id, "profile_theme", "color")
            if self.repository.get_effect(user_id, "profile_color") is None:
                self.repository.set_effect(user_id, "profile_color", "violet")
            return True, "✅ Цветной профиль активирован. Теперь можно выбрать цвет в меню ниже."

        if item_key == "custom_bg":
            self.repository.set_effect(user_id, "profile_theme", "custom_bg")
            return True, "✅ Активирован стиль **Кастомный фон**. Изменения уже видны в `/profile`."

        if item_key == "vip_frame":
            self.repository.set_effect(user_id, "profile_frame", "vip")
            return True, "✅ Активирована **VIP рамка**. Изменения уже видны в `/profile`."

        if item_key == "bm_shadow_frame":
            self.repository.set_effect(user_id, "profile_frame", "shadow")
            return True, "✅ Активирована **Теневая рамка**. Изменения уже видны в `/profile`."

        if item_key == "double_win_token":
            if not self.repository.consume_inventory_item(user_id, item_key, 1):
                return False, "❌ Не удалось активировать бустер x2."
            self.repository.set_effect(user_id, "double_win_armed", "active")
            return True, "✅ Следующая победа в игре будет умножена на x2."

        if item_key == "vip_slot_ticket":
            if not self.repository.consume_inventory_item(user_id, item_key, 1):
                return False, "❌ Не удалось активировать VIP слот."
            self.repository.set_effect(user_id, "vip_slot_armed", "active")
            return True, "✅ Следующий /slots гарантирует минимум двойное совпадение."

        if item_key == "tournament_ticket":
            return True, "🎟 Турнирный билет сохранён. Его можно будет использовать, когда появятся турниры."

        return False, "❌ Этот предмет нельзя использовать вручную."

    def set_profile_color(self, user_id: int, color_key: str) -> tuple[bool, str]:
        if color_key not in PROFILE_COLOR_PRESETS:
            return False, "❌ Такого цвета профиля нет в списке."

        inventory = self.repository.get_inventory(user_id)
        if inventory.get("color_profile", 0) <= 0:
            return False, "❌ Сначала нужно купить цветной профиль."

        if self.get_profile_style(user_id).get("theme") != "color":
            self.repository.set_effect(user_id, "profile_theme", "color")

        self.repository.set_effect(user_id, "profile_color", color_key)
        label = self.get_profile_color_label(color_key)
        return True, f"✅ Цвет профиля изменён на **{label}**. Новый вид уже доступен в `/profile`."

    def deactivate_item(self, user_id: int, item_key: str) -> tuple[bool, str]:
        inventory = self.repository.get_inventory(user_id)
        if inventory.get(item_key, 0) <= 0:
            return False, "❌ Этого предмета нет в инвентаре."

        if item_key in {"color_profile", "custom_bg"}:
            current_theme = self.get_profile_style(user_id).get("theme")
            expected_theme = "color" if item_key == "color_profile" else "custom_bg"
            if current_theme != expected_theme:
                return False, "❌ Этот стиль сейчас не активирован."
            self.repository.clear_effect(user_id, "profile_theme")
            if item_key == "color_profile":
                self.repository.clear_effect(user_id, "profile_color")
            return True, "✅ Фоновая кастомизация профиля отключена."

        if item_key in {"vip_frame", "bm_shadow_frame"}:
            current_frame = self.get_profile_style(user_id).get("frame")
            expected_frame = "vip" if item_key == "vip_frame" else "shadow"
            if current_frame != expected_frame:
                return False, "❌ Эта рамка сейчас не активирована."
            self.repository.clear_effect(user_id, "profile_frame")
            return True, "✅ Рамка профиля отключена."

        return False, "❌ Этот предмет нельзя деактивировать через магазин."

    def admin_remove_inventory_item(self, user_id: int, item_key: str, quantity: int | None = None) -> tuple[bool, str, dict[str, Any]]:
        inventory = self.repository.get_inventory(user_id)
        current_qty = inventory.get(item_key, 0)
        if current_qty <= 0:
            return False, "❌ У пользователя нет этого предмета в инвентаре.", {}

        removed_qty = self.repository.remove_inventory_item(user_id, item_key, quantity)
        if removed_qty <= 0:
            return False, "❌ Не удалось удалить предмет из инвентаря.", {}

        remaining_qty = max(current_qty - removed_qty, 0)
        self._cleanup_item_effects(user_id, item_key, remaining_qty)
        item = self.get_item(item_key)
        item_name = item.name if item is not None else item_key
        return True, f"✅ Удалено **{removed_qty}** шт. предмета **{item_name}**.", {
            "item_key": item_key,
            "item_name": item_name,
            "removed_quantity": removed_qty,
            "remaining_quantity": remaining_qty,
        }

    def admin_clear_inventory(self, user_id: int) -> tuple[bool, str, dict[str, Any]]:
        inventory = self.repository.get_inventory(user_id)
        if not inventory:
            removed_effects = self.repository.clear_effects(user_id)
            if removed_effects > 0:
                return True, "✅ Инвентарь уже был пуст, но активные shop-эффекты пользователя очищены.", {
                    "removed_total": 0,
                    "removed_unique_items": 0,
                    "removed_effects": removed_effects,
                }
            return False, "❌ Инвентарь пользователя уже пуст.", {}

        removed_total = self.repository.clear_inventory(user_id)
        removed_effects = self.repository.clear_effects(user_id)
        unique_items = len(inventory)
        return True, "✅ Инвентарь пользователя полностью очищен.", {
            "removed_total": removed_total,
            "removed_unique_items": unique_items,
            "removed_effects": removed_effects,
        }

    def _cleanup_item_effects(self, user_id: int, item_key: str, remaining_qty: int) -> None:
        if item_key == "color_profile" and remaining_qty <= 0:
            self.repository.clear_effect(user_id, "profile_theme")
            self.repository.clear_effect(user_id, "profile_color")
        elif item_key == "custom_bg" and remaining_qty <= 0:
            if self.get_profile_style(user_id).get("theme") == "custom_bg":
                self.repository.clear_effect(user_id, "profile_theme")
        elif item_key in {"vip_frame", "bm_shadow_frame"} and remaining_qty <= 0:
            expected_frame = "vip" if item_key == "vip_frame" else "shadow"
            if self.get_profile_style(user_id).get("frame") == expected_frame:
                self.repository.clear_effect(user_id, "profile_frame")
        elif item_key == "double_win_token" and remaining_qty <= 0:
            self.repository.clear_effect(user_id, "double_win_armed")
        elif item_key == "vip_slot_ticket" and remaining_qty <= 0:
            self.repository.clear_effect(user_id, "vip_slot_armed")

