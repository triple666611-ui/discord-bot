import discord
from discord import Interaction, ui

from .modal import ReportModal


class ReportPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Создать тикет",
        style=discord.ButtonStyle.success,
        emoji="📩",
        custom_id="report:create_ticket"
    )
    async def create_ticket(
        self,
        interaction: Interaction,
        button: ui.Button
    ) -> None:
        await interaction.response.send_modal(ReportModal())