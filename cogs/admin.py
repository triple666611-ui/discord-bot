
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import discord
from discord import app_commands
from discord.ext import commands

from config import Config
from repositories.admin_audit_repository import AdminAuditRepository
from repositories.warning_repository import WarningRepository
from utils.permissions import has_admin_access

EMERALD = 0x52DAB4
DANGER = 0xE05A5A

ECONOMY_ACTIONS: dict[str, dict[str, str | bool]] = {
    'balance_set': {
        'label': 'Установить баланс',
        'summary': 'Задаёт пользователю точное значение баланса.',
        'needs_amount': True,
        'input_label': 'Новый баланс',
        'placeholder': 'Например, 5000',
    },
    'balance_add': {
        'label': 'Добавить баланс',
        'summary': 'Начисляет валюту без перезаписи текущего баланса.',
        'needs_amount': True,
        'input_label': 'Сколько добавить',
        'placeholder': 'Например, 250',
    },
    'balance_remove': {
        'label': 'Снять баланс',
        'summary': 'Списывает часть валюты у пользователя.',
        'needs_amount': True,
        'input_label': 'Сколько снять',
        'placeholder': 'Например, 100',
        'dangerous': True,
    },
}

PROFILE_ACTIONS: dict[str, dict[str, str | bool]] = {
    'xp_set': {
        'label': 'Установить XP',
        'summary': 'Задаёт пользователю точное количество XP.',
        'needs_amount': True,
        'input_label': 'Новое XP',
        'placeholder': 'Например, 1200',
    },
    'xp_add': {
        'label': 'Добавить XP',
        'summary': 'Начисляет дополнительное XP.',
        'needs_amount': True,
        'input_label': 'Сколько добавить',
        'placeholder': 'Например, 300',
    },
    'rep_set': {
        'label': 'Установить репутацию',
        'summary': 'Задаёт точное значение репутации.',
        'needs_amount': True,
        'input_label': 'Новая репутация',
        'placeholder': 'Например, 15',
    },
    'rep_add': {
        'label': 'Добавить репутацию',
        'summary': 'Повышает репутацию пользователя.',
        'needs_amount': True,
        'input_label': 'Сколько добавить',
        'placeholder': 'Например, 2',
    },
    'profile_reset': {
        'label': 'Сбросить профиль',
        'summary': 'Обнуляет баланс, XP и репутацию.',
        'needs_amount': False,
        'dangerous': True,
    },
    'userinfo': {
        'label': 'Показать userinfo',
        'summary': 'Открывает служебную карточку участника.',
        'needs_amount': False,
    },
}


class AdminBaseView(discord.ui.View):
    def __init__(self, cog: 'AdminCog', opener: discord.Member, *, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.opener = opener

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opener.id:
            await interaction.response.send_message(
                'Эта админ-панель открыта для другого модератора.',
                ephemeral=True,
            )
            return False

        error = self.cog.validate_admin_interaction(interaction, require_panel_channel=True)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return False

        return True


class BackButton(discord.ui.Button):
    def __init__(self, cog: 'AdminCog', opener: discord.Member):
        super().__init__(label='Назад', style=discord.ButtonStyle.secondary, row=3)
        self.cog = cog
        self.opener = opener

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            embed=self.cog.build_home_embed(self.opener),
            view=AdminHomeView(self.cog, self.opener),
        )


class AdminTargetSelect(discord.ui.UserSelect):
    def __init__(self, parent_view: 'AdminActionView'):
        super().__init__(placeholder='Выбери пользователя', min_values=1, max_values=1, row=0)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = self.values[0]
        self.parent_view.selected_target_id = selected.id
        await interaction.response.edit_message(embed=self.parent_view.build_embed(), view=self.parent_view)


