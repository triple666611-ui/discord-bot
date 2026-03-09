from __future__ import annotations

import discord
from discord import Interaction
from discord.app_commands import command, describe, default_permissions
from discord.ext.commands import Bot, Cog

from ui.notification import Display, SelectionMembers
from config import Config


class Notification(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @command(name="notification", description="Отправить уведомление")
    @describe(message="Напишите сообщение")
    @default_permissions(administrator=True)
    async def notification(self, interaction: Interaction, message: str):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Команда доступна только на сервере.",
                ephemeral=True,
            )
            return

        display = Display(interaction.user, message)
        embed = display.main()

        await interaction.response.send_message(
            embed=embed,
            view=SelectionMembers(display),
        )


async def setup(bot: Bot):
    await bot.add_cog(Notification(bot), guild=Config.SERVER_OBJ)