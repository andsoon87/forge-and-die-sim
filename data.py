"""Данные игры Forge & Die v2.0.

Числа соответствуют RULES.md. При изменении правил менять и здесь, и в RULES.md.
"""
from enum import IntEnum
# ============================================================
# КЛАССЫ (пока только Воин, уровни 1-7)
# ============================================================
# Уровень бойца = индекс в списке + 1. WARRIOR[0] — уровень 1, WARRIOR[6] — уровень 7.
# Поля: xp_cost, hp, at, df, ability
# ability — строка-описание (позже движок будет её обрабатывать)
# WARRIOR[level_index] — level_index 0..6 (уровни 1..7).

WARRIOR = [
    {"xp_cost": 0,   "hp": 14, "at": 1, "df": 3, "ability": "stoykost_1"},      # уровень 1
    {"xp_cost": 8,   "hp": 17, "at": 1, "df": 4, "ability": None},              # уровень 2
    {"xp_cost": 18,  "hp": 20, "at": 2, "df": 4, "ability": "stoykost_duha"},   # уровень 3
    {"xp_cost": 30,  "hp": 24, "at": 3, "df": 5, "ability": "stoykost_2"},      # уровень 4
    {"xp_cost": 46,  "hp": 28, "at": 4, "df": 6, "ability": None},              # уровень 5
    {"xp_cost": 72,  "hp": 33, "at": 5, "df": 7, "ability": None},              # уровень 6
    {"xp_cost": 147, "hp": 42, "at": 7, "df": 9, "ability": "stoykost_3"},      # уровень 7
]

CLASSES = {
    "warrior": WARRIOR,
    # "hunter", "mage", "priest" — добавим на следующих шагах
}

# ============================================================
# МОНСТРЫ (пока только Пул 1 — 6 монстров)
# ============================================================
# Поля: name, at, df, hp, xp, gd, special
# special — строка-описание (позже движок будет её обрабатывать)
#
# pool_index: 0 = Пул 1, 1 = Пул 2, 2 = Пул 3, 3 = Пул 4
# monster_index: 0 = первый монстр пула.
MONSTERS = [
    # Пул 1: Слабые (этаж 1–2)
    [
        {"name": "Гоблин-вор",       "at": 0, "df": 1, "hp": 5, "xp": 2, "gd": 2, "special": None},
        {"name": "Гоблин-лучник",    "at": 1, "df": 1, "hp": 4, "xp": 2, "gd": 2, "special": "initiative_3"},
        {"name": "Орк-новичок",      "at": 1, "df": 1, "hp": 7, "xp": 3, "gd": 3, "special": None},
        {"name": "Гоблин-шаман",     "at": 0, "df": 2, "hp": 6, "xp": 3, "gd": 3, "special": "heal_2"},
        {"name": "Орк-разведчик",    "at": 2, "df": 1, "hp": 6, "xp": 2, "gd": 2, "special": "flee_on_miss"},
        {"name": "Орк-дрессировщик", "at": 1, "df": 2, "hp": 4, "xp": 1, "gd": 1, "special": "rat_companion"},
    ],
    # Пул 2: Средние (этаж 2–3) — позже
    # [],
    # Пул 3: Сильные (этаж 3–4) — позже
    # [],
    # Пул 4: Элитные (этаж 4) — позже
    # [],
]

# ============================================================
# ОСОБЫЕ МОНСТРЫ (не входят в обычные пулы)
# ============================================================
# Используются в специфических ситуациях: финальные боссы, мимики из сокровищниц.
# Поле hp_per_fighter: True — hp умножается на число бойцов; False/отсутствует — нет.

SPECIAL_MONSTERS = [
    {"name": "Minotaur Guard", "at": 4, "df": 4, "hp": 15, "hp_per_fighter": True, "xp": 8,  "gd": 10, "special": "atk_1_random"},
    {"name": "Дракон",         "at": 7, "df": 8, "hp": 25, "hp_per_fighter": True, "xp": 20, "gd": 50, "special": "atk_2_breath"},
]

# ============================================================
# МИМИКИ (из сокровищниц, по этажам)
# ============================================================
# MIMICS[floor] — floor_index 0..3 (этажи 1..4)

MIMICS = [
    {"name": "Мимик (э1)", "at": 2, "df": 2, "hp": 8,  "xp": 3,  "gd": 3,  "special": None},  # этаж 1
    {"name": "Мимик (э2)", "at": 3, "df": 3, "hp": 12, "xp": 5,  "gd": 6,  "special": None},  # этаж 2
    {"name": "Мимик (э3)", "at": 5, "df": 5, "hp": 18, "xp": 8,  "gd": 12, "special": None},  # этаж 3
    {"name": "Мимик (э4)", "at": 7, "df": 7, "hp": 27, "xp": 12, "gd": 24, "special": None},  # этаж 4
]

# ============================================================
# Типы тайлов
# ============================================================
class TileType(IntEnum):
    """Типы тайлов. Числа — для компактной записи в JSON."""
    START = 0
    FORGE = 1
    MONSTER = 2
    TREASURE = 3
    EVENT = 4
    CAMP = 5
    TRADER = 6