class AdminActionSelect(discord.ui.Select):
    def __init__(self, parent_view: 'AdminActionView', definitions: dict[str, dict[str, str | bool]]):
        options = [
            discord.SelectOption(
                label=str(meta['label']),
                value=key,
                description=str(meta['summary'])[:100],
            )
            for key, meta in definitions.items()
        ]
        super().__init__(placeholder='Выбери действие', min_values=1, max_values=1, options=options, row=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        self.parent_view.selected_action_key = self.values[0]
        await interaction.response.edit_message(embed=self.parent_view.build_embed(), view=self.parent_view)


class AdminValueModal(discord.ui.Modal):
    def __init__(self, parent_view: 'AdminActionView', action_key: str, action_meta: dict[str, str | bool], target_id: int):
        super().__init__(title=str(action_meta['label']))
        self.parent_view = parent_view
        self.action_key = action_key
        self.target_id = target_id
        self.value_input = discord.ui.TextInput(
            label=str(action_meta['input_label']),
            placeholder=str(action_meta.get('placeholder', 'Введите число')),
            required=True,
            max_length=12,
        )
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(str(self.value_input.value).strip())
        except ValueError:
            await interaction.response.send_message('Нужно ввести целое число.', ephemeral=True)
            return

        if amount < 0:
            await interaction.response.send_message('Отрицательные значения здесь запрещены.', ephemeral=True)
            return

        action_meta = self.parent_view.definitions[self.action_key]
        if bool(action_meta.get('dangerous')):
            confirm_view = ConfirmActionView(self.parent_view.cog, self.parent_view.opener, self.action_key, self.target_id, amount)
            await interaction.response.send_message(
                embed=self.parent_view.cog.build_confirm_embed(self.action_key, self.target_id, amount),
                view=confirm_view,
                ephemeral=True,
            )
            return

        result = await self.parent_view.cog.execute_member_action(
            interaction=interaction,
            action_key=self.action_key,
            target_id=self.target_id,
            amount=amount,
        )
        await interaction.response.send_message(embed=result, ephemeral=True)


class ExecuteActionButton(discord.ui.Button):
    def __init__(self, parent_view: 'AdminActionView'):
        super().__init__(label='Выполнить', style=discord.ButtonStyle.success, row=2)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.parent_view.selected_target_id is None:
            await interaction.response.send_message('Сначала выбери пользователя.', ephemeral=True)
            return

        if self.parent_view.selected_action_key is None:
            await interaction.response.send_message('Сначала выбери действие.', ephemeral=True)
            return

        action_key = self.parent_view.selected_action_key
        action_meta = self.parent_view.definitions[action_key]
        if bool(action_meta.get('needs_amount')):
            await interaction.response.send_modal(
                AdminValueModal(self.parent_view, action_key, action_meta, self.parent_view.selected_target_id)
            )
            return
        if bool(action_meta.get('dangerous')):
            confirm_view = ConfirmActionView(self.parent_view.cog, self.parent_view.opener, action_key, self.parent_view.selected_target_id, None)
            await interaction.response.send_message(
                embed=self.parent_view.cog.build_confirm_embed(action_key, self.parent_view.selected_target_id, None),
                view=confirm_view,
                ephemeral=True,
            )
            return

        result = await self.parent_view.cog.execute_member_action(
            interaction=interaction,
            action_key=action_key,
            target_id=self.parent_view.selected_target_id,
            amount=None,
        )
        await interaction.response.send_message(embed=result, ephemeral=True)


class ConfirmActionView(AdminBaseView):
    def __init__(self, cog: 'AdminCog', opener: discord.Member, action_key: str, target_id: int, amount: int | None):
        super().__init__(cog, opener, timeout=120)
        self.action_key = action_key
        self.target_id = target_id
        self.amount = amount

    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        result = await self.cog.execute_member_action(
            interaction=interaction,
            action_key=self.action_key,
            target_id=self.target_id,
            amount=self.amount,
        )
        await interaction.response.edit_message(embed=result, view=None)

    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=discord.Embed(title='Действие отменено', color=discord.Color.light_grey()),
            view=None,
        )


class AdminActionView(AdminBaseView):
    def __init__(
        self,
        cog: 'AdminCog',
        opener: discord.Member,
        *,
        section_title: str,
        section_description: str,
        definitions: dict[str, dict[str, str | bool]],
    ):
        super().__init__(cog, opener)
        self.section_title = section_title
        self.section_description = section_description
        self.definitions = definitions
        self.selected_target_id: int | None = None
        self.selected_action_key: str | None = None
        self.add_item(AdminTargetSelect(self))
        self.add_item(AdminActionSelect(self, definitions))
        self.add_item(ExecuteActionButton(self))
        self.add_item(BackButton(cog, opener))

    def build_embed(self) -> discord.Embed:
        lines = [f'`{index}.` **{meta["label"]}** - {meta["summary"]}' for index, meta in enumerate(self.definitions.values(), start=1)]
        target_line = 'не выбран'
        if self.selected_target_id is not None:
            target_line = f'<@{self.selected_target_id}>'

        action_line = 'не выбрано'
        if self.selected_action_key is not None:
            action_line = str(self.definitions[self.selected_action_key]['label'])

        embed = discord.Embed(title=self.section_title, description=self.section_description, color=EMERALD)
        embed.add_field(name='Доступные действия', value='\n'.join(lines), inline=False)
        embed.add_field(name='Выбранный пользователь', value=target_line, inline=True)
        embed.add_field(name='Выбранное действие', value=action_line, inline=True)
        embed.add_field(name='Как использовать', value='1. Выбери пользователя\n2. Выбери действие\n3. Нажми `Выполнить`', inline=False)
        embed.set_footer(text=f'Оператор: {self.opener.display_name}')
        return embed


class SyncPanelsButton(discord.ui.Button):
    def __init__(self, parent_view: 'AdminServiceView'):
        super().__init__(label='Обновить панели', style=discord.ButtonStyle.success, row=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        result = await self.parent_view.cog.sync_panels(interaction)
        await interaction.response.send_message(embed=result, ephemeral=True)


class SyncCommandsButton(discord.ui.Button):
    def __init__(self, parent_view: 'AdminServiceView'):
        super().__init__(label='Синхронизировать команды', style=discord.ButtonStyle.primary, row=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        result = await self.parent_view.cog.sync_commands(interaction)
        await interaction.response.send_message(embed=result, ephemeral=True)


class OpenAuditButton(discord.ui.Button):
    def __init__(self, parent_view: 'AdminServiceView'):
        super().__init__(label='Открыть аудит', style=discord.ButtonStyle.secondary, row=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            embed=self.parent_view.cog.build_audit_embed(),
            view=AdminAuditView(self.parent_view.cog, self.parent_view.opener),
        )

class RefreshAuditButton(discord.ui.Button):
    def __init__(self, parent_view: 'AdminAuditView'):
        super().__init__(label='Обновить аудит', style=discord.ButtonStyle.primary, row=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(embed=self.parent_view.cog.build_audit_embed(), view=self.parent_view)


class AdminServiceView(AdminBaseView):
    def __init__(self, cog: 'AdminCog', opener: discord.Member):
        super().__init__(cog, opener)
        self.add_item(SyncPanelsButton(self))
        self.add_item(SyncCommandsButton(self))
        self.add_item(OpenAuditButton(self))
        self.add_item(BackButton(cog, opener))


class AdminAuditView(AdminBaseView):
    def __init__(self, cog: 'AdminCog', opener: discord.Member):
        super().__init__(cog, opener)
        self.add_item(RefreshAuditButton(self))
        self.add_item(BackButton(cog, opener))


class AdminHomeView(AdminBaseView):
    @discord.ui.button(label='Экономика', style=discord.ButtonStyle.success, row=0)
    async def economy_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        view = AdminActionView(
            self.cog,
            self.opener,
            section_title='Admin Panel • Экономика',
            section_description='Управление валютой и ручными начислениями.',
            definitions=ECONOMY_ACTIONS,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    @discord.ui.button(label='Профили', style=discord.ButtonStyle.primary, row=0)
    async def profile_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        view = AdminActionView(
            self.cog,
            self.opener,
            section_title='Admin Panel • Профили',
            section_description='Тонкая настройка XP, репутации и профиля участника.',
            definitions=PROFILE_ACTIONS,
        )
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    @discord.ui.button(label='Модерация', style=discord.ButtonStyle.secondary, row=0)
    async def moderation_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(embed=self.cog.build_moderation_embed(self.opener), view=AdminHomeView(self.cog, self.opener))

    @discord.ui.button(label='Сервис', style=discord.ButtonStyle.secondary, row=1)
    async def service_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(embed=self.cog.build_service_embed(self.opener), view=AdminServiceView(self.cog, self.opener))

    @discord.ui.button(label='Аудит', style=discord.ButtonStyle.secondary, row=1)
    async def audit_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.edit_message(embed=self.cog.build_audit_embed(), view=AdminAuditView(self.cog, self.opener))


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.profile_service = cast(Any, bot).profile_service
        self.audit_repository = AdminAuditRepository(Config.DATA.ADMIN_AUDIT_PATH)
        self.warning_repository = WarningRepository(Config.DATA.WARNINGS_PATH)

    def validate_admin_interaction(self, interaction: discord.Interaction, *, require_panel_channel: bool = False) -> str | None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return 'Команда доступна только на сервере.'
        if require_panel_channel and interaction.channel_id != Config.CHANNELS.ADMIN_PANEL_CHANNEL_ID:
            return f'Эта панель доступна только в канале <#{Config.CHANNELS.ADMIN_PANEL_CHANNEL_ID}>.'
        if not has_admin_access(interaction.user):
            return 'У тебя нет прав для использования админ-инструментов.'
        return None

    async def record_action(
        self,
        *,
        guild: discord.Guild,
        actor: discord.Member,
        action_key: str,
        action_label: str,
        target: discord.Member | None = None,
        value: int | None = None,
        details: str | None = None,
    ) -> None:
        entry = {
            'timestamp': datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC'),
            'actor_id': actor.id,
            'actor_name': actor.display_name,
            'action_key': action_key,
            'action_label': action_label,
            'target_id': target.id if target else None,
            'target_name': target.display_name if target else None,
            'value': value,
            'details': details,
        }
        self.audit_repository.append(entry)
        await self.send_admin_log(guild, entry, actor, target)

    async def send_admin_log(self, guild: discord.Guild, entry: dict[str, Any], actor: discord.Member, target: discord.Member | None) -> None:
        channel = guild.get_channel(Config.CHANNELS.ADMIN_LOG_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        embed = discord.Embed(title='Admin Action Log', color=EMERALD, timestamp=datetime.now(UTC))
        embed.add_field(name='Действие', value=str(entry['action_label']), inline=True)
        embed.add_field(name='Модератор', value=actor.mention, inline=True)
        embed.add_field(name='Цель', value=target.mention if target else 'Без цели', inline=True)
        if entry.get('value') is not None:
            embed.add_field(name='Значение', value=f'`{entry["value"]}`', inline=True)
        if entry.get('details'):
            embed.add_field(name='Детали', value=str(entry['details'])[:1024], inline=False)
        embed.set_footer(text=f'Action key: {entry["action_key"]}')
        try:
            await channel.send(embed=embed)
        except Exception:
            pass

    def build_home_embed(self, operator: discord.Member) -> discord.Embed:
        embed = discord.Embed(title='Admin Panel • Diplom', description='Единая админ-панель для экономики, профилей, модерации и служебных действий.', color=EMERALD)
        embed.add_field(name='Экономика', value='`balance set`\n`balance add`\n`balance remove`', inline=True)
        embed.add_field(name='Профили', value='`xp set`\n`xp add`\n`rep set`\n`rep add`\n`profile reset`\n`userinfo`', inline=True)
        embed.add_field(name='Модерация', value='`/warn`\n`/unwarn`\n`/warnings`\n`/dailyreset`\n`/announce`\n`/rolegrant`\n`/roleremove`', inline=True)
        embed.add_field(name='Канал панели', value=f'<#{Config.CHANNELS.ADMIN_PANEL_CHANNEL_ID}>', inline=True)
        embed.add_field(name='Лог канал', value=f'<#{Config.CHANNELS.ADMIN_LOG_CHANNEL_ID}>', inline=True)
        embed.add_field(name='Сервис', value='`panel sync`\n`slash sync`\n`audit`', inline=True)
        embed.set_footer(text=f'Оператор: {operator.display_name}')
        return embed

    def build_moderation_embed(self, operator: discord.Member) -> discord.Embed:
        embed = discord.Embed(title='Admin Panel • Модерация', description='Отдельные slash-команды для предупреждений, ролей, объявлений и сброса daily.', color=EMERALD)
        embed.add_field(name='/warn', value='Выдать предупреждение пользователю с причиной.', inline=False)
        embed.add_field(name='/unwarn', value='Снять предупреждение по ID.', inline=False)
        embed.add_field(name='/warnings', value='Показать активные предупреждения пользователя.', inline=False)
        embed.add_field(name='/dailyreset', value='Сбросить кулдаун ежедневной награды.', inline=False)
        embed.add_field(name='/announce', value='Отправить embed-объявление в канал.', inline=False)
        embed.add_field(name='/rolegrant и /roleremove', value='Выдать или снять роль у участника.', inline=False)
        embed.set_footer(text=f'Оператор: {operator.display_name}')
        return embed

    def build_service_embed(self, operator: discord.Member) -> discord.Embed:
        embed = discord.Embed(title='Admin Panel • Сервис', description='Служебные операции для панелей и slash-команд.', color=EMERALD)
        embed.add_field(name='Обновить панели', value='Пересобирает welcome, rules и report panel.', inline=False)
        embed.add_field(name='Синхронизировать команды', value='Повторно синхронизирует guild slash-команды.', inline=False)
        embed.add_field(name='Аудит', value='Показывает последние действия админов.', inline=False)
        embed.set_footer(text=f'Оператор: {operator.display_name}')
        return embed

    def build_result_embed(self, *, title: str, description: str, color: int = EMERALD) -> discord.Embed:
        return discord.Embed(title=title, description=description, color=color)

    def build_confirm_embed(self, action_key: str, target_id: int, amount: int | None) -> discord.Embed:
        title_map = {'balance_remove': 'Подтверждение списания баланса', 'profile_reset': 'Подтверждение сброса профиля'}
        description = f'Цель: <@{target_id}>'
        if amount is not None:
            description += f'\nЗначение: **{amount}**'
        description += '\n\nПодтверди действие кнопкой ниже.'
        return discord.Embed(title=title_map.get(action_key, 'Подтверждение действия'), description=description, color=DANGER)

    def build_userinfo_embed(self, member: discord.Member) -> discord.Embed:
        profile = self.profile_service.get_profile(member.id)
        warnings = self.warning_repository.get_warnings(member.id)
        roles = [role.mention for role in member.roles if role != member.guild.default_role]
        roles_value = ', '.join(roles[:8]) if roles else 'Нет ролей'
        if len(roles) > 8:
            roles_value += f' и ещё {len(roles) - 8}'
        embed = discord.Embed(title='Admin • Userinfo', color=EMERALD)
        embed.add_field(name='Пользователь', value=f'{member.mention}\n`{member.id}`', inline=True)
        embed.add_field(name='Баланс', value=f'**{profile.balance}** монет', inline=True)
        embed.add_field(name='XP', value=f'**{profile.xp}**', inline=True)
        embed.add_field(name='Репутация', value=f'**{profile.rep}**', inline=True)
        embed.add_field(name='Предупреждения', value=f'**{len(warnings)}**', inline=True)
        embed.add_field(name='Зашёл на сервер', value=discord.utils.format_dt(member.joined_at, style='F') if member.joined_at else 'Неизвестно', inline=False)
        embed.add_field(name='Роли', value=roles_value, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        return embed

    def build_warnings_embed(self, member: discord.Member) -> discord.Embed:
        warnings = self.warning_repository.get_warnings(member.id)
        embed = discord.Embed(title='Warnings', description=f'Предупреждения пользователя {member.mention}', color=EMERALD)
        if not warnings:
            embed.add_field(name='Пусто', value='У пользователя нет активных предупреждений.', inline=False)
            return embed
        lines = []
        for item in warnings[:10]:
            lines.append(f'`#{item["id"]}` • {item.get("timestamp", "--")} • {item.get("reason", "Без причины")}')
        embed.add_field(name='Активные предупреждения', value='\n'.join(lines), inline=False)
        return embed

    def build_audit_embed(self) -> discord.Embed:
        entries = self.audit_repository.get_recent(limit=8)
        embed = discord.Embed(title='Admin Panel • Аудит', description='Последние действия админов по панели.', color=EMERALD)
        if not entries:
            embed.add_field(name='Журнал пуст', value='Пока нет ни одного записанного действия.', inline=False)
            return embed
        lines = []
        for entry in entries:
            actor = entry.get('actor_name', 'Неизвестно')
            action = entry.get('action_label', entry.get('action_key', 'action'))
            target = entry.get('target_name') or 'без цели'
            value = entry.get('value')
            suffix = '' if value is None else f' • значение: `{value}`'
            lines.append(f'`{entry.get("timestamp", "--")}` • **{actor}** • {action} • {target}{suffix}')
        embed.add_field(name='Последние записи', value='\n'.join(lines), inline=False)
        return embed

    async def resolve_member(self, guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(user_id)
        if member is not None:
            return member
        try:
            return await guild.fetch_member(user_id)
        except Exception:
            return None

    async def execute_member_action(self, *, interaction: discord.Interaction, action_key: str, target_id: int, amount: int | None) -> discord.Embed:
        guild = interaction.guild
        operator = interaction.user
        if guild is None or not isinstance(operator, discord.Member):
            return self.build_result_embed(title='Ошибка', description='Команда доступна только на сервере.', color=discord.Color.red())
        member = await self.resolve_member(guild, target_id)
        if member is None:
            return self.build_result_embed(title='Ошибка', description='Не удалось найти участника.', color=discord.Color.red())
        if action_key == 'balance_set' and amount is not None:
            new_balance = self.profile_service.set_balance(member.id, amount)
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Установить баланс', target=member, value=amount)
            return self.build_result_embed(title='Баланс обновлён', description=f'{member.mention} теперь имеет **{new_balance}** монет.')
        if action_key == 'balance_add' and amount is not None:
            new_balance = self.profile_service.add_balance(member.id, amount)
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Добавить баланс', target=member, value=amount)
            return self.build_result_embed(title='Баланс пополнен', description=f'{member.mention} получил **{amount}** монет. Новый баланс: **{new_balance}** монет.')
        if action_key == 'balance_remove' and amount is not None:
            new_balance = self.profile_service.add_balance(member.id, -amount)
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Снять баланс', target=member, value=amount)
            return self.build_result_embed(title='Баланс уменьшен', description=f'У {member.mention} списано **{amount}** монет. Остаток: **{new_balance}** монет.')
        if action_key == 'xp_set' and amount is not None:
            self.profile_service.set_xp(member.id, amount)
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Установить XP', target=member, value=amount)
            return self.build_result_embed(title='XP обновлено', description=f'{member.mention} теперь имеет **{amount}** XP.')
        if action_key == 'xp_add' and amount is not None:
            self.profile_service.add_xp(member.id, amount)
            updated = self.profile_service.get_profile(member.id)
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Добавить XP', target=member, value=amount)
            return self.build_result_embed(title='XP начислено', description=f'{member.mention} получил **{amount}** XP. Теперь у него **{updated.xp}** XP.')
        if action_key == 'rep_set' and amount is not None:
            self.profile_service.set_rep(member.id, amount)
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Установить репутацию', target=member, value=amount)
            return self.build_result_embed(title='Репутация обновлена', description=f'{member.mention} теперь имеет **{amount}** репутации.')
        if action_key == 'rep_add' and amount is not None:
            self.profile_service.add_rep(member.id, amount)
            updated = self.profile_service.get_profile(member.id)
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Добавить репутацию', target=member, value=amount)
            return self.build_result_embed(title='Репутация повышена', description=f'{member.mention} получил **{amount}** репутации. Теперь у него **{updated.rep}**.')
        if action_key == 'profile_reset':
            self.profile_service.set_balance(member.id, 0)
            self.profile_service.set_xp(member.id, 0)
            self.profile_service.set_rep(member.id, 0)
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Сбросить профиль', target=member)
            return self.build_result_embed(title='Профиль сброшен', description=f'Профиль {member.mention} обнулён: баланс, XP и репутация сброшены.')
        if action_key == 'userinfo':
            await self.record_action(guild=guild, actor=operator, action_key=action_key, action_label='Открыть userinfo', target=member)
            return self.build_userinfo_embed(member)
        return self.build_result_embed(title='Ошибка', description='Неизвестное действие.', color=discord.Color.red())

    async def sync_panels(self, interaction: discord.Interaction) -> discord.Embed:
        guild = interaction.guild
        actor = interaction.user
        tasks_done: list[str] = []
        welcome_cog = self.bot.get_cog('WelcomeCog')
        if welcome_cog is not None and hasattr(welcome_cog, 'ensure_panel'):
            await welcome_cog.ensure_panel()
            tasks_done.append('welcome panel')
        rules_cog = self.bot.get_cog('RulesCog')
        if rules_cog is not None and hasattr(rules_cog, 'ensure_rules_message'):
            await rules_cog.ensure_rules_message()
            tasks_done.append('rules panel')
        report_cog = self.bot.get_cog('ReportPanelCog')
        if report_cog is not None and hasattr(report_cog, 'ensure_panel_message'):
            await report_cog.ensure_panel_message()
            tasks_done.append('report panel')
        if guild is not None and isinstance(actor, discord.Member):
            await self.record_action(guild=guild, actor=actor, action_key='panel_sync', action_label='Обновить панели', details=', '.join(tasks_done))
        if not tasks_done:
            return self.build_result_embed(title='Panel Sync', description='Не найдено ни одной панели для обновления.', color=discord.Color.orange())
        return self.build_result_embed(title='Panel Sync', description='Обновлены панели: ' + ', '.join(f'**{item}**' for item in tasks_done))

    async def sync_commands(self, interaction: discord.Interaction) -> discord.Embed:
        guild = interaction.guild
        actor = interaction.user
        bot_any = cast(Any, self.bot)
        await bot_any.sync_guild_commands()
        if guild is not None and isinstance(actor, discord.Member):
            await self.record_action(guild=guild, actor=actor, action_key='slash_sync', action_label='Синхронизировать команды')
        return self.build_result_embed(title='Slash Sync', description='Guild slash-команды успешно пересинхронизированы.')

    @app_commands.command(name='admin', description='Открыть админ-панель сервера')
    async def admin(self, interaction: discord.Interaction) -> None:
        error = self.validate_admin_interaction(interaction, require_panel_channel=True)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return
        operator = cast(discord.Member, interaction.user)
        await interaction.response.send_message(embed=self.build_home_embed(operator), view=AdminHomeView(self, operator), ephemeral=True)

    @app_commands.command(name='warn', description='Выдать предупреждение пользователю')
    @app_commands.describe(member='Пользователь', reason='Причина предупреждения')
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        error = self.validate_admin_interaction(interaction)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message('Ботам нельзя выдавать предупреждения.', ephemeral=True)
            return
        guild = cast(discord.Guild, interaction.guild)
        actor = cast(discord.Member, interaction.user)
        warning = self.warning_repository.add_warning(member.id, actor.id, reason, datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC'))
        await self.record_action(guild=guild, actor=actor, action_key='warn', action_label='Выдать предупреждение', target=member, value=int(warning['id']), details=reason)
        await interaction.response.send_message(embed=self.build_result_embed(title='Предупреждение выдано', description=f'{member.mention} получил предупреждение `#{warning["id"]}`.\nПричина: {reason}'), ephemeral=True)

    @app_commands.command(name='unwarn', description='Снять предупреждение у пользователя')
    @app_commands.describe(member='Пользователь', warning_id='ID предупреждения')
    async def unwarn(self, interaction: discord.Interaction, member: discord.Member, warning_id: int) -> None:
        error = self.validate_admin_interaction(interaction)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return
        removed = self.warning_repository.remove_warning(member.id, warning_id)
        if removed is None:
            await interaction.response.send_message('Предупреждение с таким ID не найдено.', ephemeral=True)
            return
        guild = cast(discord.Guild, interaction.guild)
        actor = cast(discord.Member, interaction.user)
        await self.record_action(guild=guild, actor=actor, action_key='unwarn', action_label='Снять предупреждение', target=member, value=warning_id, details=str(removed.get('reason', 'Без причины')))
        await interaction.response.send_message(embed=self.build_result_embed(title='Предупреждение снято', description=f'У {member.mention} снято предупреждение `#{warning_id}`.'), ephemeral=True)

    @app_commands.command(name='warnings', description='Показать предупреждения пользователя')
    @app_commands.describe(member='Пользователь')
    async def warnings(self, interaction: discord.Interaction, member: discord.Member) -> None:
        error = self.validate_admin_interaction(interaction)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return
        guild = cast(discord.Guild, interaction.guild)
        actor = cast(discord.Member, interaction.user)
        await self.record_action(guild=guild, actor=actor, action_key='warnings', action_label='Открыть список предупреждений', target=member)
        await interaction.response.send_message(embed=self.build_warnings_embed(member), ephemeral=True)

    @app_commands.command(name='dailyreset', description='Сбросить daily кулдаун пользователю')
    @app_commands.describe(member='Пользователь')
    async def dailyreset(self, interaction: discord.Interaction, member: discord.Member) -> None:
        error = self.validate_admin_interaction(interaction)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return
        self.profile_service.repository.set_daily_ts(member.id, 0)
        guild = cast(discord.Guild, interaction.guild)
        actor = cast(discord.Member, interaction.user)
        await self.record_action(guild=guild, actor=actor, action_key='daily_reset', action_label='Сбросить daily', target=member)
        await interaction.response.send_message(embed=self.build_result_embed(title='Daily reset', description=f'Кулдаун `/daily` для {member.mention} сброшен.'), ephemeral=True)

    @app_commands.command(name='announce', description='Отправить embed-объявление в канал')
    @app_commands.describe(channel='Канал', title='Заголовок', message='Текст объявления')
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str) -> None:
        error = self.validate_admin_interaction(interaction)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return
        embed = discord.Embed(title=title, description=message, color=EMERALD)
        embed.set_footer(text=f'Отправил: {interaction.user.display_name}')
        await channel.send(embed=embed)
        guild = cast(discord.Guild, interaction.guild)
        actor = cast(discord.Member, interaction.user)
        await self.record_action(guild=guild, actor=actor, action_key='announce', action_label='Отправить объявление', value=channel.id, details=f'{title} -> #{channel.name}')
        await interaction.response.send_message(embed=self.build_result_embed(title='Объявление отправлено', description=f'Объявление опубликовано в {channel.mention}.'), ephemeral=True)

    @app_commands.command(name='rolegrant', description='Выдать роль пользователю')
    @app_commands.describe(member='Пользователь', role='Роль')
    async def rolegrant(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role) -> None:
        error = self.validate_admin_interaction(interaction)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return
        await member.add_roles(role, reason=f'Admin grant by {interaction.user}')
        guild = cast(discord.Guild, interaction.guild)
        actor = cast(discord.Member, interaction.user)
        await self.record_action(guild=guild, actor=actor, action_key='role_grant', action_label='Выдать роль', target=member, value=role.id, details=role.name)
        await interaction.response.send_message(embed=self.build_result_embed(title='Роль выдана', description=f'{member.mention} получил роль {role.mention}.'), ephemeral=True)

    @app_commands.command(name='roleremove', description='Снять роль у пользователя')
    @app_commands.describe(member='Пользователь', role='Роль')
    async def roleremove(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role) -> None:
        error = self.validate_admin_interaction(interaction)
        if error is not None:
            await interaction.response.send_message(error, ephemeral=True)
            return
        await member.remove_roles(role, reason=f'Admin remove by {interaction.user}')
        guild = cast(discord.Guild, interaction.guild)
        actor = cast(discord.Member, interaction.user)
        await self.record_action(guild=guild, actor=actor, action_key='role_remove', action_label='Снять роль', target=member, value=role.id, details=role.name)
        await interaction.response.send_message(embed=self.build_result_embed(title='Роль снята', description=f'У {member.mention} снята роль {role.mention}.'), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot), guild=Config.SERVER_OBJ)


