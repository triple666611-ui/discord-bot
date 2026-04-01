from __future__ import annotations

import datetime as dt
from typing import Any, cast

import discord

from services.shop_service import ShopItem


CATEGORY_STYLES = {
    'Косметика': ('🎨', discord.Color.blurple()),
    'Бонусы': ('⚡', discord.Color.gold()),
    'Кейсы': ('🎁', discord.Color.orange()),
    'Роли': ('👑', discord.Color.fuchsia()),
    'Подписка': ('💠', discord.Color.teal()),
    'Прочее': ('🧩', discord.Color.light_grey()),
    'Чёрный рынок': ('🕶️', discord.Color.dark_purple()),
}

EFFECT_LABELS = {
    'profile_theme': 'Тема профиля',
    'profile_frame': 'Рамка профиля',
    'double_win_armed': 'Бустер x2',
    'vip_slot_armed': 'VIP слот',
    'vip_subscription': 'VIP подписка',
}

EFFECT_VALUES = {
    'color': 'Цветной профиль',
    'custom_bg': 'Кастомный фон',
    'vip': 'VIP рамка',
    'shadow': 'Теневая рамка',
    'active': 'Активно',
}


class ShopItemSelect(discord.ui.Select['ShopView']):
    def __init__(self, shop_view: 'ShopView') -> None:
        self.shop_view = shop_view
        options = self._build_options()
        placeholder = 'Выберите предмет'

        if not options:
            options = [
                discord.SelectOption(
                    label='Пусто',
                    value='__empty__',
                    description='Сейчас здесь нет доступных предметов',
                )
            ]
            placeholder = 'Сейчас выбирать нечего'

        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options[:25],
            row=1,
            disabled=options[0].value == '__empty__',
        )

    def _build_options(self) -> list[discord.SelectOption]:
        options: list[discord.SelectOption] = []
        selected_key = self.shop_view.selected_item_key

        if self.shop_view.mode in {'catalog', 'blackmarket'}:
            for item in self.shop_view.get_catalog_items_for_mode():
                emoji = self.shop_view.get_category_emoji(item.category)
                options.append(
                    discord.SelectOption(
                        label=item.name[:100],
                        value=item.key,
                        description=f'{emoji} {item.price} монет',
                        default=item.key == selected_key,
                    )
                )
        elif self.shop_view.mode == 'inventory':
            inventory = self.shop_view.shop_service.get_inventory(self.shop_view.user_id)
            for item_key, qty in inventory.items():
                item = self.shop_view.shop_service.get_item(item_key)
                item_name = item.name if item is not None else item_key
                description = f'Количество: {qty}'
                if item is not None:
                    description = f'{self.shop_view.get_category_emoji(item.category)} {description}'
                options.append(
                    discord.SelectOption(
                        label=item_name[:100],
                        value=item_key,
                        description=description[:100],
                        default=item_key == selected_key,
                    )
                )
        return options

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.shop_view.ensure_owner(interaction):
            return
        value = self.values[0]
        if value == '__empty__':
            await interaction.response.defer()
            return

        self.shop_view.selected_item_key = value
        self.shop_view.refresh_components()
        await interaction.response.edit_message(
            embed=self.shop_view.build_current_embed(),
            view=self.shop_view,
        )


