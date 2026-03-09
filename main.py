import asyncio
import logging

import discord
from discord.ext import commands

from config import Config
from repositories.profile_repository import ProfileRepository
from repositories.panel_state_repository import PanelStateRepository
from repositories.shop_repository import ShopRepository
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
        self.shop_repository = ShopRepository(self.profile_repository.pool)

        # services
        self.profile_service = ProfileService(self.profile_repository)
        self.panel_service = PanelService(self.panel_state_repository)
        from services.shop_service import ShopService
        self.shop_service = ShopService(self.shop_repository, self.profile_service)

        # cogs
        self.cogs_list = (
            "cogs.welcome",
            "cogs.rules",
            "cogs.profiles",
            "cogs.games",
            "cogs.report_panel",
            "cogs.notification",
            "cogs.shop",
        )

    async def setup_hook(self):
        for extension in self.cogs_list:
            try:
                await self.load_extension(extension)
                logger.info(f"Загружен cog: {extension}")
            except Exception:
                logger.exception(f"Ошибка загрузки {extension}")

        try:
            self.tree.clear_commands(guild=None)
            await self.tree.sync()

            synced = await self.tree.sync(guild=Config.SERVER_OBJ)
            logger.info(f"Guild slash-команд синхронизировано: {len(synced)}")
        except Exception:
            logger.exception("Ошибка синхронизации slash-команд")

    async def close(self):

        try:
            self.profile_repository.close()
        finally:
            await super().close()

    async def on_ready(self):
        if self.user is None:
            return

        logger.info(
            f"Бот запущен как {self.user} (ID: {self.user.id})"
    )


async def main():

    Config.validate()

    bot = MyBot()

    async with bot:
        await bot.start(Config.BOT.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())