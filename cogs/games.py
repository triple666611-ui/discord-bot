import random
from typing import Any, cast

import discord
from discord import Interaction, TextChannel, app_commands
from discord.ext import commands

from config import Config

BLACKJACK_RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
BLACKJACK_SUITS = ["♠", "♥", "♦", "♣"]
BLACKJACK_TIMEOUT_SEC = 120


class BlackJackView(discord.ui.View):
    def __init__(self, cog: "Games", player: discord.abc.User, bet: int):
        super().__init__(timeout=BLACKJACK_TIMEOUT_SEC)
        self.cog = cog
        self.player = player
        self.bet = bet
        self.message: discord.Message | None = None
        self.finished = False
        self.player_hand = [self._draw_card(), self._draw_card()]
        self.dealer_hand = [self._draw_card(), self._draw_card()]

    def _draw_card(self) -> tuple[str, str]:
        return random.choice(BLACKJACK_RANKS), random.choice(BLACKJACK_SUITS)

    def _card_label(self, card: tuple[str, str]) -> str:
        rank, suit = card
        return f"{rank}{suit}"

    def _hand_value(self, hand: list[tuple[str, str]]) -> int:
        total = 0
        aces = 0
        for rank, _ in hand:
            if rank in {"J", "Q", "K"}:
                total += 10
            elif rank == "A":
                total += 11
                aces += 1
            else:
                total += int(rank)

        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total

    def _format_hand(self, hand: list[tuple[str, str]], *, hide_last: bool) -> str:
        cards = [self._card_label(card) for card in hand]
        if hide_last and cards:
            cards = [*cards[:-1], "?"]
        return " | ".join(cards)

    def _build_embed(
        self,
        *,
        title: str,
        color: discord.Color,
        result_lines: list[str],
        reveal_dealer: bool,
        balance_after: int | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(title=f"🃏 {title}", color=color)
        embed.add_field(name="Игра", value="Black Jack", inline=True)
        embed.add_field(name="Игрок", value=self.player.mention, inline=True)
        embed.add_field(name="Ставка", value=f"{self.bet} 🪙", inline=True)

        player_total = self._hand_value(self.player_hand)
        dealer_total = self._hand_value(self.dealer_hand)
        dealer_value = str(dealer_total) if reveal_dealer else "?"

        embed.add_field(
            name="Твоя рука",
            value=f"{self._format_hand(self.player_hand, hide_last=False)}\nСумма: **{player_total}**",
            inline=False,
        )
        embed.add_field(
            name="Рука дилера",
            value=f"{self._format_hand(self.dealer_hand, hide_last=not reveal_dealer)}\nСумма: **{dealer_value}**",
            inline=False,
        )
        embed.add_field(name="Статус", value="\n".join(result_lines), inline=False)
        if balance_after is not None:
            embed.add_field(name="Баланс после игры", value=f"{balance_after} 🪙", inline=False)
        embed.set_thumbnail(url=self.player.display_avatar.url)
        embed.set_footer(text=f"Игрок: {self.player.display_name}")
        return embed

    def build_live_embed(self) -> discord.Embed:
        return self._build_embed(
            title="Black Jack: ход",
            color=discord.Color.blurple(),
            result_lines=[
                "Нажми **Hit**, чтобы взять карту.",
                "Нажми **Stand**, чтобы остановиться и передать ход дилеру.",
            ],
            reveal_dealer=False,
        )

    def _disable_controls(self) -> None:
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True

    async def _finish(
        self,
        interaction: Interaction,
        *,
        title: str,
        color: discord.Color,
        result_lines: list[str],
        balance_after: int,
        result_text: str,
    ) -> None:
        self.finished = True
        self._disable_controls()
        self.stop()
        self.cog.unregister_blackjack_game(self.player.id)

        embed = self._build_embed(
            title=title,
            color=color,
            result_lines=result_lines,
            reveal_dealer=True,
            balance_after=balance_after,
        )
        await interaction.response.edit_message(embed=embed, view=self)
        await self.cog._send_high_stake_log(
            interaction,
            game_name="Black Jack",
            bet=self.bet,
            result_text=result_text,
            balance_after=balance_after,
        )

    def resolve_opening_hand(self) -> tuple[discord.Embed, int, str] | None:
        player_total = self._hand_value(self.player_hand)
        dealer_total = self._hand_value(self.dealer_hand)
        player_blackjack = player_total == 21 and len(self.player_hand) == 2
        dealer_blackjack = dealer_total == 21 and len(self.dealer_hand) == 2

        if not player_blackjack and not dealer_blackjack:
            return None

        self.finished = True
        self._disable_controls()
        self.stop()
        self.cog.unregister_blackjack_game(self.player.id)

        if player_blackjack and dealer_blackjack:
            balance_after = self.cog.profile_service.get_profile(self.player.id).balance
            title = "Black Jack: ничья"
            color = discord.Color.blurple()
            result_lines = ["У тебя и у дилера Black Jack.", "Ничья: баланс не изменился."]
            result_text = "Ничья: у обоих Black Jack"
        elif player_blackjack:
            win_amount = int(self.bet * 1.5)
            bonus_lines: list[str] = []
            if self.cog.shop_service is not None:
                win_amount, bonus_lines = self.cog.shop_service.apply_game_win_bonus(self.player.id, win_amount)
            balance_after = self.cog.profile_service.add_balance(self.player.id, win_amount)
            title = "Black Jack: победа"
            color = discord.Color.green()
            result_lines = ["У тебя натуральный Black Jack.", f"Выигрыш: **+{win_amount}** 🪙", *bonus_lines]
            result_text = f"Победа: натуральный Black Jack, выигрыш {win_amount}"
        else:
            balance_after = self.cog.profile_service.add_balance(self.player.id, -self.bet)
            title = "Black Jack: поражение"
            color = discord.Color.red()
            result_lines = ["Дилер сразу собрал Black Jack.", f"Проигрыш: **-{self.bet}** 🪙"]
            result_text = "Поражение: дилер получил натуральный Black Jack"

        embed = self._build_embed(
            title=title,
            color=color,
            result_lines=result_lines,
            reveal_dealer=True,
            balance_after=balance_after,
        )
        return embed, balance_after, result_text

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id == self.player.id:
            return True
        await interaction.response.send_message("Эта партия открыта для другого игрока.", ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        if self.finished:
            return
        self.finished = True
        self._disable_controls()
        self.stop()
        self.cog.unregister_blackjack_game(self.player.id)
        if self.message is None:
            return
        embed = self._build_embed(
            title="Black Jack: время вышло",
            color=discord.Color.orange(),
            result_lines=["Игра закрыта из-за бездействия.", "Ставка не списана, баланс не изменился."],
            reveal_dealer=True,
            balance_after=self.cog.profile_service.get_profile(self.player.id).balance,
        )
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: Interaction, _: discord.ui.Button) -> None:
        self.player_hand.append(self._draw_card())
        player_total = self._hand_value(self.player_hand)

        if player_total > 21:
            balance_after = self.cog.profile_service.add_balance(self.player.id, -self.bet)
            await self._finish(
                interaction,
                title="Black Jack: поражение",
                color=discord.Color.red(),
                result_lines=["Ты взял ещё карту и перебрал 21.", f"Проигрыш: **-{self.bet}** 🪙"],
                balance_after=balance_after,
                result_text=f"Поражение: перебор игрока ({player_total})",
            )
            return

        if player_total == 21:
            await self._resolve_stand(interaction)
            return

        await interaction.response.edit_message(embed=self.build_live_embed(), view=self)

    async def _resolve_stand(self, interaction: Interaction) -> None:
        while self._hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self._draw_card())

        player_total = self._hand_value(self.player_hand)
        dealer_total = self._hand_value(self.dealer_hand)

        if dealer_total > 21 or player_total > dealer_total:
            win_amount = self.bet
            bonus_lines: list[str] = []
            if self.cog.shop_service is not None:
                win_amount, bonus_lines = self.cog.shop_service.apply_game_win_bonus(self.player.id, win_amount)
            balance_after = self.cog.profile_service.add_balance(self.player.id, win_amount)
            await self._finish(
                interaction,
                title="Black Jack: победа",
                color=discord.Color.green(),
                result_lines=[
                    f"Твоя сумма: **{player_total}**",
                    f"Сумма дилера: **{dealer_total}**",
                    f"Выигрыш: **+{win_amount}** 🪙",
                    *bonus_lines,
                ],
                balance_after=balance_after,
                result_text=f"Победа: игрок {player_total}, дилер {dealer_total}, выигрыш {win_amount}",
            )
            return

        if player_total < dealer_total:
            balance_after = self.cog.profile_service.add_balance(self.player.id, -self.bet)
            await self._finish(
                interaction,
                title="Black Jack: поражение",
                color=discord.Color.red(),
                result_lines=[
                    f"Твоя сумма: **{player_total}**",
                    f"Сумма дилера: **{dealer_total}**",
                    f"Проигрыш: **-{self.bet}** 🪙",
                ],
                balance_after=balance_after,
                result_text=f"Поражение: игрок {player_total}, дилер {dealer_total}",
            )
            return

        balance_after = self.cog.profile_service.get_profile(self.player.id).balance
        await self._finish(
            interaction,
            title="Black Jack: ничья",
            color=discord.Color.blurple(),
            result_lines=[
                f"Твоя сумма: **{player_total}**",
                f"Сумма дилера: **{dealer_total}**",
                "Ничья: баланс не изменился.",
            ],
            balance_after=balance_after,
            result_text=f"Ничья: игрок {player_total}, дилер {dealer_total}",
        )

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.blurple)
    async def stand_button(self, interaction: Interaction, _: discord.ui.Button) -> None:
        await self._resolve_stand(interaction)


