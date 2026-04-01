import random
from dataclasses import dataclass
from typing import Any, cast

import discord
from discord import Interaction, TextChannel, app_commands
from discord.ext import commands

from config import Config

BLACKJACK_RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
BLACKJACK_SUITS = ["в™ ", "в™Ґ", "в™¦", "в™Ј"]
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
            lines.append("Удвоить — удвоить ставку, взять 1 карту и остановиться.")
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
            title="рџЋ® РРіСЂРѕРІС‹Рµ РєРѕРјР°РЅРґС‹ СЃРµСЂРІРµСЂР°",
            description="РџСЂР°РІРёР»Р° РёРіСЂ, РєР°РЅР°Р»С‹ РґР»СЏ РёРіСЂС‹ Рё Р±Р°Р·РѕРІС‹Рµ РЅР°РіСЂР°РґС‹.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="рџЄ™ /coin вЂ” РњРѕРЅРµС‚РєР°",
            value=(
                f"РљР°РЅР°Р»: <#{Config.COIN_CHANNEL_ID}>\n"
                "Р’С‹Р±РёСЂР°РµС€СЊ **РѕСЂС‘Р»** РёР»Рё **СЂРµС€РєР°** Рё СѓРєР°Р·С‹РІР°РµС€СЊ СЃС‚Р°РІРєСѓ.\n"
                "РЈРіР°РґР°Р» вЂ” **+СЃС‚Р°РІРєР°**. РќРµ СѓРіР°РґР°Р» вЂ” **-СЃС‚Р°РІРєР°**."
            ),
            inline=False,
        )
        embed.add_field(
            name="рџЋІ /dice вЂ” РљРѕСЃС‚Рё",
            value=(
                f"РљР°РЅР°Р»: <#{Config.DICE_CHANNEL_ID}>\n"
                "РўС‹ Р±СЂРѕСЃР°РµС€СЊ РєРѕСЃС‚Рё РїСЂРѕС‚РёРІ Р±РѕС‚Р°.\n"
                "Р•СЃР»Рё С‡РёСЃР»Рѕ Р±РѕР»СЊС€Рµ вЂ” **+СЃС‚Р°РІРєР°**.\n"
                "Р•СЃР»Рё РјРµРЅСЊС€Рµ вЂ” **-СЃС‚Р°РІРєР°**.\n"
                "Р•СЃР»Рё РЅРёС‡СЊСЏ вЂ” Р±Р°Р»Р°РЅСЃ РЅРµ РјРµРЅСЏРµС‚СЃСЏ."
            ),
            inline=False,
        )
        embed.add_field(
            name="рџЋ° /slots вЂ” РЎР»РѕС‚С‹",
            value=(
                f"РљР°РЅР°Р»: <#{Config.SLOTS_CHANNEL_ID}>\n"
                "**рџ’Ћрџ’Ћрџ’Ћ** в†’ **x5**\n"
                "**3 РѕРґРёРЅР°РєРѕРІС‹С…** в†’ **x3**\n"
                "**2 РѕРґРёРЅР°РєРѕРІС‹С…** в†’ **x1.5**\n"
                "РќРµС‚ СЃРѕРІРїР°РґРµРЅРёР№ вЂ” **РїСЂРѕРёРіСЂС‹С€ СЃС‚Р°РІРєРё**."
            ),
            inline=False,
        )
        embed.add_field(
            name="рџѓЏ /blackjack вЂ” Black Jack",
            value=(
                f"РљР°РЅР°Р»: <#{Config.BLACKJACK_CHANNEL_ID}>\n"
                "РРЅС‚РµСЂР°РєС‚РёРІРЅР°СЏ РїР°СЂС‚РёСЏ РїСЂРѕС‚РёРІ РґРёР»РµСЂР° СЃ РєРЅРѕРїРєР°РјРё **Hit** Рё **Stand**.\n"
                "РџРѕР±РµРґР° вЂ” **+СЃС‚Р°РІРєР°**, РЅР°С‚СѓСЂР°Р»СЊРЅС‹Р№ Black Jack вЂ” **x1.5 РѕС‚ СЃС‚Р°РІРєРё**.\n"
                "РџРѕСЂР°Р¶РµРЅРёРµ вЂ” **-СЃС‚Р°РІРєР°**, РЅРёС‡СЊСЏ вЂ” Р±Р°Р»Р°РЅСЃ РЅРµ РјРµРЅСЏРµС‚СЃСЏ."
            ),
            inline=False,
        )
        embed.add_field(
            name="рџЋЃ /daily вЂ” Р•Р¶РµРґРЅРµРІРЅР°СЏ РЅР°РіСЂР°РґР°",
            value=f"Р Р°Р· РІ 24 С‡Р°СЃР° РјРѕР¶РЅРѕ РїРѕР»СѓС‡РёС‚СЊ **{Config.DAILY_REWARD}** рџЄ™.",
            inline=False,
        )
        embed.set_footer(text="Р­С‚Сѓ РёРЅС„РѕСЂРјР°С†РёСЋ РІРёРґРёС€СЊ С‚РѕР»СЊРєРѕ С‚С‹")
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
        embed.add_field(name="РРіСЂР°", value=game_name, inline=True)
        embed.add_field(name="РРіСЂРѕРє", value=player.mention, inline=True)
        embed.add_field(name="РЎС‚Р°РІРєР°", value=f"{bet} рџЄ™", inline=True)
        embed.add_field(name="Р РµР·СѓР»СЊС‚Р°С‚", value="\n".join(result_lines), inline=False)
        embed.add_field(name="Р‘Р°Р»Р°РЅСЃ РїРѕСЃР»Рµ РёРіСЂС‹", value=f"{balance_after} рџЄ™", inline=False)
        embed.set_thumbnail(url=player.display_avatar.url)
        embed.set_footer(text=f"РРіСЂРѕРє: {player.display_name}")
        return embed

    async def send_private_topbalance(self, interaction: Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РЅР° СЃРµСЂРІРµСЂРµ.", ephemeral=True)
            return
        top_data = self.profile_service.get_top_balances(limit=10)
        if not top_data:
            await interaction.response.send_message("РџРѕРєР° РЅРµС‚ РґР°РЅРЅС‹С… РїРѕ Р±Р°Р»Р°РЅСЃСѓ.", ephemeral=True)
            return

        lines: list[str] = []
        medals = {1: "рџҐ‡", 2: "рџҐ€", 3: "рџҐ‰"}
        for index, (user_id, balance) in enumerate(top_data, start=1):
            member = interaction.guild.get_member(user_id)
            user_display = member.mention if member else f"<@{user_id}>"
            prefix = medals.get(index, f"**{index}.**")
            lines.append(f"{prefix} {user_display} вЂ” **{balance}** рџЄ™")

        embed = discord.Embed(
            title="рџ’° РўРѕРї РїРѕ Р±Р°Р»Р°РЅСЃСѓ",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Р­С‚Сѓ РёРЅС„РѕСЂРјР°С†РёСЋ РІРёРґРёС€СЊ С‚РѕР»СЊРєРѕ С‚С‹")
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
        embed = discord.Embed(title="рџ’° Р›РѕРі РєСЂСѓРїРЅРѕР№ СЃС‚Р°РІРєРё", color=discord.Color.gold())
        embed.add_field(name="РРіСЂР°", value=game_name, inline=True)
        embed.add_field(name="РРіСЂРѕРє", value=interaction.user.mention, inline=True)
        embed.add_field(name="РЎС‚Р°РІРєР°", value=f"{bet} рџЄ™", inline=True)
        embed.add_field(name="Р РµР·СѓР»СЊС‚Р°С‚", value=result_text, inline=False)
        embed.add_field(name="Р‘Р°Р»Р°РЅСЃ РїРѕСЃР»Рµ РёРіСЂС‹", value=f"{balance_after} рџЄ™", inline=True)
        embed.set_footer(text=f"User ID: {interaction.user.id}")
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    async def _check_game_channel(self, interaction: Interaction, *, allowed_channel_id: int, game_name: str) -> bool:
        if interaction.channel_id == allowed_channel_id:
            return True
        await interaction.response.send_message(
            f"вќЊ Р’ `{game_name}` РјРѕР¶РЅРѕ РёРіСЂР°С‚СЊ С‚РѕР»СЊРєРѕ РІ РєР°РЅР°Р»Рµ <#{allowed_channel_id}>.",
            ephemeral=True,
        )
        return False

    @app_commands.command(name="games", description="РџРѕРєР°Р·Р°С‚СЊ РїСЂР°РІРёР»Р° РІСЃРµС… РёРіСЂ")
    async def games_cmd(self, interaction: Interaction) -> None:
        await interaction.response.send_message(embed=self.build_games_help_embed(), ephemeral=True)

    @app_commands.command(name="topbalance", description="РџРѕРєР°Р·Р°С‚СЊ С‚РѕРї РёРіСЂРѕРєРѕРІ РїРѕ Р±Р°Р»Р°РЅСЃСѓ")
    async def topbalance_cmd(self, interaction: Interaction) -> None:
        await self.send_private_topbalance(interaction)

    @app_commands.command(name="daily", description="РџРѕР»СѓС‡РёС‚СЊ РµР¶РµРґРЅРµРІРЅСѓСЋ РЅР°РіСЂР°РґСѓ")
    async def daily_cmd(self, interaction: Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РЅР° СЃРµСЂРІРµСЂРµ.", ephemeral=True)
            return
        allowed, left = self.profile_service.can_claim_daily(interaction.user.id)
        if not allowed:
            hours = left // 3600
            minutes = (left % 3600) // 60
            await interaction.response.send_message(
                f"вЏі Р•Р¶РµРґРЅРµРІРЅСѓСЋ РЅР°РіСЂР°РґСѓ СѓР¶Рµ Р·Р°Р±СЂР°Р»Рё. РџРѕРїСЂРѕР±СѓР№ СЃРЅРѕРІР° С‡РµСЂРµР· **{hours} С‡ {minutes} РјРёРЅ**.",
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
            title="рџЋЃ Р•Р¶РµРґРЅРµРІРЅР°СЏ РЅР°РіСЂР°РґР°",
            description=f"РўС‹ РїРѕР»СѓС‡РёР» **{reward_amount}** рџЄ™\nРќРѕРІС‹Р№ Р±Р°Р»Р°РЅСЃ: **{new_balance}** рџЄ™",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"РРіСЂРѕРє: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="coin", description="РџРѕРґР±СЂРѕСЃРёС‚СЊ РјРѕРЅРµС‚РєСѓ Рё СЃС‹РіСЂР°С‚СЊ РЅР° Р±Р°Р»Р°РЅСЃ")
    @app_commands.choices(side=[app_commands.Choice(name="РѕСЂС‘Р»", value="РѕСЂС‘Р»"), app_commands.Choice(name="СЂРµС€РєР°", value="СЂРµС€РєР°")])
    async def coin_cmd(self, interaction: Interaction, side: app_commands.Choice[str], bet: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РЅР° СЃРµСЂРІРµСЂРµ.", ephemeral=True)
            return
        if not await self._check_game_channel(interaction, allowed_channel_id=Config.COIN_CHANNEL_ID, game_name="/coin"):
            return
        if bet <= 0:
            await interaction.response.send_message("вќЊ РЎС‚Р°РІРєР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 0.", ephemeral=True)
            return
        profile = self.profile_service.get_profile(interaction.user.id)
        if profile.balance < bet:
            await interaction.response.send_message(
                f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РјРѕРЅРµС‚. РўРІРѕР№ Р±Р°Р»Р°РЅСЃ: **{profile.balance}** рџЄ™",
                ephemeral=True,
            )
            return

        result = random.choice(["РѕСЂС‘Р»", "СЂРµС€РєР°"])
        win = side.value == result
        if win:
            win_amount = bet
            bonus_lines: list[str] = []
            if self.shop_service is not None:
                win_amount, bonus_lines = self.shop_service.apply_game_win_bonus(interaction.user.id, bet)
            new_balance = self.profile_service.add_balance(interaction.user.id, win_amount)
            embed = self._build_game_embed(
                title="РњРѕРЅРµС‚РєР°: РїРѕР±РµРґР°",
                emoji="рџЄ™",
                color=discord.Color.green(),
                player=interaction.user,
                game_name="РњРѕРЅРµС‚РєР°",
                bet=bet,
                result_lines=[f"РўС‹ РІС‹Р±СЂР°Р»: **{side.value}**", f"Р’С‹РїР°Р»Рѕ: **{result}**", f"Р’С‹РёРіСЂС‹С€: **+{win_amount}** рџЄ™", *bonus_lines],
                balance_after=new_balance,
            )
            result_text = f"РџРѕР±РµРґР°, РІС‹РїР°Р»Рѕ {result}, РІС‹РёРіСЂС‹С€ {win_amount}"
        else:
            new_balance = self.profile_service.add_balance(interaction.user.id, -bet)
            embed = self._build_game_embed(
                title="РњРѕРЅРµС‚РєР°: РїРѕСЂР°Р¶РµРЅРёРµ",
                emoji="рџЄ™",
                color=discord.Color.red(),
                player=interaction.user,
                game_name="РњРѕРЅРµС‚РєР°",
                bet=bet,
                result_lines=[f"РўС‹ РІС‹Р±СЂР°Р»: **{side.value}**", f"Р’С‹РїР°Р»Рѕ: **{result}**", f"РџСЂРѕРёРіСЂС‹С€: **-{bet}** рџЄ™"],
                balance_after=new_balance,
            )
            result_text = f"РџРѕСЂР°Р¶РµРЅРёРµ, РІС‹РїР°Р»Рѕ {result}"
        await interaction.response.send_message(embed=embed)
        await self._send_high_stake_log(interaction, game_name="РњРѕРЅРµС‚РєР°", bet=bet, result_text=result_text, balance_after=new_balance)

    @app_commands.command(name="dice", description="Р‘СЂРѕСЃРёС‚СЊ РєРѕСЃС‚Рё РїСЂРѕС‚РёРІ Р±РѕС‚Р° Рё СЃС‹РіСЂР°С‚СЊ РЅР° Р±Р°Р»Р°РЅСЃ")
    async def dice_cmd(self, interaction: Interaction, bet: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РЅР° СЃРµСЂРІРµСЂРµ.", ephemeral=True)
            return
        if not await self._check_game_channel(interaction, allowed_channel_id=Config.DICE_CHANNEL_ID, game_name="/dice"):
            return
        if bet <= 0:
            await interaction.response.send_message("вќЊ РЎС‚Р°РІРєР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 0.", ephemeral=True)
            return
        profile = self.profile_service.get_profile(interaction.user.id)
        if profile.balance < bet:
            await interaction.response.send_message(
                f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РјРѕРЅРµС‚. РўРІРѕР№ Р±Р°Р»Р°РЅСЃ: **{profile.balance}** рџЄ™",
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
                title="РљРѕСЃС‚Рё: РїРѕР±РµРґР°",
                emoji="рџЋІ",
                color=discord.Color.green(),
                player=interaction.user,
                game_name="РљРѕСЃС‚Рё",
                bet=bet,
                result_lines=[f"РўРІРѕР№ Р±СЂРѕСЃРѕРє: **{user_roll}**", f"Р‘СЂРѕСЃРѕРє Р±РѕС‚Р°: **{bot_roll}**", f"Р’С‹РёРіСЂС‹С€: **+{win_amount}** рџЄ™", *bonus_lines],
                balance_after=new_balance,
            )
            result_text = f"РџРѕР±РµРґР°: РёРіСЂРѕРє {user_roll}, Р±РѕС‚ {bot_roll}, РІС‹РёРіСЂС‹С€ {win_amount}"
        elif user_roll < bot_roll:
            new_balance = self.profile_service.add_balance(interaction.user.id, -bet)
            embed = self._build_game_embed(
                title="РљРѕСЃС‚Рё: РїРѕСЂР°Р¶РµРЅРёРµ",
                emoji="рџЋІ",
                color=discord.Color.red(),
                player=interaction.user,
                game_name="РљРѕСЃС‚Рё",
                bet=bet,
                result_lines=[f"РўРІРѕР№ Р±СЂРѕСЃРѕРє: **{user_roll}**", f"Р‘СЂРѕСЃРѕРє Р±РѕС‚Р°: **{bot_roll}**", f"РџСЂРѕРёРіСЂС‹С€: **-{bet}** рџЄ™"],
                balance_after=new_balance,
            )
            result_text = f"РџРѕСЂР°Р¶РµРЅРёРµ: РёРіСЂРѕРє {user_roll}, Р±РѕС‚ {bot_roll}"
        else:
            new_balance = profile.balance
            embed = self._build_game_embed(
                title="РљРѕСЃС‚Рё: РЅРёС‡СЊСЏ",
                emoji="рџЋІ",
                color=discord.Color.blurple(),
                player=interaction.user,
                game_name="РљРѕСЃС‚Рё",
                bet=bet,
                result_lines=[f"РўРІРѕР№ Р±СЂРѕСЃРѕРє: **{user_roll}**", f"Р‘СЂРѕСЃРѕРє Р±РѕС‚Р°: **{bot_roll}**", "РќРёС‡СЊСЏ: Р±Р°Р»Р°РЅСЃ РЅРµ РёР·РјРµРЅРёР»СЃСЏ"],
                balance_after=new_balance,
            )
            result_text = f"РќРёС‡СЊСЏ: РёРіСЂРѕРє {user_roll}, Р±РѕС‚ {bot_roll}"
        await interaction.response.send_message(embed=embed)
        await self._send_high_stake_log(interaction, game_name="РљРѕСЃС‚Рё", bet=bet, result_text=result_text, balance_after=new_balance)

    @app_commands.command(name="slots", description="РЎС‹РіСЂР°С‚СЊ РІ СЃР»РѕС‚С‹ РЅР° Р±Р°Р»Р°РЅСЃ")
    async def slots_cmd(self, interaction: Interaction, bet: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РЅР° СЃРµСЂРІРµСЂРµ.", ephemeral=True)
            return
        if not await self._check_game_channel(interaction, allowed_channel_id=Config.SLOTS_CHANNEL_ID, game_name="/slots"):
            return
        if bet <= 0:
            await interaction.response.send_message("вќЊ РЎС‚Р°РІРєР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 0.", ephemeral=True)
            return
        profile = self.profile_service.get_profile(interaction.user.id)
        if profile.balance < bet:
            await interaction.response.send_message(
                f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РјРѕРЅРµС‚. РўРІРѕР№ Р±Р°Р»Р°РЅСЃ: **{profile.balance}** рџЄ™",
                ephemeral=True,
            )
            return

        symbols = ["рџЌ’", "рџЌ‹", "рџ””", "7пёЏвѓЈ", "рџ’Ћ"]
        roll = [random.choice(symbols) for _ in range(3)]
        vip_slot_active = self.shop_service.consume_vip_slot_effect(interaction.user.id) if self.shop_service is not None else False
        if vip_slot_active and len(set(roll)) == 3:
            chosen = random.choice(symbols)
            roll[1] = chosen
            roll[2] = chosen
        multiplier = 0.0
        result_name = "РџСЂРѕРёРіСЂС‹С€"
        if roll == ["рџ’Ћ", "рџ’Ћ", "рџ’Ћ"]:
            multiplier = 5.0
            result_name = "Р”Р¶РµРєРїРѕС‚"
        elif roll[0] == roll[1] == roll[2]:
            multiplier = 3.0
            result_name = "РўСЂРѕР№РЅРѕРµ СЃРѕРІРїР°РґРµРЅРёРµ"
        elif roll[0] == roll[1] or roll[0] == roll[2] or roll[1] == roll[2]:
            multiplier = 1.5
            result_name = "Р”РІРѕР№РЅРѕРµ СЃРѕРІРїР°РґРµРЅРёРµ"

        if multiplier == 0.0:
            new_balance = self.profile_service.add_balance(interaction.user.id, -bet)
            embed = self._build_game_embed(
                title="РЎР»РѕС‚С‹: РїСЂРѕРёРіСЂС‹С€",
                emoji="рџЋ°",
                color=discord.Color.red(),
                player=interaction.user,
                game_name="РЎР»РѕС‚С‹",
                bet=bet,
                result_lines=[f"РљРѕРјР±РёРЅР°С†РёСЏ: **{' | '.join(roll)}**", f"Р РµР·СѓР»СЊС‚Р°С‚: **{result_name}**", f"РџСЂРѕРёРіСЂС‹С€: **-{bet}** рџЄ™"],
                balance_after=new_balance,
            )
            result_text = f"{result_name}: {' | '.join(roll)}"
        else:
            win_amount = int(bet * multiplier)
            bonus_lines: list[str] = []
            if vip_slot_active:
                bonus_lines.append("рџЋ° РЎСЂР°Р±РѕС‚Р°Р» VIP СЃР»РѕС‚: РјРёРЅРёРјСѓРј РґРІРѕР№РЅРѕРµ СЃРѕРІРїР°РґРµРЅРёРµ РіР°СЂР°РЅС‚РёСЂРѕРІР°РЅРѕ.")
            if self.shop_service is not None:
                win_amount, extra_bonus_lines = self.shop_service.apply_game_win_bonus(interaction.user.id, win_amount)
                bonus_lines.extend(extra_bonus_lines)
            new_balance = self.profile_service.add_balance(interaction.user.id, win_amount)
            embed = self._build_game_embed(
                title="РЎР»РѕС‚С‹: РїРѕР±РµРґР°",
                emoji="рџЋ°",
                color=discord.Color.green(),
                player=interaction.user,
                game_name="РЎР»РѕС‚С‹",
                bet=bet,
                result_lines=[
                    f"РљРѕРјР±РёРЅР°С†РёСЏ: **{' | '.join(roll)}**",
                    f"Р РµР·СѓР»СЊС‚Р°С‚: **{result_name}**",
                    f"РњРЅРѕР¶РёС‚РµР»СЊ: **x{multiplier}**",
                    f"Р’С‹РёРіСЂС‹С€: **+{win_amount}** рџЄ™",
                    *bonus_lines,
                ],
                balance_after=new_balance,
            )
            result_text = f"{result_name}: {' | '.join(roll)} | x{multiplier}"
        await interaction.response.send_message(embed=embed)
        await self._send_high_stake_log(interaction, game_name="РЎР»РѕС‚С‹", bet=bet, result_text=result_text, balance_after=new_balance)

    @app_commands.command(name="blackjack", description="РЎС‹РіСЂР°С‚СЊ РІ Black Jack РїСЂРѕС‚РёРІ РґРёР»РµСЂР°")
    async def blackjack_cmd(self, interaction: Interaction, bet: int) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("РљРѕРјР°РЅРґР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РЅР° СЃРµСЂРІРµСЂРµ.", ephemeral=True)
            return
        if not await self._check_game_channel(interaction, allowed_channel_id=Config.BLACKJACK_CHANNEL_ID, game_name="/blackjack"):
            return
        if bet <= 0:
            await interaction.response.send_message("вќЊ РЎС‚Р°РІРєР° РґРѕР»Р¶РЅР° Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ 0.", ephemeral=True)
            return
        if interaction.user.id in self.active_blackjack_games:
            await interaction.response.send_message("вќЊ РЈ С‚РµР±СЏ СѓР¶Рµ РµСЃС‚СЊ Р°РєС‚РёРІРЅР°СЏ РїР°СЂС‚РёСЏ РІ Black Jack. Р—Р°РєРѕРЅС‡Рё РµС‘ РёР»Рё РґРѕР¶РґРёСЃСЊ С‚Р°Р№Рј-Р°СѓС‚Р°.", ephemeral=True)
            return

        profile = self.profile_service.get_profile(interaction.user.id)
        if profile.balance < bet:
            await interaction.response.send_message(
                f"вќЊ РќРµРґРѕСЃС‚Р°С‚РѕС‡РЅРѕ РјРѕРЅРµС‚. РўРІРѕР№ Р±Р°Р»Р°РЅСЃ: **{profile.balance}** рџЄ™",
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



