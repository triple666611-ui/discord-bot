import asyncio
import logging

import discord
from discord.ext import commands

from config import Config
from repositories.profile_repository import ProfileRepository
from repositories.panel_state_repository import PanelStateRepository
from services.panel_service import PanelService
from services.profile_service import ProfileService


logging.basicConfig(
    level=logging.INFO,
    format='[{asctime}] [{levelname:<8}] {name}: {message}',
    style='{',
)

logger = logging.getLogger("bot")


class MyBot(commands.Bot):

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.messages = True
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=Config.BOT.PREFIX,
            intents=intents,
            help_command=None
        )

        # repositories
        self.profile_repository = ProfileRepository(Config.DATA.PROFILES_DB_PATH)
        self.panel_state_repository = PanelStateRepository(Config.DATA.PANEL_STATE_PATH)

        # services
        self.profile_service = ProfileService(self.profile_repository)
        self.panel_service = PanelService(self.panel_state_repository)

        # cogs
        self.cogs_list = (
            "cogs.welcome",
            "cogs.rules",
            "cogs.profiles",
            "cogs.games",
            "cogs.report_panel",
            "cogs.notification",
        )

    async def setup_hook(self):

        for extension in self.cogs_list:
            try:
                await self.load_extension(extension)
                logger.info(f"Загружен cog: {extension}")
            except Exception:
                logger.exception(f"Ошибка загрузки {extension}")

    async def close(self):

        try:
            self.profile_repository.close()
        finally:
            await super().close()

    async def on_ready(self):

        if self.user is None:
            return

        try:
            synced = await self.tree.sync()

            logger.info(
                f"Бот запущен как {self.user} (ID: {self.user.id}) | "
                f"Slash-команд синхронизировано: {len(synced)}"
            )

        except Exception:
            logger.exception("Ошибка синхронизации slash-команд")


async def main():

    Config.validate()

    bot = MyBot()

    async with bot:
        await bot.start(Config.BOT.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())