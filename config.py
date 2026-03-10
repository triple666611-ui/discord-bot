import os
from pathlib import Path

import discord
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)


class BotConfig:
    TOKEN: str = os.getenv('DISCORD_TOKEN') or ""
    PREFIX = '!'
    SERVER_ID = 1478992186078138441
    SERVER_OBJECT = discord.Object(id=SERVER_ID)


class ChannelConfig:
    ROLE_PANEL_CHANNEL_ID = 1479028120584716288
    RULES_CHANNEL_ID = 1479065658485506180
    REPORT_CHANNEL_ID = 1478998579833077811
    REPORT_PANEL_CHANNEL_ID = 1479015652382474284
    COIN_CHANNEL_ID = 1480309524538720318
    DICE_CHANNEL_ID = 1480309607137022244
    SLOTS_CHANNEL_ID = 1480309625269256284
    BALANCE_LOG_CHANNEL_ID = 1480300433590194207


class RoleConfig:
    RULES_ACCEPT_ROLE_ID = 1479066080474431619
    MOD_ROLE_ID = 1479014566678499483
    SELF_ROLES = {
        '🎮 1': 1479027693038211092,
        '💻 2': 1479027706145280105,
        '🎨 3': 1479027718652821514,
    }


class TicketConfig:
    TICKETS_CATEGORY_ID = 1479037309293953135
    TICKET_DELETE_DELAY_SECONDS = 3600


class WelcomeConfig:
    GIF_URL = 'https://i.gifer.com/5RTG.gif'
    PANEL_BG_URL = ''
    DESCRIPTION = (
        "Добро пожаловать на сервер!\n\n"
        "🎭 **Выберите роли ниже**\n"
        "📜 **Обязательно ознакомьтесь с правилами**\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📌 **Полезные команды**\n\n"
        "👤 `/profile` — посмотреть профиль\n"
        "⭐ `/rep @user` — изменить репутацию\n"
        "🎮 `/games` — правила всех игр\n"
        "🏆 `/topbalance` — топ игроков по балансу\n"
        "🎁 `/daily` — ежедневная награда\n"
        "🛒 `/shop` — магазин предметов\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    FOOTER = 'Выбор ролей можно изменить в любой момент'


class ShopConfig:
    VIP_ROLE_ID = 1480822286415298661
    ELITE_ROLE_ID = 1480824707316977776
    LEGEND_ROLE_ID = 1480824802787856425


class EconomyConfig:
    DAILY_REWARD = 100
    DAILY_COOLDOWN_SEC = 86400
    HIGH_STAKE_THRESHOLD = 10000
    MSG_XP_MIN = 15
    MSG_XP_MAX = 25
    MSG_XP_COOLDOWN_SEC = 60
    VOICE_XP_PER_MIN = 10
    REP_COOLDOWN_SEC = 12 * 60 * 60


class DataConfig:
    PROFILES_DB_PATH = DATA_DIR / 'profiles.db'
    PANEL_STATE_PATH = DATA_DIR / 'panel_messages.json'
    REACTION_ROLES_PATH = DATA_DIR / 'reaction_roles.json'


class Config:
    BOT = BotConfig
    CHANNELS = ChannelConfig
    ROLES = RoleConfig
    TICKETS = TicketConfig
    WELCOME = WelcomeConfig
    ECONOMY = EconomyConfig
    DATA = DataConfig
    SHOP = ShopConfig

    TOKEN = BOT.TOKEN
    PREFIX = BOT.PREFIX
    SERVER_ID = BOT.SERVER_ID
    SERVER_OBJ = BOT.SERVER_OBJECT
    ROLE_PANEL_CHANNEL_ID = CHANNELS.ROLE_PANEL_CHANNEL_ID
    RULES_CHANNEL_ID = CHANNELS.RULES_CHANNEL_ID
    REPORT_CHANNEL_ID = CHANNELS.REPORT_CHANNEL_ID
    REPORT_PANEL_CHANNEL_ID = CHANNELS.REPORT_PANEL_CHANNEL_ID
    COIN_CHANNEL_ID = CHANNELS.COIN_CHANNEL_ID
    DICE_CHANNEL_ID = CHANNELS.DICE_CHANNEL_ID
    SLOTS_CHANNEL_ID = CHANNELS.SLOTS_CHANNEL_ID
    BALANCE_LOG_CHANNEL_ID = CHANNELS.BALANCE_LOG_CHANNEL_ID
    RULES_ACCEPT_ROLE_ID = ROLES.RULES_ACCEPT_ROLE_ID
    MOD_ROLE_ID = ROLES.MOD_ROLE_ID
    SELF_ROLES = ROLES.SELF_ROLES
    TICKETS_CATEGORY_ID = TICKETS.TICKETS_CATEGORY_ID
    TICKET_DELETE_DELAY_SECONDS = TICKETS.TICKET_DELETE_DELAY_SECONDS
    WELCOME_GIF_URL = WELCOME.GIF_URL
    WELCOME_PANEL_BG_URL = WELCOME.PANEL_BG_URL
    WELCOME_DESCRIPTION = WELCOME.DESCRIPTION
    WELCOME_FOOTER = WELCOME.FOOTER
    DAILY_REWARD = ECONOMY.DAILY_REWARD
    DAILY_COOLDOWN_SEC = ECONOMY.DAILY_COOLDOWN_SEC
    HIGH_STAKE_THRESHOLD = ECONOMY.HIGH_STAKE_THRESHOLD

    @classmethod
    def validate(cls) -> None:
        if not cls.BOT.TOKEN:
            raise ValueError(
                'DISCORD_TOKEN не найден. Создай файл .env и добавь строку:\n'
                'DISCORD_TOKEN=твой_токен'
            )
