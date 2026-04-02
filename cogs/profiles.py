from __future__ import annotations

import time
from typing import Any, cast

import discord
from discord import app_commands
from discord.ext import commands, tasks

from services.level_service import level_from_xp, xp_for_next_level
from ui.profile.card_renderer import render_profile_card
from config import Config
from utils.permissions import has_admin_access


class ProfilesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.profile_service = cast(Any, bot).profile_service

        self.msg_xp_cd: dict[int, float] = {}
        self.voice_active: dict[int, int] = {}

        self.voice_xp_loop.start()

    async def cog_unload(self) -> None:
        if self.voice_xp_loop.is_running():
            self.voice_xp_loop.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        now = time.time()
        last_time = self.msg_xp_cd.get(user_id, 0)
        if now - last_time < Config.ECONOMY.MSG_XP_COOLDOWN_SEC:
            return

        self.msg_xp_cd[user_id] = now

        try:
            self.profile_service.add_xp(user_id, Config.ECONOMY.VOICE_XP_PER_MIN)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.bot:
            return

        if before.channel is None and after.channel is not None:
            self.voice_active[member.id] = int(time.time())
        elif before.channel is not None and after.channel is None:
            self.voice_active.pop(member.id, None)
        elif before.channel != after.channel and after.channel is not None:
            self.voice_active[member.id] = int(time.time())

    @tasks.loop(minutes=1)
    async def voice_xp_loop(self) -> None:
        for user_id in list(self.voice_active.keys()):
            try:
                self.profile_service.add_xp(user_id, Config.ECONOMY.VOICE_XP_PER_MIN)
            except Exception:
                pass

    @voice_xp_loop.before_loop
    async def before_voice_xp_loop(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="profile", description="Посмотреть профиль")
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        member = member or cast(discord.Member, interaction.user)
        profile = self.profile_service.get_profile(member.id)

        level, current_xp = level_from_xp(profile.xp)
        style = {'theme': None, 'frame': None}
        shop_service = getattr(self.bot, 'shop_service', None)
        if shop_service is not None:
            try:
                style = shop_service.get_profile_style(member.id)
            except Exception:
                style = {'theme': None, 'frame': None}

        image = await render_profile_card(member, {
            'level': level,
            'rep': profile.rep,
            'balance': profile.balance,
            'xp': current_xp,
            'xp_needed': xp_for_next_level(level),
            'theme': style.get('theme'),
            'frame': style.get('frame'),
        })
        file = discord.File(image, filename="profile.png")

        await interaction.response.send_message(file=file, ephemeral=True)

    @app_commands.command(name="rep", description="Повысить репутацию пользователю")
    async def rep(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        if member.bot:
            await interaction.response.send_message(
                "Нельзя изменять репутацию боту.",
                ephemeral=True,
            )
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message(
                "Нельзя изменять репутацию самому себе.",
                ephemeral=True,
            )
            return

        allowed, retry_after = self.profile_service.can_rep(interaction.user.id, member.id)
        if not allowed:
            hours = retry_after // 3600
            minutes = (retry_after % 3600) // 60
            await interaction.response.send_message(
                f"Репутацию можно менять позже. Подожди **{hours} ч. {minutes} мин.**",
                ephemeral=True,
            )
            return

        target_profile = self.profile_service.get_profile(member.id)
        new_rep = self.profile_service.set_rep(member.id, target_profile.rep + 1)
        self.profile_service.set_rep_ts(interaction.user.id, member.id)

        await interaction.response.send_message(
            f"Ты повысил репутацию {member.mention}. Теперь у него **{new_rep}** репутации."
        )

    @app_commands.command(name="setbalance", description="Установить баланс пользователю")
    @app_commands.describe(member="Пользователь", amount="Новый баланс")
    async def setbalance(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
    ) -> None:
        user_member = cast(discord.Member, interaction.user)
        if not has_admin_access(user_member):
            await interaction.response.send_message(
                "У тебя нет прав для этой команды.",
                ephemeral=True,
            )
            return

        if amount < 0:
            await interaction.response.send_message(
                "Баланс не может быть отрицательным.",
                ephemeral=True,
            )
            return

        self.profile_service.set_balance(member.id, amount)
        await interaction.response.send_message(
            f"Баланс пользователя {member.mention} установлен на **{amount}**."
        )

    @app_commands.command(name="setrep", description="Установить репутацию пользователю")
    @app_commands.describe(member="Пользователь", amount="Новое значение репутации")
    async def setrep(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
    ) -> None:
        user_member = cast(discord.Member, interaction.user)
        if not has_admin_access(user_member):
            await interaction.response.send_message("У тебя нет прав для этой команды.", ephemeral=True)
            return

        if amount < 0:
            await interaction.response.send_message("Репутация не может быть отрицательной.", ephemeral=True)
            return

        self.profile_service.set_rep(member.id, amount)
        await interaction.response.send_message(
            f"Репутация пользователя {member.mention} установлена на **{amount}**."
        )

    @app_commands.command(name="setxp", description="Установить XP пользователю")
    @app_commands.describe(member="Пользователь", amount="Новое значение XP")
    async def setxp(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
    ) -> None:
        user_member = cast(discord.Member, interaction.user)
        if not has_admin_access(user_member):
            await interaction.response.send_message("У тебя нет прав для этой команды.", ephemeral=True)
            return

        if amount < 0:
            await interaction.response.send_message("XP не может быть отрицательным.", ephemeral=True)
            return

        self.profile_service.set_xp(member.id, amount)
        await interaction.response.send_message(
            f"XP пользователя {member.mention} установлен на **{amount}**."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ProfilesCog(bot), guild=Config.SERVER_OBJ)

