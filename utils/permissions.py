from __future__ import annotations

import discord

from config import Config


def has_admin_access(member: discord.abc.User | discord.Member) -> bool:
    if not isinstance(member, discord.Member):
        return False

    if member.guild_permissions.administrator:
        return True

    return any(role.id == Config.MOD_ROLE_ID for role in member.roles)
