from discord import Member, Embed

__all__ = ("Display",)


class Display:
    def __init__(self, author: Member, target: Member | None):
        self.author = author
        self.target = target

    def main(self, msg: str):
        embed = Embed(title="Новый репорт!")
        embed.description = (
            f"**От:** {self.author.mention}\n"
            f"**На:** {self.target.mention if self.target else 'Отсутствует'}\n\n"
            f"**Содержание:**\n{msg}"
        )
        embed.set_footer(text=f"ReporterID: {self.author.id} | Status: OPEN")
        return embed

    @staticmethod
    def confirm(embed: Embed, admin: Member):
        embed.title = "Репорт (принят)"
        rid = Display._get_reporter_id(embed)
        embed.set_footer(
            text=f"ReporterID: {rid} | Status: ACCEPTED | By: {admin.name} ({admin.id})",
            icon_url=admin.avatar.url if admin.avatar else None,
        )
        return embed

    @staticmethod
    def reject(embed: Embed, admin: Member):
        embed.title = "Репорт (отклонён)"
        rid = Display._get_reporter_id(embed)
        embed.set_footer(
            text=f"ReporterID: {rid} | Status: REJECTED | By: {admin.name} ({admin.id})",
            icon_url=admin.avatar.url if admin.avatar else None,
        )
        return embed

    @staticmethod
    def close(embed: Embed, closer: Member):
        embed.title = "Репорт (закрыт)"
        rid = Display._get_reporter_id(embed)
        embed.set_footer(
            text=f"ReporterID: {rid} | Status: CLOSED | By: {closer.name} ({closer.id})",
            icon_url=closer.avatar.url if closer.avatar else None,
        )
        return embed

    @staticmethod
    def _get_reporter_id(embed: Embed) -> int | None:
        if not embed.footer or not embed.footer.text:
            return None
        try:
            part = embed.footer.text.split("ReporterID:")[1].strip()
            return int(part.split("|")[0].strip())
        except Exception:
            return None