class ShopView(discord.ui.View):
    def __init__(self, cog: Any, user_id: int) -> None:
        super().__init__(timeout=600)
        self.cog = cog
        self.user_id = user_id
        self.profile_service = cast(Any, cog).profile_service
        self.shop_service = cast(Any, cog).shop_service
        self.mode = 'main'
        self.selected_item_key: str | None = None
        self.notice: tuple[str, str, bool] | None = None
        self.refresh_components()

    async def ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title='Ошибка',
                    description='Эта панель магазина открыта для другого пользователя.',
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return False
        return True

    def format_ts(self, ts: int | None) -> str:
        if ts is None:
            return 'бессрочно'
        return dt.datetime.fromtimestamp(ts).strftime('%d.%m.%Y %H:%M')

    def get_selected_item(self) -> ShopItem | None:
        if self.selected_item_key is None:
            return None
        return self.shop_service.get_item(self.selected_item_key)

    def get_catalog_items_for_mode(self) -> list[ShopItem]:
        if self.mode == 'blackmarket':
            return [self.shop_service.get_black_market_offer()]

        items: list[ShopItem] = []
        for group in self.shop_service.get_catalog().values():
            items.extend(group)
        return items

    def get_category_emoji(self, category: str) -> str:
        return CATEGORY_STYLES.get(category, ('🛍️', discord.Color.blurple()))[0]

    def format_item_line(self, item: ShopItem) -> str:
        return f"{self.get_category_emoji(item.category)} **{item.name}** • {item.price} монет\n{item.description}"

    def format_effect(self, effect_key: str, effect_data: dict[str, Any]) -> str:
        label = EFFECT_LABELS.get(effect_key, effect_key.replace('_', ' ').title())
        raw_value = effect_data.get('value')
        value = EFFECT_VALUES.get(str(raw_value), str(raw_value))
        expires_text = self.format_ts(effect_data.get('expires_ts'))
        return f'• **{label}**: {value} • до {expires_text}'

    def apply_embed_style(self, embed: discord.Embed, color: discord.Color) -> discord.Embed:
        embed.color = color
        embed.set_footer(text='Магазин сервера • выбор и действия доступны через кнопки ниже')
        if self.notice is not None:
            title, message, success = self.notice
            icon = '✅' if success else '❌'
            embed.add_field(name=f'{icon} {title}', value=message, inline=False)
        return embed

    def set_notice(self, title: str, message: str, success: bool) -> None:
        self.notice = (title, message, success)

    def clear_notice(self) -> None:
        self.notice = None

    def sync_selected_item(self) -> None:
        if self.selected_item_key is None:
            return

        if self.mode in {'catalog', 'blackmarket'}:
            available = {item.key for item in self.get_catalog_items_for_mode()}
        elif self.mode == 'inventory':
            available = set(self.shop_service.get_inventory(self.user_id).keys())
        else:
            available = set()

        if self.selected_item_key not in available:
            self.selected_item_key = None

    def refresh_components(self) -> None:
        self.sync_selected_item()
        self.clear_items()
        self.add_item(self.catalog_button)
        self.add_item(self.inventory_button)
        self.add_item(self.black_market_button)
        self.add_item(self.back_button)

        if self.mode in {'catalog', 'inventory', 'blackmarket'}:
            self.add_item(ShopItemSelect(self))

        if self.mode in {'catalog', 'blackmarket'}:
            self.add_item(self.buy_button)
        if self.mode == 'inventory':
            self.add_item(self.use_button)
            self.add_item(self.deactivate_button)

        selected = self.get_selected_item()
        self.buy_button.disabled = self.mode not in {'catalog', 'blackmarket'} or selected is None
        self.use_button.disabled = self.mode != 'inventory' or selected is None
        self.deactivate_button.disabled = self.mode != 'inventory' or selected is None
        self.back_button.disabled = self.mode == 'main'

    def build_main_embed(self) -> discord.Embed:
        profile = self.profile_service.get_profile(self.user_id)
        embed = discord.Embed(
            title='🛍️ Магазин сервера',
            description=(
                'Добро пожаловать в магазин. Здесь можно купить косметику, бонусы, роли и особые редкие товары.\n\n'
                f'**Текущий баланс:** {profile.balance} монет'
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name='✨ Что доступно',
            value=(
                '🎨 Каталог — все обычные товары магазина\n'
                '🎒 Инвентарь — использование купленных предметов\n'
                '🕶️ Чёрный рынок — редкое предложение дня'
            ),
            inline=False,
        )
        embed.add_field(
            name='💡 Подсказка',
            value='Сначала открой раздел, затем выбери предмет из списка и используй кнопку действия.',
            inline=False,
        )
        return self.apply_embed_style(embed, discord.Color.blurple())

    def build_catalog_embed(self) -> discord.Embed:
        profile = self.profile_service.get_profile(self.user_id)
        embed = discord.Embed(
            title='🎨 Каталог магазина',
            description=(
                'Выберите предмет в меню ниже. В каталоге показаны только названия, цена и описание без технических кодов.\n\n'
                f'**Баланс:** {profile.balance} монет'
            ),
            color=discord.Color.blurple(),
        )
        for category, items in self.shop_service.get_catalog().items():
            emoji = self.get_category_emoji(category)
            lines = [f'{emoji} **{item.name}** • {item.price} монет' for item in items]
            embed.add_field(name=f'{emoji} {category}', value='\n'.join(lines), inline=False)

        selected = self.get_selected_item()
        if selected is not None:
            embed.add_field(
                name='🧾 Выбранный предмет',
                value=self.format_item_line(selected),
                inline=False,
            )
        return self.apply_embed_style(embed, discord.Color.blurple())

    def build_inventory_embed(self) -> discord.Embed:
        inventory = self.shop_service.get_inventory(self.user_id)
        effects = self.shop_service.list_effects(self.user_id)
        profile = self.profile_service.get_profile(self.user_id)
        active_cosmetics = self.shop_service.get_active_cosmetics(self.user_id)

        embed = discord.Embed(
            title='🎒 Твой инвентарь',
            description=f'Здесь лежат купленные предметы и активные эффекты.\n\n**Баланс:** {profile.balance} монет',
            color=discord.Color.green(),
        )

        if inventory:
            lines: list[str] = []
            for item_key, qty in inventory.items():
                item = self.shop_service.get_item(item_key)
                item_name = item.name if item is not None else 'Неизвестный предмет'
                emoji = self.get_category_emoji(item.category) if item is not None else '📦'
                markers: list[str] = []
                if item_key == active_cosmetics.get('theme'):
                    markers.append('активный фон')
                if item_key == active_cosmetics.get('frame'):
                    markers.append('активная рамка')
                suffix = f" • {' / '.join(markers)}" if markers else ''
                lines.append(f'{emoji} **{item_name}** x{qty}{suffix}')
            embed.add_field(name='📦 Предметы', value='\n'.join(lines), inline=False)
        else:
            embed.add_field(name='📦 Предметы', value='Инвентарь пока пуст.', inline=False)

        if effects:
            effect_lines = [self.format_effect(effect_key, effect_data) for effect_key, effect_data in effects.items()]
            embed.add_field(name='✨ Активные эффекты', value='\n'.join(effect_lines), inline=False)

        selected = self.get_selected_item()
        if selected is not None:
            embed.add_field(
                name='🧾 Выбранный предмет',
                value=self.format_item_line(selected),
                inline=False,
            )
        return self.apply_embed_style(embed, discord.Color.green())

    def build_black_market_embed(self) -> discord.Embed:
        profile = self.profile_service.get_profile(self.user_id)
        item = self.shop_service.get_black_market_offer()
        embed = discord.Embed(
            title='🕶️ Чёрный рынок',
            description=(
                'Редкий товар дня. Предложение обновляется раз в 24 часа и может исчезнуть до следующего цикла.\n\n'
                f'**Баланс:** {profile.balance} монет'
            ),
            color=discord.Color.dark_purple(),
        )
        embed.add_field(name='🔥 Сегодняшнее предложение', value=self.format_item_line(item), inline=False)

        selected = self.get_selected_item()
        if selected is not None:
            embed.add_field(
                name='🧾 Выбранный предмет',
                value=f'Готово к покупке: **{selected.name}** за **{selected.price}** монет',
                inline=False,
            )
        return self.apply_embed_style(embed, discord.Color.dark_purple())

    def build_current_embed(self) -> discord.Embed:
        if self.mode == 'catalog':
            return self.build_catalog_embed()
        if self.mode == 'inventory':
            return self.build_inventory_embed()
        if self.mode == 'blackmarket':
            return self.build_black_market_embed()
        return self.build_main_embed()

    async def handle_buy(self, interaction: discord.Interaction) -> None:
        item = self.get_selected_item()
        if item is None:
            await interaction.response.send_message(
                embed=discord.Embed(title='Покупка', description='Сначала выбери предмет.', color=discord.Color.red()),
                ephemeral=True,
            )
            return

        success, message, details = self.shop_service.buy_item(self.user_id, item.key)
        self.set_notice('Покупка', message, success)

        if success:
            if self.mode == 'catalog' and item.kind == 'cosmetic':
                self.mode = 'inventory'
                self.selected_item_key = item.key
            elif self.mode == 'blackmarket':
                reward_item = details.get('item')
                self.mode = 'inventory'
                self.selected_item_key = reward_item.key if reward_item is not None else item.key

            role_id = details.get('role_id')
            if role_id and interaction.guild is not None:
                role = interaction.guild.get_role(int(role_id))
                member = interaction.guild.get_member(self.user_id)
                if role is not None and member is not None:
                    try:
                        await member.add_roles(role, reason='Покупка роли в /shop')
                        self.set_notice('Покупка', f'{message}\n\nВыдана роль {role.mention}', True)
                    except discord.Forbidden:
                        self.set_notice('Покупка', f'{message}\n\nУ бота нет прав на выдачу роли.', False)
                    except discord.HTTPException:
                        self.set_notice('Покупка', f'{message}\n\nDiscord API не дал выдать роль.', False)

        self.refresh_components()
        await interaction.response.edit_message(
            embed=self.build_current_embed(),
            view=self,
        )

    async def handle_use(self, interaction: discord.Interaction) -> None:
        item = self.get_selected_item()
        if item is None:
            await interaction.response.send_message(
                embed=discord.Embed(title='Использование', description='Сначала выбери предмет.', color=discord.Color.red()),
                ephemeral=True,
            )
            return

        success, message = self.shop_service.use_item(self.user_id, item.key)
        self.set_notice('Использование', message, success)
        self.refresh_components()
        await interaction.response.edit_message(
            embed=self.build_current_embed(),
            view=self,
        )

    async def handle_deactivate(self, interaction: discord.Interaction) -> None:
        item = self.get_selected_item()
        if item is None:
            await interaction.response.send_message(
                embed=discord.Embed(title='Отключение', description='Сначала выбери предмет.', color=discord.Color.red()),
                ephemeral=True,
            )
            return

        success, message = self.shop_service.deactivate_item(self.user_id, item.key)
        self.set_notice('Отключение', message, success)
        self.refresh_components()
        await interaction.response.edit_message(
            embed=self.build_current_embed(),
            view=self,
        )

    @discord.ui.button(label='Каталог', style=discord.ButtonStyle.primary, row=0)
    async def catalog_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        self.mode = 'catalog'
        self.selected_item_key = None
        self.clear_notice()
        self.refresh_components()
        await interaction.response.edit_message(embed=self.build_current_embed(), view=self)

    @discord.ui.button(label='Инвентарь', style=discord.ButtonStyle.success, row=0)
    async def inventory_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        self.mode = 'inventory'
        self.selected_item_key = None
        self.clear_notice()
        self.refresh_components()
        await interaction.response.edit_message(embed=self.build_current_embed(), view=self)

    @discord.ui.button(label='Чёрный рынок', style=discord.ButtonStyle.danger, row=0)
    async def black_market_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        self.mode = 'blackmarket'
        self.selected_item_key = self.shop_service.get_black_market_offer().key
        self.clear_notice()
        self.refresh_components()
        await interaction.response.edit_message(embed=self.build_current_embed(), view=self)

    @discord.ui.button(label='Назад', style=discord.ButtonStyle.secondary, row=0)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        self.mode = 'main'
        self.selected_item_key = None
        self.clear_notice()
        self.refresh_components()
        await interaction.response.edit_message(embed=self.build_current_embed(), view=self)

    @discord.ui.button(label='Купить', style=discord.ButtonStyle.primary, row=2)
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        await self.handle_buy(interaction)

    @discord.ui.button(label='Использовать', style=discord.ButtonStyle.success, row=2)
    async def use_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        await self.handle_use(interaction)

    @discord.ui.button(label='Отключить', style=discord.ButtonStyle.secondary, row=2)
    async def deactivate_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.ensure_owner(interaction):
            return
        await self.handle_deactivate(interaction)