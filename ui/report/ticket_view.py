import discord
from discord import Interaction, TextChannel, ui

from config import Config


def _get_ticket_owner_id(channel: discord.abc.GuildChannel) -> int | None:
    topic = getattr(channel, "topic", None)
    if not topic:
        return None

    try:
        return int(topic.strip())
    except ValueError:
        return None


def _build_claimed_embed(
    original: discord.Embed | None,
    moderator: discord.Member
) -> discord.Embed:
    if original is None:
        embed = discord.Embed(
            title="📨 Тикет принят",
            description="Тикет был принят модератором.",
            color=discord.Color.green()
        )
        embed.add_field(name="Статус", value=f"🟢 Принят: {moderator.mention}", inline=False)
        return embed

    embed = discord.Embed.from_dict(original.to_dict())
    embed.color = discord.Color.green()

    replaced = False
    for index, field in enumerate(embed.fields):
        if field.name and field.name.lower() == "статус":
            embed.set_field_at(index, name="Статус", value=f"🟢 Принят: {moderator.mention}", inline=field.inline)
            replaced = True
            break

    if not replaced:
        embed.add_field(name="Статус", value=f"🟢 Принят: {moderator.mention}", inline=False)

    return embed


def _build_close_log_embed(
    ticket_channel: discord.TextChannel,
    closer: discord.Member,
    owner: discord.Member | None
) -> discord.Embed:
    embed = discord.Embed(
        title="🔒 Тикет закрыт",
        color=discord.Color.red()
    )

    embed.add_field(name="Канал", value=ticket_channel.name, inline=True)
    embed.add_field(name="Закрыл", value=closer.mention, inline=True)
    embed.add_field(
        name="Автор тикета",
        value=owner.mention if owner else "Не найден",
        inline=True
    )

    embed.set_footer(text=f"Ticket channel ID: {ticket_channel.id}")
    return embed


class CloseTicketView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Закрыть тикет",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket:close"
    )
    async def close_ticket(
        self,
        interaction: Interaction,
        button: ui.Button
    ) -> None:
        channel = interaction.channel
        guild = interaction.guild
        user = interaction.user

        if guild is None or channel is None or not isinstance(channel, TextChannel):
            await interaction.response.send_message(
                "❌ Не удалось определить канал тикета.",
                ephemeral=True
            )
            return

        if not isinstance(user, discord.Member):
            await interaction.response.send_message(
                "❌ Не удалось определить пользователя.",
                ephemeral=True
            )
            return

        owner_id = _get_ticket_owner_id(channel)
        mod_role = guild.get_role(Config.MOD_ROLE_ID)
        is_owner = owner_id == user.id
        is_mod = mod_role in user.roles if mod_role else False

        if not is_owner and not is_mod:
            await interaction.response.send_message(
                "❌ Закрыть тикет может только его автор или модератор.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 Тикет закрывается...",
            ephemeral=True
        )

        log_channel = guild.get_channel(Config.REPORT_CHANNEL_ID)
        owner = guild.get_member(owner_id) if owner_id else None

        if isinstance(log_channel, TextChannel):
            try:
                embed = _build_close_log_embed(
                    ticket_channel=channel,
                    closer=user,
                    owner=owner
                )
                await log_channel.send(embed=embed)
            except Exception:
                pass

        try:
            await channel.delete(reason=f"Тикет закрыт пользователем {user} ({user.id})")
        except Exception as error:
            try:
                await interaction.followup.send(
                    f"❌ Не удалось удалить канал: {error}",
                    ephemeral=True
                )
            except Exception:
                pass


class TicketClaimView(ui.View):
    def __init__(
        self,
        ticket_channel_id: int,
        claimed_by_id: int = 0,
        disabled: bool = False
    ):
        super().__init__(timeout=None)
        self.ticket_channel_id = ticket_channel_id
        self.claimed_by_id = claimed_by_id

        button = ui.Button(
            label="Принять тикет",
            style=discord.ButtonStyle.primary,
            emoji="✅",
            disabled=disabled,
            custom_id=f"ticket:claim:{ticket_channel_id}"
        )
        button.callback = self.claim_ticket
        self.add_item(button)

    async def claim_ticket(self, interaction: Interaction) -> None:
        guild = interaction.guild
        user = interaction.user

        if guild is None or not isinstance(user, discord.Member):
            await interaction.response.send_message(
                "❌ Не удалось определить сервер или пользователя.",
                ephemeral=True
            )
            return

        mod_role = guild.get_role(Config.MOD_ROLE_ID)
        if mod_role is None or mod_role not in user.roles:
            await interaction.response.send_message(
                "❌ Только модератор может принять тикет.",
                ephemeral=True
            )
            return

        ticket_channel = guild.get_channel(self.ticket_channel_id)
        if not isinstance(ticket_channel, TextChannel):
            await interaction.response.send_message(
                "❌ Канал тикета не найден.",
                ephemeral=True
            )
            return

        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True
                item.label = "Тикет принят"

        embed = _build_claimed_embed(
            interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None,
            moderator=user
        )

        try:
            await ticket_channel.send(
                embed=discord.Embed(
                    title="✅ Тикет принят",
                    description=f"Тикет взял в работу модератор {user.mention}.",
                    color=discord.Color.green()
                )
            )
        except Exception:
            pass

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )