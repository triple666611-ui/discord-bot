from discord import Interaction, Member, Role
from discord.ui import View, RoleSelect, MentionableSelect

from .embed import Display


class BaseView(View):

    def __init__(self, author: Member):
        super().__init__()

        self.author = author

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        if interaction.user == self.author:
            return True
        await interaction.response.send_message('Вы не можете нажать !!', ephemeral=True)
        return False


class MyMemberSelect(MentionableSelect):

    def __init__(self, message: str):
        self.message = message
        super().__init__(placeholder='Выберите участника или роль', max_values=25)

    async def callback(self, interaction: Interaction):
        for select in self.values:
            if isinstance(select, Role):
                for member in select.members:
                    await member.send(self.message)
            else:
                await select.send(self.message)
        await interaction.response.send_message('Успешно всем отправлены сообщения', ephemeral=True)


class SelectionMembers(BaseView):

    def __init__(self, interface: Display):
        super().__init__(author=interface.author)
        self.add_item(MyMemberSelect(interface.message))
