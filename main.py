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
            help_command=None,
        )

        self.guild_commands_synced = False

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

    async def sync_guild_commands(self) -> None:
        synced = await self.tree.sync(guild=Config.SERVER_OBJ)
        self.guild_commands_synced = True
        logger.info(f"Guild slash commands synced: {len(synced)}")

    async def setup_hook(self) -> None:
        for extension in self.cogs_list:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded cog: {extension}")
            except Exception:
                logger.exception(f"Failed to load cog: {extension}")

        try:
            await self.sync_guild_commands()
        except Exception:
            logger.exception("Failed to sync slash commands")

    async def close(self) -> None:
        try:
            self.profile_repository.close()
        finally:
            await super().close()

    async def on_ready(self) -> None:
        if self.user is None:
            return

        logger.info(f"Bot started as {self.user} (ID: {self.user.id})")

        if not self.guild_commands_synced:
            try:
                await self.sync_guild_commands()
            except Exception:
                logger.exception("Failed to re-sync slash commands in on_ready")


async def main() -> None:
    Config.validate()

    bot = MyBot()

    async with bot:
        await bot.start(Config.BOT.TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
