from __future__ import annotations

import datetime as dt
from typing import Any, cast

import discord
from discord import app_commands
from discord.ext import commands

from config import Config


class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.profile_service = cast(Any, bot).profile_service
        self.shop_service = cast(Any, bot).shop_service

    def _format_ts(self, ts: int | None) -> str:
        if ts is None:
            return "бессрочно"
        return dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")

    def _build_catalog_embed(self, user_id: int) -> discord.Embed:
        profile = self.profile_service.get_profile(user_id)
        embed = discord.Embed(
            title="🛒 Магазин сервера",
            description=(
                "Покупай косметику, бонусы, роли, VIP и кейсы за монеты сервера.\n"
                f"Твой баланс: **{profile.balance}** 🪙"
            ),
            color=discord.Color.blurple(),
        )

        catalog = self.shop_service.get_catalog()
        for category, items in catalog.items():
            lines = [f"`{item.key}` — **{item.name}** — {item.price} 🪙" for item in items]
            embed.add_field(name=category, value="\n".join(lines), inline=False)

        embed.add_field(
            name="⚫ Чёрный рынок",
            value="Используй `/shop action:blackmarket`, чтобы посмотреть редкий ежедневный товар.",
            inline=False,
        )
        embed.set_footer(text="Покупка: /shop action:buy item:<ключ> | Использование: /shop action:use item:<ключ>")
        return embed

    def _build_inventory_embed(self, user_id: int) -> discord.Embed:
        inventory = self.shop_service.get_inventory(user_id)
        effects = self.shop_service.list_effects(user_id)
        profile = self.profile_service.get_profile(user_id)

        embed = discord.Embed(
            title="🎒 Инвентарь игрока",
            description=f"Текущий баланс: **{profile.balance}** 🪙",
            color=discord.Color.green(),
        )

        if inventory:
            lines: list[str] = []
            for item_key, qty in inventory.items():
                item = self.shop_service.get_item(item_key)
                item_name = item.name if item is not None else item_key
                lines.append(f"• {item_name} — **x{qty}**")
            embed.add_field(name="Предметы", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Предметы", value="Инвентарь пуст.", inline=False)

        if effects:
            effect_lines: list[str] = []
            for effect_key, effect_data in effects.items():
                expires = self._format_ts(effect_data.get("expires_ts"))
                value = effect_data.get("value")
                effect_lines.append(f"• `{effect_key}` → **{value}** до **{expires}**")
            embed.add_field(name="Активные эффекты", value="\n".join(effect_lines), inline=False)
        else:
            embed.add_field(name="Активные эффекты", value="Нет активных эффектов.", inline=False)

        return embed

    def _build_black_market_embed(self, user_id: int) -> discord.Embed:
        item = self.shop_service.get_black_market_offer()
        profile = self.profile_service.get_profile(user_id)
        embed = discord.Embed(
            title="⚫ Чёрный рынок",
            description=(
                "Редкий товар дня. Ассортимент меняется каждые 24 часа.\n"
                f"Твой баланс: **{profile.balance}** 🪙"
            ),
            color=discord.Color.dark_purple(),
        )
        embed.add_field(
            name=item.name,
            value=(
                f"Ключ: `{item.key}`\n"
                f"Цена: **{item.price}** 🪙\n"
                f"Описание: {item.description}"
            ),
            inline=False,
        )
        embed.set_footer(text="Покупка: /shop action:buy item:black_market_offer")
        return embed

    @app_commands.command(name="shop", description="Магазин сервера: каталог, покупка, инвентарь и использование предметов")
    @app_commands.describe(action="Что сделать", item="Ключ предмета из магазина")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="каталог", value="browse"),
            app_commands.Choice(name="купить", value="buy"),
            app_commands.Choice(name="инвентарь", value="inventory"),
            app_commands.Choice(name="использовать", value="use"),
            app_commands.Choice(name="чёрный рынок", value="blackmarket"),
        ],
        item=[
            app_commands.Choice(name="🌈 Цветной профиль", value="color_profile"),
            app_commands.Choice(name="🖼 Кастомный фон", value="custom_bg"),
            app_commands.Choice(name="⭐ VIP рамка", value="vip_frame"),
            app_commands.Choice(name="🎲 x2 выигрыш", value="double_win_token"),
            app_commands.Choice(name="🎰 VIP слот", value="vip_slot_ticket"),
            app_commands.Choice(name="🎁 Малый кейс", value="small_case"),
            app_commands.Choice(name="💎 Большой кейс", value="big_case"),
            app_commands.Choice(name="💎 Роль VIP", value="role_vip"),
            app_commands.Choice(name="👑 Роль Elite", value="role_elite"),
            app_commands.Choice(name="🌟 Роль Legend", value="role_legend"),
            app_commands.Choice(name="💠 VIP 7 дней", value="vip_7d"),
            app_commands.Choice(name="🚀 VIP 30 дней", value="vip_30d"),
            app_commands.Choice(name="🏆 Турнирный билет", value="tournament_ticket"),
            app_commands.Choice(name="⚫ Товар чёрного рынка", value="black_market_offer"),
            app_commands.Choice(name="🕶 Теневая рамка", value="bm_shadow_frame"),
        ],
    )
    async def shop(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        item: app_commands.Choice[str] | None = None,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return

        if action.value == "browse":
            await interaction.response.send_message(embed=self._build_catalog_embed(interaction.user.id), ephemeral=True)
            return

        if action.value == "inventory":
            await interaction.response.send_message(embed=self._build_inventory_embed(interaction.user.id), ephemeral=True)
            return

        if action.value == "blackmarket":
            await interaction.response.send_message(embed=self._build_black_market_embed(interaction.user.id), ephemeral=True)
            return

        if item is None:
            await interaction.response.send_message("❌ Для этого действия нужно выбрать предмет.", ephemeral=True)
            return

        if action.value == "buy":
            success, message, details = self.shop_service.buy_item(interaction.user.id, item.value)
            if not success:
                await interaction.response.send_message(message, ephemeral=True)
                return

            embed = discord.Embed(
                title="🛍 Покупка завершена",
                description=message,
                color=discord.Color.green(),
            )
            purchased_item = details.get("item")
            if purchased_item is not None:
                embed.add_field(name="Предмет", value=purchased_item.name, inline=False)
                embed.add_field(name="Категория", value=purchased_item.category, inline=True)
                embed.add_field(name="Цена", value=f"{purchased_item.price} 🪙", inline=True)

            role_id = details.get("role_id")
            if role_id:
                role = interaction.guild.get_role(int(role_id)) if interaction.guild else None
                if role is None:
                    embed.add_field(name="Роль", value=f"ID {role_id} не найден на сервере.", inline=False)
                else:
                    member = interaction.guild.get_member(interaction.user.id)
                    if member is None:
                        embed.add_field(name="Роль", value="Пользователь не найден на сервере.", inline=False)
                    else:
                        try:
                            await member.add_roles(role, reason="Покупка роли в /shop")
                            embed.add_field(name="Роль", value=f"Выдана роль {role.mention}", inline=False)
                        except discord.Forbidden:
                            embed.add_field(name="Роль", value="Нет прав для выдачи роли. Проверь позицию роли бота.", inline=False)
                        except discord.HTTPException:
                            embed.add_field(name="Роль", value="Не удалось выдать роль из-за ошибки Discord API.", inline=False)

            expires_ts = details.get("expires_ts")
            if expires_ts:
                expires_text = self._format_ts(int(expires_ts))
                embed.add_field(name="Срок действия", value=expires_text, inline=False)

            reward_text = details.get("reward_text")
            if reward_text:
                embed.add_field(name="Награда", value=str(reward_text), inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if action.value == "use":
            success, message = self.shop_service.use_item(interaction.user.id, item.value)
            color = discord.Color.green() if success else discord.Color.red()
            await interaction.response.send_message(
                embed=discord.Embed(title="⚙ Использование предмета", description=message, color=color),
                ephemeral=True,
            )
            return

        await interaction.response.send_message("❌ Неизвестное действие магазина.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShopCog(bot))
