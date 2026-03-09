import discord
from typing import Any, cast
from discord.ext.commands import Bot, Cog

from config import Config


class RulesCog(Cog):
    OLD_MARKERS = {"[rules_panel]"}

    def __init__(self, bot: Bot):
        self.bot = bot
        self.panel_service = cast(Any, bot).panel_service

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Правила сервера",
            description=(
                "Добро пожаловать! Чтобы всем было комфортно общаться, соблюдайте правила сервера.\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "**1️⃣ Уважение**\n"
                "• Не оскорбляйте других участников\n"
                "• Запрещены токсичность и провокации\n"
                "• Уважайте мнение других пользователей\n\n"
                "**2️⃣ Запрещённый контент**\n"
                "• NSFW-контент запрещён\n"
                "• Реклама без разрешения запрещена\n"
                "• Спам, флуд и бессмысленные сообщения запрещены\n\n"
                "**3️⃣ Поведение в каналах**\n"
                "• Используйте каналы по назначению\n"
                "• Не злоупотребляйте упоминаниями\n"
                "• Следуйте указаниям администрации и модерации\n\n"
                "**4️⃣ Игровая система**\n"
                "• Используйте игровые команды только в предназначенных каналах\n"
                "• Не злоупотребляйте багами и ошибками системы\n"
                "• Для просмотра правил игр используйте `/games`\n\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "⚠️ **За нарушение правил могут применяться меры:**\n"
                "• предупреждение\n"
                "• мут\n"
                "• ограничение доступа\n"
                "• бан"
            ),
            color=0x5865F2,
        )
        embed.set_footer(text='Соблюдайте правила и приятного общения')
        return embed

    async def ensure_rules_message(self) -> None:
        guild = self.bot.get_guild(Config.BOT.SERVER_ID)
        if guild is None:
            return
        channel = guild.get_channel(Config.CHANNELS.RULES_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        await self.panel_service.ensure_message(
            channel=channel,
            state_key='rules_panel_message_id',
            embed=self.build_embed(),
            cleanup_markers=self.OLD_MARKERS,
        )

    @Cog.listener()
    async def on_ready(self) -> None:
        await self.ensure_rules_message()


async def setup(bot: Bot):
    await bot.add_cog(RulesCog(bot), guild=Config.BOT.SERVER_OBJECT)
