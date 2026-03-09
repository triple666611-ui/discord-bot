from io import BytesIO
from typing import Any, cast

import discord
from discord.ext.commands import Bot, Cog

from config import Config
from ui.welcome.banner import build_minimal_welcome_banner
from ui.welcome.view import WelcomePanelView


class WelcomeCog(Cog):
    OLD_MARKERS = {"[welcome_panel]"}

    def __init__(self, bot: Bot):
        self.bot = bot
        self.panel_service = cast(Any, bot).panel_service

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title='Добро пожаловать!', description=Config.WELCOME.DESCRIPTION, color=0x5865F2)
        if Config.WELCOME.GIF_URL:
            embed.set_thumbnail(url=Config.WELCOME.GIF_URL)
        embed.set_footer(text=Config.WELCOME.FOOTER)
        return embed

    async def ensure_panel(self):
        guild = self.bot.get_guild(Config.BOT.SERVER_ID)
        if guild is None: return
        channel = guild.get_channel(Config.CHANNELS.ROLE_PANEL_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel): return
        banner_png = await build_minimal_welcome_banner(guild.name)
        file = discord.File(BytesIO(banner_png), filename='welcome_panel.png')
        embed = self.build_embed(); embed.set_image(url='attachment://welcome_panel.png')
        await self.panel_service.ensure_message(channel=channel, state_key='welcome_panel_message_id', embed=embed, view=WelcomePanelView(), file=file, cleanup_markers=self.OLD_MARKERS)

    @Cog.listener()
    async def on_ready(self):
        self.bot.add_view(WelcomePanelView())
        await self.ensure_panel()

async def setup(bot: Bot):
    await bot.add_cog(WelcomeCog(bot), guild=Config.BOT.SERVER_OBJECT)
