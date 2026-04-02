from __future__ import annotations

from typing import Any, cast

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from ui.shop.view import ShopView


class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.profile_service = cast(Any, bot).profile_service
        self.shop_service = cast(Any, bot).shop_service

    @app_commands.command(name='shop', description='Открыть магазин сервера')
    async def shop(self, interaction: discord.Interaction) -> None:
        await self._open_shop_view(interaction, mode='main')

    @app_commands.command(name='inventory', description='Открыть инвентарь сервера')
    async def inventory(self, interaction: discord.Interaction) -> None:
        await self._open_shop_view(interaction, mode='inventory')

    async def _open_shop_view(self, interaction: discord.Interaction, *, mode: str) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title='Ошибка',
                    description='Команда доступна только на сервере.',
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        view = ShopView(self, interaction.user.id)
        view.mode = mode
        view.selected_item_key = None
        view.refresh_components()
        await interaction.response.send_message(
            embed=view.build_current_embed(),
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShopCog(bot), guild=Config.SERVER_OBJ)
