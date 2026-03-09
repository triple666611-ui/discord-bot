import random
from typing import Any, cast

import discord
from discord import Interaction, TextChannel, app_commands
from discord.ext import commands

from config import Config


class Games(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.profile_service = cast(Any, bot).profile_service
        self.shop_service = getattr(cast(Any, bot), "shop_service", None)

    def build_games_help_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎮 Игровые команды сервера",
            description="Правила игр, каналы для игры и базовые награды.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="🪙 /coin — Монетка",
            value=(
                f"Канал: <#{Config.COIN_CHANNEL_ID}>\n"
                "Выбираешь **орел** или **решка** и указываешь ставку.\n"
                "Угадал — **+ставка**. Не угадал — **-ставка**."
            ),
            inline=False,
        )
        embed.add_field(
            name="🎲 /dice — Кости",
            value=(
                f"Канал: <#{Config.DICE_CHANNEL_ID}>\n"
                "Ты бросаешь Кости против бота.\n"
                "Если число больше — **+ставка**.\n"
                "Если меньше — **-ставка**.\n"
                "Если ничья — баланс не меняется."
            ),
            inline=False,
        )
        embed.add_field(
            name="🎰 /slots — Слоты",
            value=(
                f"Канал: <#{Config.SLOTS_CHANNEL_ID}>\n"
                "**💎💎💎** → **x5**\n"
                "**3 одинаковых** → **x3**\n"
                "**2 одинаковых** → **x1.5**\n"
                "Нет совпадений — **проигрыш ставки**."
            ),
            inline=False,
        )
        embed.add_field(
            name="🎁 /daily — Ежедневная награда",
            value=f"Раз в 24 часа можно получить **{Config.DAILY_REWARD}** 🪙.",
            inline=False,
        )
        embed.set_footer(text="Эту информацию видишь только ты")
        return embed

    def _build_game_embed(
        self,
        *,
        title: str,
        emoji: str,
        color: discord.Color,
        player: discord.abc.User,
        game_name: str,
        bet: int,
        result_lines: list[str],
        balance_after: int,
    ) -> discord.Embed:
        embed = discord.Embed(title=f"{emoji} {title}", color=color)
        embed.add_field(name="Игра", value=game_name, inline=True)
        embed.add_field(name="Игрок", value=player.mention, inline=True)
        embed.add_field(name="Ставка", value=f"{bet} 🪙", inline=True)
        embed.add_field(name="Результат", value="\n".join(result_lines), inline=False)
        embed.add_field(name="Баланс после игры", value=f"{balance_after} 🪙", inline=False)
        embed.set_thumbnail(url=player.display_avatar.url)
        embed.set_footer(text=f"Игрок: {player.display_name}")
        return embed

    async def send_private_topbalance(self, interaction: Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        top_data = self.profile_service.get_top_balances(limit=10)
        if not top_data:
            await interaction.response.send_message("Пока нет данных по балансу.", ephemeral=True)
            return

        lines: list[str] = []
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for index, (user_id, balance) in enumerate(top_data, start=1):
            member = interaction.guild.get_member(user_id)
            user_display = member.mention if member else f"<@{user_id}>"
            prefix = medals.get(index, f"**{index}.**")
            lines.append(f"{prefix} {user_display} — **{balance}** 🪙")

        embed = discord.Embed(
            title="💰 Топ по балансу",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Эту информацию видишь только ты")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _send_high_stake_log(
        self,
        interaction: Interaction,
        *,
        game_name: str,
        bet: int,
        result_text: str,
        balance_after: int,
    ) -> None:
        if interaction.guild is None or bet < Config.HIGH_STAKE_THRESHOLD:
            return
        channel = interaction.guild.get_channel(Config.BALANCE_LOG_CHANNEL_ID)
        if not isinstance(channel, TextChannel):
            return
        embed = discord.Embed(title="💰 Лог крупной ставки", color=discord.Color.gold())
        embed.add_field(name="Игра", value=game_name, inline=True)
        embed.add_field(name="Игрок", value=interaction.user.mention, inline=True)
        embed.add_field(name="Ставка", value=f"{bet} 🪙", inline=True)
        embed.add_field(name="Результат", value=result_text, inline=False)
        embed.add_field(name="Баланс после игры", value=f"{balance_after} 🪙", inline=True)
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    async def _check_game_channel(self, interaction: Interaction, *, allowed_channel_id: int, game_name: str) -> bool:
        if interaction.channel_id == allowed_channel_id:
            return True
        await interaction.response.send_message(
            f"❌ В `{game_name}` можно играть только в канале <#{allowed_channel_id}>.",
            ephemeral=True,
        )
        return False

    @app_commands.command(name="games", description="Показать правила всех игр")
    async def games_cmd(self, interaction: Interaction) -> None:
        await interaction.response.send_message(embed=self.build_games_help_embed(), ephemeral=True)

    @app_commands.command(name="topbalance", description="Показать топ игроков по балансу")
    async def topbalance_cmd(self, interaction: Interaction) -> None:
        await self.send_private_topbalance(interaction)

    @app_commands.command(name="daily", description="Получить ежедневную награду")
    async def daily_cmd(self, interaction: Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        allowed, left = self.profile_service.can_claim_daily(interaction.user.id)
        if not allowed:
            hours = left // 3600
            minutes = (left % 3600) // 60
            await interaction.response.send_message(
                f"⏳ Ежедневную награду уже забрали. Попробуй снова через **{hours} ч {minutes} мин**.",
                ephemeral=True,
            )
            return
        reward_amount = Config.DAILY_REWARD
        if self.shop_service is not None:
            reward_amount = self.shop_service.get_daily_reward_amount(interaction.user.id)
            new_balance = self.shop_service.claim_daily(interaction.user.id)
        else:
            new_balance = self.profile_service.claim_daily(interaction.user.id)
        embed = discord.Embed(
            title="🎁 Ежедневная награда",
            description=f"Ты получил **{reward_amount}** 🪙\nНовый баланс: **{new_balance}** 🪙",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Игрок: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="coin", description="Подбросить монетку и сыграть на баланс")
    @app_commands.choices(side=[app_commands.Choice(name="орел", value="орел"), app_commands.Choice(name="решка", value="решка")])
    async def coin_cmd(self, interaction: Interaction, side: app_commands.Choice[str], bet: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not await self._check_game_channel(interaction, allowed_channel_id=Config.COIN_CHANNEL_ID, game_name="/coin"):
            return
        if bet <= 0:
            await interaction.response.send_message("❌ Ставка должна быть больше 0.", ephemeral=True)
            return
        profile = self.profile_service.get_profile(interaction.user.id)
        if profile.balance < bet:
            await interaction.response.send_message(
                f"❌ Недостаточно монет. Твой баланс: **{profile.balance}** 🪙",
                ephemeral=True,
            )
            return

        result = random.choice(["орел", "решка"])
        win = side.value == result
        if win:
            win_amount = bet
            bonus_lines: list[str] = []
            if self.shop_service is not None:
                win_amount, bonus_lines = self.shop_service.apply_game_win_bonus(interaction.user.id, bet)
            new_balance = self.profile_service.add_balance(interaction.user.id, win_amount)
            embed = self._build_game_embed(
                title="Монетка: победа",
                emoji="🪙",
                color=discord.Color.green(),
                player=interaction.user,
                game_name="Монетка",
                bet=bet,
                result_lines=[f"Ты выбрал: **{side.value}**", f"Выпало: **{result}**", f"Выигрыш: **+{win_amount}** 🪙", *bonus_lines],
                balance_after=new_balance,
            )
            result_text = f"Победа, выпало {result}, выигрыш {win_amount}"
        else:
            new_balance = self.profile_service.add_balance(interaction.user.id, -bet)
            embed = self._build_game_embed(
                title="Монетка: поражение",
                emoji="🪙",
                color=discord.Color.red(),
                player=interaction.user,
                game_name="Монетка",
                bet=bet,
                result_lines=[f"Ты выбрал: **{side.value}**", f"Выпало: **{result}**", f"Проигрыш: **-{bet}** 🪙"],
                balance_after=new_balance,
            )
            result_text = f"Поражение, выпало {result}"
        await interaction.response.send_message(embed=embed)
        await self._send_high_stake_log(interaction, game_name="Монетка", bet=bet, result_text=result_text, balance_after=new_balance)

    @app_commands.command(name="dice", description="Бросить Кости против бота и сыграть на баланс")
    async def dice_cmd(self, interaction: Interaction, bet: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not await self._check_game_channel(interaction, allowed_channel_id=Config.DICE_CHANNEL_ID, game_name="/dice"):
            return
        if bet <= 0:
            await interaction.response.send_message("❌ Ставка должна быть больше 0.", ephemeral=True)
            return
        profile = self.profile_service.get_profile(interaction.user.id)
        if profile.balance < bet:
            await interaction.response.send_message(
                f"❌ Недостаточно монет. Твой баланс: **{profile.balance}** 🪙",
                ephemeral=True,
            )
            return

        user_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)
        if user_roll > bot_roll:
            win_amount = bet
            bonus_lines: list[str] = []
            if self.shop_service is not None:
                win_amount, bonus_lines = self.shop_service.apply_game_win_bonus(interaction.user.id, bet)
            new_balance = self.profile_service.add_balance(interaction.user.id, win_amount)
            embed = self._build_game_embed(
                title="Кости: победа",
                emoji="🎲",
                color=discord.Color.green(),
                player=interaction.user,
                game_name="Кости",
                bet=bet,
                result_lines=[f"Твой бросок: **{user_roll}**", f"Бросок бота: **{bot_roll}**", f"Выигрыш: **+{win_amount}** 🪙", *bonus_lines],
                balance_after=new_balance,
            )
            result_text = f"Победа: игрок {user_roll}, бот {bot_roll}, выигрыш {win_amount}"
        elif user_roll < bot_roll:
            new_balance = self.profile_service.add_balance(interaction.user.id, -bet)
            embed = self._build_game_embed(
                title="Кости: поражение",
                emoji="🎲",
                color=discord.Color.red(),
                player=interaction.user,
                game_name="Кости",
                bet=bet,
                result_lines=[f"Твой бросок: **{user_roll}**", f"Бросок бота: **{bot_roll}**", f"Проигрыш: **-{bet}** 🪙"],
                balance_after=new_balance,
            )
            result_text = f"Поражение: игрок {user_roll}, бот {bot_roll}"
        else:
            new_balance = profile.balance
            embed = self._build_game_embed(
                title="Кости: ничья",
                emoji="🎲",
                color=discord.Color.blurple(),
                player=interaction.user,
                game_name="Кости",
                bet=bet,
                result_lines=[f"Твой бросок: **{user_roll}**", f"Бросок бота: **{bot_roll}**", "Ничья: баланс не изменился"],
                balance_after=new_balance,
            )
            result_text = f"Ничья: игрок {user_roll}, бот {bot_roll}"
        await interaction.response.send_message(embed=embed)
        await self._send_high_stake_log(interaction, game_name="Кости", bet=bet, result_text=result_text, balance_after=new_balance)

    @app_commands.command(name="slots", description="Сыграть в слоты на баланс")
    async def slots_cmd(self, interaction: Interaction, bet: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not await self._check_game_channel(interaction, allowed_channel_id=Config.SLOTS_CHANNEL_ID, game_name="/slots"):
            return
        if bet <= 0:
            await interaction.response.send_message("❌ Ставка должна быть больше 0.", ephemeral=True)
            return
        profile = self.profile_service.get_profile(interaction.user.id)
        if profile.balance < bet:
            await interaction.response.send_message(
                f"❌ Недостаточно монет. Твой баланс: **{profile.balance}** 🪙",
                ephemeral=True,
            )
            return

        symbols = ["🍒", "🍋", "🔔", "7️⃣", "💎"]
        roll = [random.choice(symbols) for _ in range(3)]
        vip_slot_active = self.shop_service.consume_vip_slot_effect(interaction.user.id) if self.shop_service is not None else False
        if vip_slot_active and len(set(roll)) == 3:
            chosen = random.choice(symbols)
            roll[1] = chosen
            roll[2] = chosen
        multiplier = 0.0
        result_name = "Проигрыш"
        if roll == ["💎", "💎", "💎"]:
            multiplier = 5.0
            result_name = "Джекпот"
        elif roll[0] == roll[1] == roll[2]:
            multiplier = 3.0
            result_name = "Тройное совпадение"
        elif roll[0] == roll[1] or roll[0] == roll[2] or roll[1] == roll[2]:
            multiplier = 1.5
            result_name = "Двойное совпадение"

        if multiplier == 0.0:
            new_balance = self.profile_service.add_balance(interaction.user.id, -bet)
            embed = self._build_game_embed(
                title="Слоты: проигрыш",
                emoji="🎰",
                color=discord.Color.red(),
                player=interaction.user,
                game_name="Слоты",
                bet=bet,
                result_lines=[f"Комбинация: **{' | '.join(roll)}**", f"Результат: **{result_name}**", f"Проигрыш: **-{bet}** 🪙"],
                balance_after=new_balance,
            )
            result_text = f"{result_name}: {' | '.join(roll)}"
        else:
            win_amount = int(bet * multiplier)
            bonus_lines: list[str] = []
            if vip_slot_active:
                bonus_lines.append("🎰 Сработал VIP слот: минимум двойное совпадение гарантировано.")
            if self.shop_service is not None:
                win_amount, extra_bonus_lines = self.shop_service.apply_game_win_bonus(interaction.user.id, win_amount)
                bonus_lines.extend(extra_bonus_lines)
            new_balance = self.profile_service.add_balance(interaction.user.id, win_amount)
            embed = self._build_game_embed(
                title="Слоты: победа",
                emoji="🎰",
                color=discord.Color.green(),
                player=interaction.user,
                game_name="Слоты",
                bet=bet,
                result_lines=[
                    f"Комбинация: **{' | '.join(roll)}**",
                    f"Результат: **{result_name}**",
                    f"Множитель: **x{multiplier}**",
                    f"Выигрыш: **+{win_amount}** 🪙",
                    *bonus_lines,
                ],
                balance_after=new_balance,
            )
            result_text = f"{result_name}: {' | '.join(roll)} | x{multiplier}"
        await interaction.response.send_message(embed=embed)
        await self._send_high_stake_log(interaction, game_name="Слоты", bet=bet, result_text=result_text, balance_after=new_balance)


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot), guild=Config.SERVER_OBJ)