class Games(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.profile_service = cast(Any, bot).profile_service
        self.shop_service = getattr(cast(Any, bot), "shop_service", None)
        self.active_blackjack_games: set[int] = set()

    def register_blackjack_game(self, user_id: int) -> None:
        self.active_blackjack_games.add(user_id)

    def unregister_blackjack_game(self, user_id: int) -> None:
        self.active_blackjack_games.discard(user_id)

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
                "Выбираешь **орёл** или **решка** и указываешь ставку.\n"
                "Угадал — **+ставка**. Не угадал — **-ставка**."
            ),
            inline=False,
        )
        embed.add_field(
            name="🎲 /dice — Кости",
            value=(
                f"Канал: <#{Config.DICE_CHANNEL_ID}>\n"
                "Ты бросаешь кости против бота.\n"
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
            name="🃏 /blackjack — Black Jack",
            value=(
                f"Канал: <#{Config.BLACKJACK_CHANNEL_ID}>\n"
                "Интерактивная партия против дилера с кнопками **Hit** и **Stand**.\n"
                "Победа — **+ставка**, натуральный Black Jack — **x1.5 от ставки**.\n"
                "Поражение — **-ставка**, ничья — баланс не меняется."
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
    @app_commands.choices(side=[app_commands.Choice(name="орёл", value="орёл"), app_commands.Choice(name="решка", value="решка")])
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

        result = random.choice(["орёл", "решка"])
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

    @app_commands.command(name="dice", description="Бросить кости против бота и сыграть на баланс")
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

    @app_commands.command(name="blackjack", description="Сыграть в Black Jack против дилера")
    async def blackjack_cmd(self, interaction: Interaction, bet: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Команда доступна только на сервере.", ephemeral=True)
            return
        if not await self._check_game_channel(interaction, allowed_channel_id=Config.BLACKJACK_CHANNEL_ID, game_name="/blackjack"):
            return
        if bet <= 0:
            await interaction.response.send_message("❌ Ставка должна быть больше 0.", ephemeral=True)
            return
        if interaction.user.id in self.active_blackjack_games:
            await interaction.response.send_message("❌ У тебя уже есть активная партия в Black Jack. Закончи её или дождись тайм-аута.", ephemeral=True)
            return

        profile = self.profile_service.get_profile(interaction.user.id)
        if profile.balance < bet:
            await interaction.response.send_message(
                f"❌ Недостаточно монет. Твой баланс: **{profile.balance}** 🪙",
                ephemeral=True,
            )
            return

        self.register_blackjack_game(interaction.user.id)
        view = BlackJackView(self, interaction.user, bet)
        opening_result = view.resolve_opening_hand()
        if opening_result is not None:
            embed, balance_after, result_text = opening_result
            await interaction.response.send_message(embed=embed)
            await self._send_high_stake_log(
                interaction,
                game_name="Black Jack",
                bet=bet,
                result_text=result_text,
                balance_after=balance_after,
            )
            return

        await interaction.response.send_message(embed=view.build_live_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Games(bot), guild=Config.SERVER_OBJ)

