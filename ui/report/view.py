import discord
from discord import Interaction
from discord.ui import View, button, Button

from config import Config
from cogs.ui.report.embed import Display


def _is_moderator(member: discord.Member):
    perms = member.guild_permissions
    return perms.administrator or perms.manage_messages


class ReportInteraction(View):

    def __init__(self, display: Display):
        super().__init__(timeout=None)
        self.display = display

    @button(
        label="Принять",
        style=discord.ButtonStyle.success,
        custom_id="report_accept"
    )
    async def accept(self, interaction: Interaction, btn: Button):

        member = interaction.user

        if not _is_moderator(member):

            await interaction.response.send_message(
                "❌ Только модератор может принять репорт",
                ephemeral=True
            )
            return

        message = interaction.message

        if not message.embeds:
            return

        embed = message.embeds[0]

        # обновляем embed
        await message.edit(
            embed=Display.confirm(embed, member),
            view=None
        )

        guild = interaction.guild
        ticket_channel = None

        if guild:

            # ищем тикет по ID сообщения репорта
            for channel in guild.text_channels:

                if str(message.id) in channel.name:

                    ticket_channel = channel
                    break

        # отправляем сообщение в тикет
        if ticket_channel:

            try:

                await ticket_channel.send(
                    f"🛡 **Репорт принят модератором**\n"
                    f"Модератор: {member.mention}"
                )

            except:
                pass

        # отправляем ссылку модератору
        if ticket_channel:

            await interaction.response.send_message(
                f"✅ Репорт принят\n\n"
                f"💬 Перейти в тикет:\n{ticket_channel.jump_url}",
                ephemeral=True
            )

        else:

            await interaction.response.send_message(
                "⚠️ Репорт принят, но тикет не найден",
                ephemeral=True
            )

    @button(
        label="Отклонить",
        style=discord.ButtonStyle.danger,
        custom_id="report_reject"
    )
    async def reject(self, interaction: Interaction, btn: Button):

        member = interaction.user

        if not _is_moderator(member):

            await interaction.response.send_message(
                "❌ Только модератор может отклонить репорт",
                ephemeral=True
            )
            return

        message = interaction.message

        if not message.embeds:
            return

        embed = message.embeds[0]

        await message.edit(
            embed=Display.reject(embed, member),
            view=None
        )

        await interaction.response.send_message(
            "❌ Репорт отклонён",
            ephemeral=True
        )