import random
from dataclasses import dataclass
from typing import Any, cast

import discord
from discord import Interaction, TextChannel, app_commands
from discord.ext import commands

from config import Config

BLACKJACK_RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
BLACKJACK_SUITS = ["♠", "♥", "♦", "♣"]
BLACKJACK_TIMEOUT_SEC = 120


@dataclass(slots=True)
class BlackJackHand:
    cards: list[tuple[str, str]]
    bet: int
    doubled: bool = False
    stood: bool = False
    busted: bool = False
    blackjack: bool = False
    result_text: str = ""
    payout_delta: int = 0


class BlackJackView(discord.ui.View):
    def __init__(self, cog: "Games", player: discord.abc.User, bet: int):
        super().__init__(timeout=BLACKJACK_TIMEOUT_SEC)
        self.cog = cog
        self.player = player
        self.base_bet = bet
        self.message: discord.Message | None = None
        self.finished = False
        self.dealer_hand = [self._draw_card(), self._draw_card()]
        self.hands = [BlackJackHand(cards=[self._draw_card(), self._draw_card()], bet=bet)]
        self.active_hand_index = 0
        self._refresh_button_states()

    def _draw_card(self) -> tuple[str, str]:
        return random.choice(BLACKJACK_RANKS), random.choice(BLACKJACK_SUITS)

    def _card_label(self, card: tuple[str, str]) -> str:
        rank, suit = card
        return f"{rank}{suit}"

    def _hand_value(self, cards: list[tuple[str, str]]) -> int:
        total = 0
        aces = 0
        for rank, _ in cards:
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

    def _is_blackjack(self, hand: BlackJackHand) -> bool:
        return len(hand.cards) == 2 and self._hand_value(hand.cards) == 21

    def _current_hand(self) -> BlackJackHand:
        return self.hands[self.active_hand_index]

    def _can_double_hand(self, hand: BlackJackHand) -> bool:
        return len(hand.cards) == 2 and not hand.stood and not hand.busted

    def _can_split_hand(self, hand: BlackJackHand) -> bool:
        return len(self.hands) == 1 and len(hand.cards) == 2 and hand.cards[0][0] == hand.cards[1][0]

    def _format_hand(self, cards: list[tuple[str, str]], *, hide_last: bool) -> str:
        labels = [self._card_label(card) for card in cards]
        if hide_last and labels:
            labels = [*labels[:-1], "?"]
        return " | ".join(labels)

    def _format_player_hand(self, hand: BlackJackHand, index: int) -> str:
        total = self._hand_value(hand.cards)
        flags: list[str] = []
        if not self.finished and index == self.active_hand_index:
            flags.append("Сейчас ход")
        if hand.blackjack:
            flags.append("Blackjack")
        if hand.doubled:
            flags.append("Double")
        if hand.busted:
            flags.append("Перебор")
        elif hand.stood:
            flags.append("Зафиксирована")
        suffix = f" ({', '.join(flags)})" if flags else ""
        return (
            f"**Рука {index + 1}**{suffix}\n"
            f"{self._format_hand(hand.cards, hide_last=False)}\n"
            f"Сумма: **{total}** • Ставка: **{hand.bet}** 🪙"
        )

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
        embed.add_field(name="Сумма ставок", value=f"{sum(hand.bet for hand in self.hands)} 🪙", inline=True)
        dealer_total = self._hand_value(self.dealer_hand)
        embed.add_field(
            name="Руки игрока",
            value="\n\n".join(self._format_player_hand(hand, index) for index, hand in enumerate(self.hands)),
            inline=False,
        )
        embed.add_field(
            name="Рука дилера",
            value=f"{self._format_hand(self.dealer_hand, hide_last=not reveal_dealer)}\nСумма: **{dealer_total if reveal_dealer else '?'}**",
            inline=False,
        )
        embed.add_field(name="Статус", value="\n".join(result_lines), inline=False)
        if balance_after is not None:
            embed.add_field(name="Баланс после игры", value=f"{balance_after} 🪙", inline=False)
        embed.set_thumbnail(url=self.player.display_avatar.url)
        embed.set_footer(text=f"Игрок: {self.player.display_name}")
        return embed

    def build_live_embed(self) -> discord.Embed:
        hand = self._current_hand()
        lines = [
            "Ещё — взять ещё одну карту.",
            "Хватит — зафиксировать текущую руку.",
        ]
        if self._can_double_hand(hand):
            lines.append("Удвоить — удвоить ставку, взять одну карту и сразу остановиться.")
        if self._can_split_hand(hand):
            lines.append("Разделить — разбить пару на две независимые руки.")
        return self._build_embed(
            title="Black Jack: ход",
            color=discord.Color.blurple(),
            result_lines=lines,
            reveal_dealer=False,
        )

    def _disable_controls(self) -> None:
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True

    def _refresh_button_states(self) -> None:
        if self.finished:
            self._disable_controls()
            return
        hand = self._current_hand()
        self.hit_button.disabled = hand.stood or hand.busted
        self.stand_button.disabled = hand.stood or hand.busted
        self.double_button.disabled = not self._can_double_hand(hand)
        self.split_button.disabled = not self._can_split_hand(hand)

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
            bet=sum(hand.bet for hand in self.hands),
            result_text=result_text,
            balance_after=balance_after,
        )

    def resolve_opening_hand(self) -> tuple[discord.Embed, int, str] | None:
        player_hand = self.hands[0]
        player_blackjack = self._is_blackjack(player_hand)
        dealer_blackjack = len(self.dealer_hand) == 2 and self._hand_value(self.dealer_hand) == 21
        if not player_blackjack and not dealer_blackjack:
            return None
        self.finished = True
        self._disable_controls()
        self.stop()
        self.cog.unregister_blackjack_game(self.player.id)
        if player_blackjack and dealer_blackjack:
            player_hand.blackjack = True
            balance_after = self.cog.profile_service.get_profile(self.player.id).balance
            title = "Black Jack: ничья"
            color = discord.Color.blurple()
            result_lines = ["У тебя и у дилера Black Jack.", "Ставка возвращена."]
            result_text = "Ничья: у обоих blackjack"
        elif player_blackjack:
            player_hand.blackjack = True
            win_amount = int(player_hand.bet * 1.5)
            bonus_lines: list[str] = []
            if self.cog.shop_service is not None:
                win_amount, bonus_lines = self.cog.shop_service.apply_game_win_bonus(self.player.id, win_amount)
            balance_after = self.cog.profile_service.add_balance(self.player.id, win_amount)
            title = "Black Jack: победа"
            color = discord.Color.green()
            result_lines = ["Натуральный Black Jack.", f"Выплата 3:2: **+{win_amount}** 🪙", *bonus_lines]
            result_text = f"Победа blackjack: {win_amount}"
        else:
            balance_after = self.cog.profile_service.add_balance(self.player.id, -player_hand.bet)
            title = "Black Jack: поражение"
            color = discord.Color.red()
            result_lines = ["Дилер собрал Black Jack.", f"Проигрыш: **-{player_hand.bet}** 🪙"]
            result_text = "Поражение: blackjack дилера"
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

    def _move_to_next_hand(self) -> bool:
        for index in range(self.active_hand_index + 1, len(self.hands)):
            if not self.hands[index].stood and not self.hands[index].busted:
                self.active_hand_index = index
                return True
        return False

    async def _advance_or_resolve(self, interaction: Interaction) -> None:
        if self._move_to_next_hand():
            self._refresh_button_states()
            await interaction.response.edit_message(embed=self.build_live_embed(), view=self)
            return
        await self._resolve_dealer(interaction)

    async def _resolve_dealer(self, interaction: Interaction) -> None:
        while self._hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self._draw_card())
        dealer_total = self._hand_value(self.dealer_hand)
        total_delta = 0
        lines = [f"Сумма дилера: **{dealer_total}**"]
        for index, hand in enumerate(self.hands, start=1):
            player_total = self._hand_value(hand.cards)
            if hand.busted:
                hand.payout_delta = -hand.bet
                hand.result_text = f"Рука {index}: перебор, **-{hand.bet}** 🪙"
            elif dealer_total > 21 or player_total > dealer_total:
                win_amount = hand.bet
                bonus_lines: list[str] = []
                if self.cog.shop_service is not None:
                    win_amount, bonus_lines = self.cog.shop_service.apply_game_win_bonus(self.player.id, win_amount)
                hand.payout_delta = win_amount
                hand.result_text = f"Рука {index}: победа, **+{win_amount}** 🪙"
                if bonus_lines:
                    hand.result_text += f" ({'; '.join(bonus_lines)})"
            elif player_total == dealer_total:
                hand.payout_delta = 0
                hand.result_text = f"Рука {index}: ничья, ставка возвращена"
            else:
                hand.payout_delta = -hand.bet
                hand.result_text = f"Рука {index}: поражение, **-{hand.bet}** 🪙"
            total_delta += hand.payout_delta
            lines.append(hand.result_text)
        balance_after = self.cog.profile_service.add_balance(self.player.id, total_delta) if total_delta else self.cog.profile_service.get_profile(self.player.id).balance
        title = "Black Jack: ничья"
        color = discord.Color.blurple()
        if total_delta > 0:
            title = "Black Jack: победа"
            color = discord.Color.green()
        elif total_delta < 0:
            title = "Black Jack: поражение"
            color = discord.Color.red()
        await self._finish(
            interaction,
            title=title,
            color=color,
            result_lines=lines,
            balance_after=balance_after,
            result_text=f"Дилер {dealer_total}, итог {total_delta}",
        )

    @discord.ui.button(label="Ещё", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: Interaction, _: discord.ui.Button) -> None:
        hand = self._current_hand()
        hand.cards.append(self._draw_card())
        if self._hand_value(hand.cards) > 21:
            hand.busted = True
            hand.stood = True
            await self._advance_or_resolve(interaction)
            return
        self._refresh_button_states()
        await interaction.response.edit_message(embed=self.build_live_embed(), view=self)

    @discord.ui.button(label="Хватит", style=discord.ButtonStyle.blurple)
    async def stand_button(self, interaction: Interaction, _: discord.ui.Button) -> None:
        hand = self._current_hand()
        hand.stood = True
        await self._advance_or_resolve(interaction)

    @discord.ui.button(label="Удвоить", style=discord.ButtonStyle.red)
    async def double_button(self, interaction: Interaction, _: discord.ui.Button) -> None:
        hand = self._current_hand()
        if not self._can_double_hand(hand):
            await interaction.response.send_message("Удвоение доступно только на первых двух картах.", ephemeral=True)
            return
        if self.cog.profile_service.get_profile(self.player.id).balance < hand.bet:
            await interaction.response.send_message("Не хватает монет для удвоения ставки.", ephemeral=True)
            return
        hand.bet *= 2
        hand.doubled = True
        hand.cards.append(self._draw_card())
        if self._hand_value(hand.cards) > 21:
            hand.busted = True
        hand.stood = True
        await self._advance_or_resolve(interaction)

    @discord.ui.button(label="Разделить", style=discord.ButtonStyle.secondary)
    async def split_button(self, interaction: Interaction, _: discord.ui.Button) -> None:
        hand = self._current_hand()
        if not self._can_split_hand(hand):
            await interaction.response.send_message("Разделение доступно только для пары одного достоинства.", ephemeral=True)
            return
        if self.cog.profile_service.get_profile(self.player.id).balance < self.base_bet:
            await interaction.response.send_message("Не хватает монет для второй ставки при split.", ephemeral=True)
            return
        first_card, second_card = hand.cards
        self.hands = [
            BlackJackHand(cards=[first_card, self._draw_card()], bet=self.base_bet),
            BlackJackHand(cards=[second_card, self._draw_card()], bet=self.base_bet),
        ]
        self.active_hand_index = 0
        self._refresh_button_states()
        await interaction.response.edit_message(embed=self.build_live_embed(), view=self)

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

