from __future__ import annotations

import datetime as dt
from typing import Any, cast

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from services.shop_service import BlackMarketOffer, ShopItem


def format_relative_duration(expires_ts: int | None) -> str:
    if expires_ts is None:
        return "навсегда"

    now = int(dt.datetime.now().timestamp())
    remaining = max(0, expires_ts - now)
    if remaining <= 0:
        return "истекло"

    days, rem = divmod(remaining, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days} д.")
    if hours:
        parts.append(f"{hours} ч.")
    if minutes and len(parts) < 2:
        parts.append(f"{minutes} мин.")
    return " ".join(parts) if parts else "меньше минуты"


class BaseShopView(discord.ui.View):
    def __init__(self, cog: "ShopCog", owner_id: int, *, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ Это меню доступно только тому, кто открыл магазин.",
                ephemeral=True,
            )
            return False
        return True


class MainShopView(BaseShopView):
    @discord.ui.button(label="Каталог", style=discord.ButtonStyle.primary, emoji="🛍️")
    async def open_catalog(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        embed = self.cog.build_catalog_embed(interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=CatalogView(self.cog, self.owner_id))

    @discord.ui.button(label="Инвентарь", style=discord.ButtonStyle.success, emoji="🎒")
    async def open_inventory(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        embed = self.cog.build_inventory_embed(interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=InventoryView(self.cog, self.owner_id))

    @discord.ui.button(label="Чёрный рынок", style=discord.ButtonStyle.danger, emoji="🕶️")
    async def open_black_market(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        embed = self.cog.build_black_market_embed(interaction.user.id)
        await interaction.response.edit_message(embed=embed, view=BlackMarketView(self.cog, self.owner_id))


class CatalogSelect(discord.ui.Select):
    def __init__(self, cog: "ShopCog"):
        self.cog = cog
        options = [
            discord.SelectOption(
                label=item.name[:100],
                value=item.key,
                description=f"{item.category} • {item.price} монет"[:100],
            )
            for item in cog.shop_service.get_all_items()[:25]
        ]
        super().__init__(placeholder="Выбери предмет для покупки", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        item = self.cog.shop_service.get_item(self.values[0])
        if item is None:
            await interaction.response.send_message("❌ Предмет не найден.", ephemeral=True)
            return

        embed = self.cog.build_confirm_embed(interaction.user.id, item)
        await interaction.response.edit_message(
            embed=embed,
            view=ConfirmPurchaseView(self.cog, interaction.user.id, item, source="catalog"),
        )


class CatalogView(BaseShopView):
    def __init__(self, cog: "ShopCog", owner_id: int):
        super().__init__(cog, owner_id)
        self.add_item(CatalogSelect(cog))

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_to_main(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=self.cog.build_main_embed(interaction.user.id),
            view=MainShopView(self.cog, self.owner_id),
        )


class InventorySelect(discord.ui.Select):
    def __init__(self, cog: "ShopCog", user_id: int):
        self.cog = cog
        inventory = cog.shop_service.get_inventory(user_id)
        effects = cog.shop_service.list_effects(user_id)

        options: list[discord.SelectOption] = []

        current_theme = effects.get("profile_theme", {}).get("value")
        current_frame = effects.get("profile_frame", {}).get("value")

        for item_key, qty in inventory.items():
            item = cog.shop_service.get_item(item_key)
            if item is None:
                continue

            if item.key == "color_profile":
                desc = "Деактивировать" if current_theme == "color_profile" else "Активировать"
                options.append(
                    discord.SelectOption(
                        label=item.name[:100],
                        value=item.key,
                        description=desc[:100],
                    )
                )
            elif item.key == "custom_bg":
                desc = "Деактивировать" if current_theme == "custom_bg" else "Активировать"
                options.append(
                    discord.SelectOption(
                        label=item.name[:100],
                        value=item.key,
                        description=desc[:100],
                    )
                )
            elif item.key == "vip_frame":
                desc = "Деактивировать" if current_frame == "vip_frame" else "Активировать"
                options.append(
                    discord.SelectOption(
                        label=item.name[:100],
                        value=item.key,
                        description=desc[:100],
                    )
                )
            elif item.key in {"double_win_token", "vip_slot_ticket"}:
                desc = f"Использовать • осталось {qty}"
                options.append(
                    discord.SelectOption(
                        label=item.name[:100],
                        value=item.key,
                        description=desc[:100],
                    )
                )

        if not options:
            options.append(
                discord.SelectOption(
                    label="Нет доступных действий",
                    value="__empty__",
                    description="Косметика или используемые предметы отсутствуют",
                )
            )

        super().__init__(
            placeholder="Выбери предмет для действия",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0]
        if selected == "__empty__":
            await interaction.response.defer()
            return

        success, message = self.cog.shop_service.use_item(interaction.user.id, selected)

        result_embed = discord.Embed(
            title="🎒 Управление инвентарём",
            description=message,
            color=discord.Color.green() if success else discord.Color.red(),
        )

        await interaction.response.edit_message(
            embed=self.cog.build_inventory_embed(interaction.user.id, notice_embed=result_embed),
            view=InventoryView(self.cog, interaction.user.id),
        )


class InventoryView(BaseShopView):
    def __init__(self, cog: "ShopCog", owner_id: int):
        super().__init__(cog, owner_id)

        inventory = cog.shop_service.get_inventory(owner_id)
        actionable_keys = {"color_profile", "custom_bg", "vip_frame", "double_win_token", "vip_slot_ticket"}

        if any(key in actionable_keys for key in inventory):
            self.add_item(InventorySelect(cog, owner_id))

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.primary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=self.cog.build_inventory_embed(interaction.user.id),
            view=InventoryView(self.cog, self.owner_id),
        )

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_to_main(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=self.cog.build_main_embed(interaction.user.id),
            view=MainShopView(self.cog, self.owner_id),
        )


class BlackMarketSelect(discord.ui.Select):
    def __init__(self, cog: "ShopCog"):
        self.cog = cog
        offers = cog.shop_service.get_black_market_offers()
        options = [
            discord.SelectOption(
                label=offer.item.name[:100],
                value=offer.item.key,
                description=f"{offer.original_price} → {offer.discounted_price} монет"[:100],
            )
            for offer in offers
        ]
        super().__init__(placeholder="Выбери предмет с чёрного рынка", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        offer = self.cog.shop_service.get_black_market_offer(self.values[0])
        if offer is None:
            await interaction.response.send_message(
                "❌ Этот лот уже недоступен. Попробуй открыть рынок заново.",
                ephemeral=True,
            )
            return

        embed = self.cog.build_black_market_confirm_embed(interaction.user.id, offer)
        await interaction.response.edit_message(
            embed=embed,
            view=ConfirmPurchaseView(self.cog, interaction.user.id, offer.item, source="black_market"),
        )


class BlackMarketView(BaseShopView):
    def __init__(self, cog: "ShopCog", owner_id: int):
        super().__init__(cog, owner_id)
        self.add_item(BlackMarketSelect(cog))

    @discord.ui.button(label="Обновить", style=discord.ButtonStyle.primary, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=self.cog.build_black_market_embed(interaction.user.id),
            view=BlackMarketView(self.cog, self.owner_id),
        )

    @discord.ui.button(label="Назад", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_to_main(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=self.cog.build_main_embed(interaction.user.id),
            view=MainShopView(self.cog, self.owner_id),
        )


class ConfirmPurchaseView(BaseShopView):
    def __init__(self, cog: "ShopCog", owner_id: int, item: ShopItem, *, source: str):
        super().__init__(cog, owner_id)
        self.item = item
        self.source = source

    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.source == "black_market":
            success, message, details = self.cog.shop_service.buy_black_market_item(interaction.user.id, self.item.key)
        else:
            success, message, details = self.cog.shop_service.buy_item(interaction.user.id, self.item.key)

        if not success:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="❌ Покупка не выполнена",
                    description=message,
                    color=discord.Color.red(),
                ),
                view=self._return_view(),
            )
            return

        embed = self.cog.build_purchase_result_embed(message, details)

        role_id = details.get("role_id")
        if role_id and interaction.guild:
            role = interaction.guild.get_role(int(role_id))
            member = interaction.guild.get_member(interaction.user.id)

            if role is None:
                embed.add_field(name="Роль", value=f"ID {role_id} не найден на сервере.", inline=False)
            elif member is None:
                embed.add_field(name="Роль", value="Пользователь не найден на сервере.", inline=False)
            else:
                try:
                    await member.add_roles(role, reason="Покупка роли в /shop")
                    embed.add_field(name="Роль", value=f"Выдана роль {role.mention}", inline=False)
                except discord.Forbidden:
                    embed.add_field(
                        name="Роль",
                        value="Нет прав для выдачи роли. Проверь позицию роли бота.",
                        inline=False,
                    )
                except discord.HTTPException:
                    embed.add_field(
                        name="Роль",
                        value="Не удалось выдать роль из-за ошибки Discord API.",
                        inline=False,
                    )

        await interaction.response.edit_message(embed=embed, view=self._return_view())

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.source == "black_market":
            await interaction.response.edit_message(
                embed=self.cog.build_black_market_embed(interaction.user.id),
                view=BlackMarketView(self.cog, self.owner_id),
            )
            return

        await interaction.response.edit_message(
            embed=self.cog.build_catalog_embed(interaction.user.id),
            view=CatalogView(self.cog, self.owner_id),
        )

    def _return_view(self) -> discord.ui.View:
        if self.source == "black_market":
            return BlackMarketView(self.cog, self.owner_id)
        return CatalogView(self.cog, self.owner_id)


class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.profile_service = cast(Any, bot).profile_service
        self.shop_service = cast(Any, bot).shop_service

    def build_main_embed(self, user_id: int) -> discord.Embed:
        profile = self.profile_service.get_profile(user_id)
        embed = discord.Embed(
            title="🛒 Магазин сервера",
            description=(
                "Добро пожаловать в магазин сервера.\n\n"
                "**Разделы:**\n"
                "🛍️ Каталог — весь ассортимент магазина\n"
                "🎒 Инвентарь — купленные и активные предметы\n"
                "🕶️ Чёрный рынок — 3 случайных товара со скидкой 20%"
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Твой баланс", value=f"**{profile.balance}** 🪙", inline=True)
        embed.add_field(name="Обновление чёрного рынка", value="Каждые **24 часа**", inline=True)
        embed.set_footer(text="Приятных покупок! Если возникнут вопросы, пиши в поддержку через репорт канал")
        return embed

    def build_catalog_embed(self, user_id: int) -> discord.Embed:
        profile = self.profile_service.get_profile(user_id)
        embed = discord.Embed(
            title="🛍️ Каталог магазина",
            description=f"Выбери предмет в меню ниже. Текущий баланс: **{profile.balance}** 🪙",
            color=discord.Color.blurple(),
        )
        for category, items in self.shop_service.get_catalog().items():
            lines = [f"**{item.name}** — {item.price} 🪙\n{item.description}" for item in items]
            embed.add_field(name=category, value="\n\n".join(lines), inline=False)
        embed.set_footer(text="После выбора предмета появится отдельное подтверждение покупки")
        return embed

    def build_inventory_embed(self, user_id: int, notice_embed: discord.Embed | None = None) -> discord.Embed:
        inventory = self.shop_service.get_inventory(user_id)
        effects = self.shop_service.list_effects(user_id)
        profile = self.profile_service.get_profile(user_id)

        embed = discord.Embed(
            title="🎒 Твой инвентарь",
            description=f"Баланс: **{profile.balance}** 🪙",
            color=discord.Color.green(),
        )

        purchased_lines: list[str] = []
        for item_key, qty in inventory.items():
            item = self.shop_service.get_item(item_key)
            item_name = item.name if item is not None else item_key
            suffix = f" ×{qty}" if qty > 1 else ""
            purchased_lines.append(f"• {item_name}{suffix}")

        embed.add_field(
            name="Купленные предметы",
            value="\n".join(purchased_lines) if purchased_lines else "Пока ничего не куплено.",
            inline=False,
        )

        effect_names = {
            "vip_subscription": "💠 VIP подписка",
            "profile_theme": "🎨 Активный стиль профиля",
            "profile_frame": "🖼️ Активная рамка",
            "double_win_armed": "🎲 Бустер x2",
            "vip_slot_armed": "🎰 VIP слот",
        }

        value_names = {
            "color_profile": "Цветной профиль",
            "custom_bg": "Кастомный фон",
            "vip_frame": "VIP рамка",
        }

        active_lines: list[str] = []
        for effect_key, effect_data in effects.items():
            label = effect_names.get(effect_key, effect_key)
            raw_value = effect_data.get("value")
            value = value_names.get(str(raw_value), str(raw_value if raw_value is not None else "активно"))
            ttl = format_relative_duration(effect_data.get("expires_ts"))

            active_lines.append(
                f"• {label}: **{value}** — пропадет через **{ttl}**"
                if ttl != "навсегда"
                else f"• {label}: **{value}** — **навсегда**"
            )

        embed.add_field(
            name="Активированные предметы",
            value="\n".join(active_lines) if active_lines else "Сейчас нет активных предметов.",
            inline=False,
        )

        if notice_embed is not None:
            embed.add_field(
                name="Последнее действие",
                value=notice_embed.description or "Действие выполнено.",
                inline=False,
            )

        embed.set_footer(text="В меню ниже можно активировать или деактивировать косметику")
        return embed

    def build_black_market_embed(self, user_id: int) -> discord.Embed:
        profile = self.profile_service.get_profile(user_id)
        offers = self.shop_service.get_black_market_offers()
        embed = discord.Embed(
            title="🕶️ Чёрный рынок",
            description=(
                f"Здесь каждый день появляются **3 случайных предложения**.\n"
                f"Баланс: **{profile.balance}** 🪙\n"
                f"Скидка на все лоты: **20%**"
            ),
            color=discord.Color.dark_purple(),
        )
        for idx, offer in enumerate(offers, start=1):
            embed.add_field(
                name=f"Лот #{idx} — {offer.item.name}",
                value=(
                    f"~~{offer.original_price}~~ 🪙 → **{offer.discounted_price}** 🪙\n"
                    f"{offer.item.description}"
                ),
                inline=False,
            )
        embed.set_footer(text="Ассортимент обновляется каждые 24 часа")
        return embed

    def build_confirm_embed(self, user_id: int, item: ShopItem) -> discord.Embed:
        profile = self.profile_service.get_profile(user_id)
        embed = discord.Embed(
            title="⚠️ Подтверждение покупки",
            description="Подтверди покупку выбранного предмета.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Предмет", value=item.name, inline=False)
        embed.add_field(name="Категория", value=item.category, inline=True)
        embed.add_field(name="Цена", value=f"{item.price} 🪙", inline=True)
        embed.add_field(name="Описание", value=item.description, inline=False)
        embed.set_footer(text=f"Текущий баланс: {profile.balance} 🪙")
        return embed

    def build_black_market_confirm_embed(self, user_id: int, offer: BlackMarketOffer) -> discord.Embed:
        profile = self.profile_service.get_profile(user_id)
        embed = discord.Embed(
            title="⚠️ Подтверждение покупки",
            description="Подтверди покупку лота с чёрного рынка.",
            color=discord.Color.orange(),
        )
        embed.add_field(name="Предмет", value=offer.item.name, inline=False)
        embed.add_field(name="Старая цена", value=f"~~{offer.original_price}~~ 🪙", inline=True)
        embed.add_field(name="Новая цена", value=f"**{offer.discounted_price}** 🪙", inline=True)
        embed.add_field(name="Описание", value=offer.item.description, inline=False)
        embed.set_footer(text=f"Текущий баланс: {profile.balance} 🪙")
        return embed

    def build_purchase_result_embed(self, message: str, details: dict[str, Any]) -> discord.Embed:
        embed = discord.Embed(title="✅ Покупка завершена", description=message, color=discord.Color.green())
        item = details.get("item")
        if item is not None:
            embed.add_field(name="Предмет", value=item.name, inline=False)
            embed.add_field(name="Категория", value=item.category, inline=True)

        discounted_price = details.get("discounted_price")
        original_price = details.get("original_price")
        paid_price = details.get("paid_price")
        if discounted_price is not None and original_price is not None:
            embed.add_field(name="Цена", value=f"~~{original_price}~~ 🪙 → **{discounted_price}** 🪙", inline=True)
        elif paid_price is not None:
            embed.add_field(name="Цена", value=f"**{paid_price}** 🪙", inline=True)

        expires_ts = details.get("expires_ts")
        if expires_ts is not None:
            expires_at = dt.datetime.fromtimestamp(int(expires_ts)).strftime("%d.%m.%Y %H:%M")
            embed.add_field(name="Срок действия", value=f"До **{expires_at}**", inline=False)

        reward_text = details.get("reward_text")
        if reward_text:
            embed.add_field(name="Награда", value=str(reward_text), inline=False)

        return embed

    @app_commands.command(name="shop", description="Открыть магазин сервера")
    async def shop(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        embed = self.build_main_embed(interaction.user.id)
        await interaction.response.send_message(
            embed=embed,
            view=MainShopView(self, interaction.user.id),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShopCog(bot), guild=Config.SERVER_OBJ)