# ============================================================
# ТАЙЛЫ (61 карта)
# ============================================================
# TILES[i] — i 0..60 (тайлы 00S..60E).
# Поля: type, monster_formula, in_deck.
# monster_formula: {"per": 1|2|4, "revival": bool} — только для type="monster"
#   per — на сколько разделить число бойцов (1:1 → per=1, 1:2 → per=2, 1:4 → per=4)
#   revival — True: при повторном входе d6: 1–2 монстр возрождается
TILES = [
    # 00–04
    {"type": TileType.START,    "monster_formula": None, "in_deck": False},  # 00S
    {"type": TileType.FORGE,    "monster_formula": None, "in_deck": True},   # 01F
    {"type": TileType.FORGE,    "monster_formula": None, "in_deck": True},   # 02F
    {"type": TileType.FORGE,    "monster_formula": None, "in_deck": True},   # 03F
    {"type": TileType.FORGE,    "monster_formula": None, "in_deck": True},   # 04F

    # 05–08: лагеря
    {"type": TileType.CAMP,     "monster_formula": None, "in_deck": True},   # 05A
    {"type": TileType.CAMP,     "monster_formula": None, "in_deck": True},   # 06A
    {"type": TileType.CAMP,     "monster_formula": None, "in_deck": True},   # 07A
    {"type": TileType.CAMP,     "monster_formula": None, "in_deck": True},   # 08A

    # 09–12: торговцы
    {"type": TileType.TRADER,   "monster_formula": None, "in_deck": True},   # 09T
    {"type": TileType.TRADER,   "monster_formula": None, "in_deck": True},   # 10T
    {"type": TileType.TRADER,   "monster_formula": None, "in_deck": True},   # 11T
    {"type": TileType.TRADER,   "monster_formula": None, "in_deck": True},   # 12T

    # 13–24: сокровищницы
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 13G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 14G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 15G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 16G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 17G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 18G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 19G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 20G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 21G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 22G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 23G
    {"type": TileType.TREASURE, "monster_formula": None, "in_deck": True},   # 24G

    # 25–48: монстры
    {"type": TileType.MONSTER, "monster_formula": {"per": 2, "revival": False}, "in_deck": True},  # 25M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": True},  "in_deck": True},  # 26M
    {"type": TileType.MONSTER, "monster_formula": {"per": 4, "revival": False}, "in_deck": True},  # 27M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": False}, "in_deck": True},  # 28M
    {"type": TileType.MONSTER, "monster_formula": {"per": 2, "revival": False}, "in_deck": True},  # 29M
    {"type": TileType.MONSTER, "monster_formula": {"per": 4, "revival": True},  "in_deck": True},  # 30M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": False}, "in_deck": True},  # 31M
    {"type": TileType.MONSTER, "monster_formula": {"per": 2, "revival": False}, "in_deck": True},  # 32M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": False}, "in_deck": True},  # 33M
    {"type": TileType.MONSTER, "monster_formula": {"per": 4, "revival": True},  "in_deck": True},  # 34M
    {"type": TileType.MONSTER, "monster_formula": {"per": 2, "revival": False}, "in_deck": True},  # 35M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": False}, "in_deck": True},  # 36M
    {"type": TileType.MONSTER, "monster_formula": {"per": 4, "revival": False}, "in_deck": True},  # 37M
    {"type": TileType.MONSTER, "monster_formula": {"per": 2, "revival": False}, "in_deck": True},  # 38M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": True},  "in_deck": True},  # 39M
    {"type": TileType.MONSTER, "monster_formula": {"per": 4, "revival": False}, "in_deck": True},  # 40M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": False}, "in_deck": True},  # 41M
    {"type": TileType.MONSTER, "monster_formula": {"per": 2, "revival": False}, "in_deck": True},  # 42M
    {"type": TileType.MONSTER, "monster_formula": {"per": 4, "revival": False}, "in_deck": True},  # 43M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": False}, "in_deck": True},  # 44M
    {"type": TileType.MONSTER, "monster_formula": {"per": 2, "revival": False}, "in_deck": True},  # 45M
    {"type": TileType.MONSTER, "monster_formula": {"per": 4, "revival": True},  "in_deck": True},  # 46M
    {"type": TileType.MONSTER, "monster_formula": {"per": 1, "revival": False}, "in_deck": True},  # 47M
    {"type": TileType.MONSTER, "monster_formula": {"per": 2, "revival": False}, "in_deck": True},  # 48M

    # 49–60: события
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 49E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 50E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 51E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 52E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 53E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 54E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 55E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 56E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 57E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 58E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 59E
    {"type": TileType.EVENT,    "monster_formula": None, "in_deck": True},   # 60E
]

# ============================================================
# СНАРЯЖЕНИЕ (пока пусто)
# ============================================================

EQUIPMENT = []

# ============================================================
# СОБЫТИЯ (пока пусто)
# ============================================================

EVENTS = []