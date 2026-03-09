from discord import Member, Embed


class Display:

    def __init__(self, author: Member, message):
        self.author = author
        self.message = message

    def main(self):
        embed = Embed()
        embed.title = f'Рассылка - {self.author.name}'
        embed.description = 'Все выбранные участники или участники у которых есть определенные роли, ' \
                            f'получат это сообщение: {self.message}'
        return embed
