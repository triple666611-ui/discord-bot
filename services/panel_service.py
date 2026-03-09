import logging

import discord

logger = logging.getLogger(__name__)


class PanelService:
    def __init__(self, repository):
        self.repository = repository

    def get_message_id(self, key: str) -> int | None:
        value = self.repository.get(key)
        return int(value) if value else None

    def set_message_id(self, key: str, message_id: int) -> None:
        self.repository.set(key, int(message_id))

    async def ensure_message(self, *, channel: discord.TextChannel, state_key: str, embed: discord.Embed | None = None, content: str | None = None, view: discord.ui.View | None = None, file: discord.File | None = None, cleanup_markers: set[str] | None = None) -> discord.Message | None:
        if cleanup_markers:
            async for message in channel.history(limit=50):
                if message.author.id != channel.guild.me.id:
                    continue
                if message.content in cleanup_markers:
                    try:
                        await message.delete()
                    except Exception:
                        logger.exception('Не удалось удалить старый marker message')

        saved_message_id = self.get_message_id(state_key)
        if saved_message_id:
            try:
                message = await channel.fetch_message(saved_message_id)
                kwargs = {'content': content, 'embed': embed, 'view': view}
                if file is not None:
                    kwargs['attachments'] = [file]
                await message.edit(**kwargs)
                return message
            except Exception:
                logger.exception('Не удалось обновить panel message: %s', state_key)

        try:
            kwargs = {'content': content, 'embed': embed, 'view': view}
            if file is not None:
                kwargs['file'] = file
            message = await channel.send(**kwargs)
            self.set_message_id(state_key, message.id)
            return message
        except Exception:
            logger.exception('Не удалось отправить panel message: %s', state_key)
            return None
