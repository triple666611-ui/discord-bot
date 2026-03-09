from discord import TextChannel
from discord.ext.commands import Bot, Cog

from config import Config
from ui.report.panel_view import ReportPanelView
from ui.report.ticket_view import CloseTicketView, TicketClaimView


PANEL_TEXT = (
    "🛡 **Репорты и тикеты**\n"
    "Если у вас возникла проблема, нажмите кнопку ниже.\n"
    "Опишите ситуацию максимально подробно и, по возможности, приложите доказательства."
)


class ReportPanelCog(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    async def ensure_panel_message(self) -> None:
        guild = self.bot.get_guild(Config.SERVER_OBJ.id)
        if guild is None:
            return

        channel = guild.get_channel(Config.REPORT_PANEL_CHANNEL_ID)
        if not isinstance(channel, TextChannel):
            return

        async for message in channel.history(limit=50):
            if self.bot.user is None:
                return

            if message.author.id != self.bot.user.id:
                continue

            if "Репорты и тикеты" in (message.content or ""):
                try:
                    await message.edit(content=PANEL_TEXT, view=ReportPanelView())
                except Exception:
                    pass
                return

        try:
            await channel.send(content=PANEL_TEXT, view=ReportPanelView())
        except Exception:
            pass

    @Cog.listener()
    async def on_ready(self) -> None:
        try:
            self.bot.add_view(ReportPanelView())
            self.bot.add_view(CloseTicketView())
            self.bot.add_view(TicketClaimView(ticket_channel_id=0, claimed_by_id=0, disabled=True))
        except Exception:
            pass

        await self.ensure_panel_message()


async def setup(bot: Bot):
    await bot.add_cog(ReportPanelCog(bot), guild=Config.SERVER_OBJ)