import re
import time

import discord
from discord import Interaction, TextChannel, TextStyle
from discord.ui import Modal, TextInput

from config import Config
from .ticket_view import CloseTicketView, TicketClaimView


PROCESSING_USERS: set[int] = set()
BUTTON_COOLDOWNS: dict[int, float] = {}


def _parse_next_ticket_number(category: discord.CategoryChannel) -> int:
    max_number = 0
    pattern = re.compile(r"^ticket-(\d{3,})$")

    for channel in category.text_channels:
        match = pattern.match(channel.name)
        if match:
            try:
                value = int(match.group(1))
                if value > max_number:
                    max_number = value
            except ValueError:
                continue

    return max_number + 1


def _build_ticket_open_embed(
    user: discord.Member,
    ticket_number: int,
    description: str
) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎫 Тикет #{ticket_number:03d}",
        description=(
            "Спасибо за обращение.\n"
            "Опишите дополнительные детали, если это нужно, и ожидайте ответа модератора."
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(name="Автор", value=user.mention, inline=True)
    embed.add_field(name="Номер", value=f"#{ticket_number:03d}", inline=True)
    embed.add_field(name="Статус", value="🟡 Ожидает принятия", inline=True)
    embed.add_field(name="Описание проблемы", value=description[:1024], inline=False)

    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"User ID: {user.id}")

    return embed


def _build_mod_log_embed(
    user: discord.Member,
    ticket_channel: discord.TextChannel,
    ticket_number: int,
    description: str
) -> discord.Embed:
    embed = discord.Embed(
        title=f"📨 Новый тикет #{ticket_number:03d}",
        description="Нажмите кнопку ниже, чтобы принять тикет.",
        color=discord.Color.orange()
    )

    embed.add_field(name="Пользователь", value=user.mention, inline=True)
    embed.add_field(name="Канал", value=ticket_channel.mention, inline=True)
    embed.add_field(name="Статус", value="🟡 Не принят", inline=True)
    embed.add_field(name="Описание", value=description[:1024], inline=False)

    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"Ticket channel ID: {ticket_channel.id}")

    return embed


class ReportModal(Modal, title="Создание тикета"):
    description = TextInput(
        label="Опишите проблему",
        placeholder="Например: пользователь нарушает правила, спамит, оскорбляет...",
        style=TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: Interaction) -> None:
        guild = interaction.guild
        user = interaction.user

        if guild is None or not isinstance(user, discord.Member):
            await interaction.response.send_message(
                "❌ Не удалось определить сервер или пользователя.",
                ephemeral=True
            )
            return

        now = time.time()
        last_click = BUTTON_COOLDOWNS.get(user.id, 0.0)

        if now - last_click < 5:
            await interaction.response.send_message(
                "⏳ Подожди несколько секунд перед повторной отправкой.",
                ephemeral=True
            )
            return

        if user.id in PROCESSING_USERS:
            await interaction.response.send_message(
                "⏳ Твой тикет уже создаётся. Подожди пару секунд.",
                ephemeral=True
            )
            return

        category = guild.get_channel(Config.TICKETS_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "❌ Категория тикетов не найдена.",
                ephemeral=True
            )
            return

        for channel in category.text_channels:
            if channel.topic == str(user.id):
                await interaction.response.send_message(
                    f"❌ У тебя уже есть открытый тикет: {channel.mention}",
                    ephemeral=True
                )
                return

        PROCESSING_USERS.add(user.id)
        BUTTON_COOLDOWNS[user.id] = now

        try:
            ticket_number = _parse_next_ticket_number(category)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=False
                ),
                user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                )
            }

            mod_role = guild.get_role(Config.MOD_ROLE_ID)
            if mod_role is not None:
                overwrites[mod_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True
                )

            ticket_channel = await guild.create_text_channel(
                name=f"ticket-{ticket_number:03d}",
                category=category,
                topic=str(user.id),
                overwrites=overwrites,
                reason=f"Создан тикет пользователем {user} ({user.id})"
            )

            open_embed = _build_ticket_open_embed(
                user=user,
                ticket_number=ticket_number,
                description=self.description.value
            )

            await ticket_channel.send(
                content=f"{user.mention}" + (f" {mod_role.mention}" if mod_role else ""),
                embed=open_embed,
                view=CloseTicketView()
            )

            mod_log_channel = guild.get_channel(Config.REPORT_CHANNEL_ID)
            if isinstance(mod_log_channel, TextChannel):
                mod_embed = _build_mod_log_embed(
                    user=user,
                    ticket_channel=ticket_channel,
                    ticket_number=ticket_number,
                    description=self.description.value
                )

                await mod_log_channel.send(
                    embed=mod_embed,
                    view=TicketClaimView(ticket_channel_id=ticket_channel.id)
                )

            await interaction.response.send_message(
                f"✅ Тикет создан: {ticket_channel.mention}",
                ephemeral=True
            )

        except Exception as error:
            await interaction.response.send_message(
                f"❌ Не удалось создать тикет: {error}",
                ephemeral=True
            )
        finally:
            PROCESSING_USERS.discard(user.id)