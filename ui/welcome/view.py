import discord
from discord.ui import Select, View
from config import Config

class RolesSelect(Select):
    def __init__(self):
        options = [discord.SelectOption(label=name[:100], value=str(role_id)) for name, role_id in Config.ROLES.SELF_ROLES.items()]
        super().__init__(placeholder='🎭 Выберите роли (можно несколько)', min_values=0, max_values=min(len(options), 25), options=options, custom_id='welcome_panel:roles_select')

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message('Это работает только на сервере.', ephemeral=True)
            return
        member = interaction.user
        guild = interaction.guild
        allowed_ids = set(Config.ROLES.SELF_ROLES.values())
        selected_ids = {int(value) for value in self.values}
        current_ids = {role.id for role in member.roles if role.id in allowed_ids}
        to_add = [guild.get_role(role_id) for role_id in selected_ids - current_ids]
        to_remove = [guild.get_role(role_id) for role_id in current_ids - selected_ids]
        to_add = [role for role in to_add if role is not None]
        to_remove = [role for role in to_remove if role is not None]
        try:
            if to_remove:
                await member.remove_roles(*to_remove, reason='Welcome panel roles select')
            if to_add:
                await member.add_roles(*to_add, reason='Welcome panel roles select')
        except discord.Forbidden:
            await interaction.response.send_message('❌ Бот не может выдать или снять эти роли.', ephemeral=True)
            return
        except Exception:
            await interaction.response.send_message('❌ Ошибка при обновлении ролей.', ephemeral=True)
            return
        await interaction.response.send_message('✅ Роли обновлены.', ephemeral=True)

class WelcomePanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RolesSelect())
        self.add_item(discord.ui.Button(label='📜 Правила', style=discord.ButtonStyle.link, url=f'https://discord.com/channels/{Config.BOT.SERVER_ID}/{Config.CHANNELS.RULES_CHANNEL_ID}'))
