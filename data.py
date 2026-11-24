"""Данные игры Forge & Die II.

Числа соответствуют RULES.md. При изменении правил менять и здесь, и в RULES.md.

СОГЛАШЕНИЕ: всё, что читается из этого модуля, ТОЛЬКО ЧИТАЕТСЯ.
Любое состояние (visited, убитые монстры, «сбежал») живёт в копиях тайлов
внутри floor_state, а не здесь.
"""
from enum import IntEnum

# ============================================================
# КЛАССЫ (пока только Воин, уровни 1-7)
# ============================================================
# Уровень бойца = индекс в списке + 1. WARRIOR[0] — уровень 1, WARRIOR[6] — уровень 7.
# Поля: xp_cost, hp, at, df, ability
# ability — строка-описание (позже движок будет её обрабатывать)

WARRIOR = [
    {"xp_cost": 0,   "bonus": {"hp": 14, "at": 1, "df": 3}, "ability": [("stk",1)]},          # уровень 1
    {"xp_cost": 8,   "bonus": {"hp": 17, "at": 1, "df": 4}, "ability": [("stk",1)]},          # уровень 2
    {"xp_cost": 18,  "bonus": {"hp": 20, "at": 2, "df": 4}, "ability": [("stk",1), ("std",)]},# уровень 3
    {"xp_cost": 30,  "bonus": {"hp": 24, "at": 3, "df": 5}, "ability": [("stk",2), ("std",)]},# уровень 4
    {"xp_cost": 46,  "bonus": {"hp": 28, "at": 4, "df": 6}, "ability": [("stk",2), ("std",)]},# уровень 5
    {"xp_cost": 72,  "bonus": {"hp": 33, "at": 5, "df": 7}, "ability": [("stk",2), ("std",)]},# уровень 6
    {"xp_cost": 147, "bonus": {"hp": 42, "at": 7, "df": 9}, "ability": [("stk",3), ("std",)]},# уровень 7
]
HUNTER = [
    {"xp_cost": 0,  "bonus": {"hp": 10, "at": 1,  "df": 1},                        "ability": []},         # уровень 1
    {"xp_cost": 4,  "bonus": {"hp": 11, "at": 2,  "df": 1, "init": 2},             "ability": []},         # уровень 2
    {"xp_cost": 10, "bonus": {"hp": 13, "at": 3,  "df": 2, "init": 2, "x_att": 2}, "ability": []},         # уровень 3
    {"xp_cost": 18, "bonus": {"hp": 15, "at": 5,  "df": 2, "init": 2, "x_att": 2}, "ability": [("chut",)]},# уровень 4
    {"xp_cost": 28, "bonus": {"hp": 17, "at": 6,  "df": 3, "init": 3, "x_att": 2}, "ability": [("chut",)]},# уровень 5
    {"xp_cost": 44, "bonus": {"hp": 19, "at": 7,  "df": 3, "init": 3, "x_att": 2}, "ability": [("chut",)]},# уровень 6
    {"xp_cost": 84, "bonus": {"hp": 24, "at": 10, "df": 4, "init": 3, "x_att": 2}, "ability": [("chut",)]},# уровень 7
]
MAGE = [
    {"xp_cost": 0,   "bonus": {"hp": 8,  "at": 2,  "df": 1}, "ability": [("sprk",1,1)]},           # уровень 1
    {"xp_cost": 6,   "bonus": {"hp": 9,  "at": 3,  "df": 1}, "ability": [("sprk",1,1), ("mg_v",)]},# уровень 2
    {"xp_cost": 14,  "bonus": {"hp": 11, "at": 5,  "df": 1}, "ability": [("sprk",2,1), ("mg_v",)]},# уровень 3
    {"xp_cost": 24,  "bonus": {"hp": 14, "at": 7,  "df": 2}, "ability": [("sprk",2,2), ("mg_v",)]},# уровень 4
    {"xp_cost": 36,  "bonus": {"hp": 16, "at": 9,  "df": 2}, "ability": [("sprk",2,2), ("mg_v",)]},# уровень 5
    {"xp_cost": 55,  "bonus": {"hp": 18, "at": 11, "df": 3}, "ability": [("sprk",3,2), ("mg_v",)]},# уровень 6
    {"xp_cost": 109, "bonus": {"hp": 23, "at": 14, "df": 4}, "ability": [("sprk",4,3), ("mg_v",)]},# уровень 7
]
PRIEST = [
    {"xp_cost": 0,   "bonus": {"hp": 12, "at": 0,  "df": 2}, "ability": [("heal",2,1)]},             # уровень 1
    {"xp_cost": 7,   "bonus": {"hp": 14, "at": 0,  "df": 3}, "ability": [("heal",2,1)]},             # уровень 2
    {"xp_cost": 16,  "bonus": {"hp": 16, "at": 1,  "df": 3}, "ability": [("heal",3,1)]},             # уровень 3
    {"xp_cost": 26,  "bonus": {"hp": 19, "at": 2,  "df": 4}, "ability": [("heal",3,2)]},             # уровень 4
    {"xp_cost": 38,  "bonus": {"hp": 22, "at": 3,  "df": 5}, "ability": [("heal",3,2), ("aura",6)]},# уровень 5
    {"xp_cost": 57,  "bonus": {"hp": 25, "at": 4,  "df": 6}, "ability": [("heal",4,2), ("aura",6)]},# уровень 6
    {"xp_cost": 114, "bonus": {"hp": 31, "at": 6,  "df": 8}, "ability": [("heal",6,3), ("aura",5)]},# уровень 7
]
CLASSES = {
    "warrior": WARRIOR,
    "hunter":  HUNTER,
    "mage":    MAGE,
    "priest":  PRIEST,
}
CLASS_NAMES = {
    "warrior": "Воин",
    "hunter":  "Охотник",
    "mage":    "Маг",
    "priest":  "Жрец",
}
# Стартовое снаряжение класса (код из EQUIPMENT). Выдаётся при создании
# бойца (старт игры и найм в лагере). См. RULES.md §2.1–2.4.
STARTING_EQUIPMENT = {
    "warrior": "UW01",  # Ржавый меч
    "hunter":  "US01",  # Кожаный доспех
    "mage":    "US03",  # Мантия ученика
    "priest":  "UA03",  # Святой символ
}
# id тайла → класс обитателя лагеря (05A..08A)
CAMP_CLASS = {5: "warrior", 6: "hunter", 7: "mage", 8: "priest"}

# ============================================================
# МОНСТРЫ (20 карт: 4 пула)
# ============================================================
# Поля: name, at, df, hp, xp, gd, special
# special — строка-описание (позже движок будет её обрабатывать)
#
# MONSTERS[pool_index][monster_index]
# pool_index: 0 = Пул 1, 1 = Пул 2, 2 = Пул 3, 3 = Пул 4
# monster_index: 0 = первый монстр пула.
MONSTERS = [
    # Пул 1: Слабые (этаж 1–2)
    [
        {"name": "Гоблин-вор",       "bonus": {"at": 0, "df": 1, "hp": 5},            "xp": 2, "gd": 2, "ability": []},
        {"name": "Гоблин-лучник",    "bonus": {"at": 1, "df": 1, "hp": 4, "init": 3}, "xp": 2, "gd": 2, "ability": []},
        {"name": "Орк-новичок",      "bonus": {"at": 1, "df": 1, "hp": 7},            "xp": 3, "gd": 3, "ability": []},
        {"name": "Гоблин-шаман",     "bonus": {"at": 0, "df": 2, "hp": 6},            "xp": 3, "gd": 3, "ability": [("heal",2,1)]},
        {"name": "Орк-разведчик",    "bonus": {"at": 2, "df": 1, "hp": 6},            "xp": 2, "gd": 2, "ability": [("flee",)]},
        {"name": "Орк-дрессировщик", "bonus": {"at": 1, "df": 2, "hp": 4},            "xp": 1, "gd": 1, "ability": [("rat",)]},
    ],
    # Пул 2: Средние (этаж 2–3)
    [
        {"name": "Орк-ветеран",     "bonus": {"at": 2, "df": 3, "hp": 11},                      "xp": 4, "gd": 5,  "ability": []},
        {"name": "Гоблин-берсерк",  "bonus": {"at": 4, "df": 1, "hp": 8, "x_att": 2, "dmg": 1}, "xp": 4, "gd": 4, "ability": []},
        {"name": "Орк-шаман",       "bonus": {"at": 1, "df": 4, "hp": 10},                      "xp": 5, "gd": 5,  "ability": [("smm",1,2)]},
        {"name": "Гоблин-ассасин",  "bonus": {"at": 3, "df": 2, "hp": 7},                       "xp": 4, "gd": 4,  "ability": [("ign_df",)]},
        {"name": "Демон-имп",       "bonus": {"at": 3, "df": 3, "hp": 9},                       "xp": 5, "gd": 5,  "ability": [("sprk_imm",)]},
        {"name": "Каменный голем",  "bonus": {"at": 1, "df": 5, "hp": 12},                      "xp": 6, "gd": 6,  "ability": [("fatk_imm",)]},
        {"name": "Гоблин-король",   "bonus": {"at": 2, "df": 4, "hp": 10},                      "xp": 5, "gd": 6,  "ability": [("gb_atk", 1)]},
    ],
    # Пул 3: Сильные (этаж 3–4)
    [
        {"name": "Демон-страж",     "bonus": {"at": 4, "df": 5, "hp": 15},             "xp": 7, "gd": 9,  "ability": [("sprk_imm",)]},
        {"name": "Орк-вожак клана", "bonus": {"at": 5, "df": 4, "hp": 16, "x_att": 2}, "xp": 7, "gd": 10, "ability": []},
        {"name": "Демон-палач",     "bonus": {"at": 6, "df": 3, "hp": 14, "dmg": 2},   "xp": 8, "gd": 10, "ability": [("sprk_imm",)]},
        {"name": "Демон-колдун",    "bonus": {"at": 4, "df": 6, "hp": 13},             "xp": 8, "gd": 11, "ability": [("infr",), ("sprk_imm",)]},
        {"name": "Гоблин-титан",    "bonus": {"at": 5, "df": 6, "hp": 18},             "xp": 9, "gd": 12, "ability": []},
    ],
    # Пул 4: Элитные (этаж 4)
    [
        {"name": "Демон-лорд", "bonus": {"at": 7, "df": 6, "hp": 20, "x_att": 2}, "xp": 10, "gd": 15, "ability": [("sprk_imm",)]},
        {"name": "Орк-бог",    "bonus": {"at": 9, "df": 8, "hp": 24, "x_att": 2}, "xp": 12, "gd": 18, "ability": []},
    ],
]

# ============================================================
# Формула колоды монстров по этажам
# ============================================================
# MONSTER_POOLS_BY_FLOOR[floor_index] — список pool_index, входящих в колоду этажа.
# floor_index 0..3 (этажи 1..4).
# Пул 1 (Слабые)  — выпадают на этажах 1–2
# Пул 2 (Средние) — выпадают на этажах 2–3
# Пул 3 (Сильные) — выпадают на этажах 3–4
# Пул 4 (Элитные) — выпадают на этаже 4
MONSTER_POOLS_BY_FLOOR = {
    0: [0],
    1: [0, 1],
    2: [1, 2],
    3: [2, 3],
}

# ============================================================
# ОСОБЫЕ МОНСТРЫ (не входят в обычные пулы)
# ============================================================
# Используются в специфических ситуациях: финальные боссы, мимики из сокровищниц.
# Поле hp_per_fighter: True — hp умножается на число бойцов; False/отсутствует — нет.

SPECIAL_MONSTERS = [
    {"name": "Minotaur Guard", "bonus": {"at": 4, "df": 4, "hp": 15}, "xp": 8,  "gd": 10,
     "ability": [("atk_rnd", 1), ("hp_x_n",)]},
    {"name": "Дракон",         "bonus": {"at": 7, "df": 8, "hp": 25, "x_att": 2}, "xp": 20, "gd": 50,
     "ability": [("breath",), ("hp_x_n",)]},
]

# ============================================================
# МИМИКИ (из сокровищниц, по этажам)
# ============================================================
# MIMICS[floor] — floor_index 0..3 (этажи 1..4)

MIMICS = [
    {"name": "Мимик (э1)", "bonus": {"at": 2, "df": 2, "hp": 8},  "xp": 3,  "gd": 3,  "ability": []},
    {"name": "Мимик (э2)", "bonus": {"at": 3, "df": 3, "hp": 12}, "xp": 5,  "gd": 6,  "ability": []},
    {"name": "Мимик (э3)", "bonus": {"at": 5, "df": 5, "hp": 18}, "xp": 8,  "gd": 12, "ability": []},
    {"name": "Мимик (э4)", "bonus": {"at": 7, "df": 7, "hp": 27}, "xp": 12, "gd": 24, "ability": []},
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

TILE_TYPE_NAMES = {
    TileType.START: "Старт",
    TileType.FORGE: "Кузница",
    TileType.MONSTER: "Монстр",
    TileType.TREASURE: "Сокровищница",
    TileType.EVENT: "Событие",
    TileType.CAMP: "Лагерь",
    TileType.TRADER: "Торговец",
}

# ============================================================
# ТАЙЛЫ (61 карта)
# ============================================================
# TILES[i] — i 0..60 (тайлы 00S..60E).
# Поля: type, name, monster_formula.
# monster_formula: {"per": 1|2|4, "revival": bool} — только для type="monster"
#   per — на сколько разделить число бойцов (1:1 → per=1, 1:2 → per=2, 1:4 → per=4)
#   revival — True: при каждом повторном входе d6: 1 - монстры возрождаются
TILES = [
    # 00–04
    {"type": TileType.START,    "name": "Start",           "monster_formula": None},  # 00S
    {"type": TileType.FORGE,    "name": "Deep Forge",      "monster_formula": None},  # 01F
    {"type": TileType.FORGE,    "name": "Rune Anvil",      "monster_formula": None},  # 02F
    {"type": TileType.FORGE,    "name": "Old Smelter",     "monster_formula": None},  # 03F
    {"type": TileType.FORGE,    "name": "Molten Pit",      "monster_formula": None},  # 04F

    # 05–08: лагеря
    {"type": TileType.CAMP,     "name": "Warrior's Rest",  "monster_formula": None},  # 05A
    {"type": TileType.CAMP,     "name": "Ranger's Camp",   "monster_formula": None},  # 06A
    {"type": TileType.CAMP,     "name": "Mage's Tower",    "monster_formula": None},  # 07A
    {"type": TileType.CAMP,     "name": "Priest's Shrine", "monster_formula": None},  # 08A

        # 09–12: торговцы
    {"type": TileType.TRADER,   "name": "Lost Trader",     "monster_formula": None},  # 09T
    {"type": TileType.TRADER,   "name": "Grey Market",     "monster_formula": None},  # 10T
    {"type": TileType.TRADER,   "name": "Peddler's Nook",  "monster_formula": None},  # 11T
    {"type": TileType.TRADER,   "name": "Old Barter",      "monster_formula": None},  # 12T

    # 13–24: сокровищницы
    {"type": TileType.TREASURE, "name": "Old Vault",      "monster_formula": None},  # 13G
    {"type": TileType.TREASURE, "name": "Hidden Cache",   "monster_formula": None},  # 14G
    {"type": TileType.TREASURE, "name": "Dusty Library",  "monster_formula": None},  # 15G
    {"type": TileType.TREASURE, "name": "Sealed Chest",   "monster_formula": None},  # 16G
    {"type": TileType.TREASURE, "name": "Coin Cellar",    "monster_formula": None},  # 17G
    {"type": TileType.TREASURE, "name": "Gem Pocket",     "monster_formula": None},  # 18G
    {"type": TileType.TREASURE, "name": "Gold Seam",      "monster_formula": None},  # 19G
    {"type": TileType.TREASURE, "name": "Lost Strongbox", "monster_formula": None},  # 20G
    {"type": TileType.TREASURE, "name": "Relic Room",     "monster_formula": None},  # 21G
    {"type": TileType.TREASURE, "name": "Buried Hoard",   "monster_formula": None},  # 22G
    {"type": TileType.TREASURE, "name": "Sunken Chest",   "monster_formula": None},  # 23G
    {"type": TileType.TREASURE, "name": "Vault Door",     "monster_formula": None},  # 24G

    # 25–48: монстры
    {"type": TileType.MONSTER, "name": "Raider Camp",     "monster_formula": {"per": 2, "revival": False}},  # 25M
    {"type": TileType.MONSTER, "name": "Orc Patrol",      "monster_formula": {"per": 1, "revival": True}},   # 26M
    {"type": TileType.MONSTER, "name": "Beast Den",       "monster_formula": {"per": 4, "revival": False}},  # 27M
    {"type": TileType.MONSTER, "name": "Goblin Nest",     "monster_formula": {"per": 1, "revival": False}},  # 28M
    {"type": TileType.MONSTER, "name": "Dark Kennel",     "monster_formula": {"per": 2, "revival": False}},  # 29M
    {"type": TileType.MONSTER, "name": "Bone Pit",        "monster_formula": {"per": 4, "revival": True}},   # 30M
    {"type": TileType.MONSTER, "name": "Spider Lair",     "monster_formula": {"per": 1, "revival": False}},  # 31M
    {"type": TileType.MONSTER, "name": "Wolf Run",        "monster_formula": {"per": 2, "revival": False}},  # 32M
    {"type": TileType.MONSTER, "name": "Slime Cave",      "monster_formula": {"per": 1, "revival": False}},  # 33M
    {"type": TileType.MONSTER, "name": "Bat Roost",       "monster_formula": {"per": 4, "revival": True}},   # 34M
    {"type": TileType.MONSTER, "name": "Troll Bridge",    "monster_formula": {"per": 2, "revival": False}},  # 35M
    {"type": TileType.MONSTER, "name": "Rat Tunnels",     "monster_formula": {"per": 1, "revival": False}},  # 36M
    {"type": TileType.MONSTER, "name": "Guard Post",      "monster_formula": {"per": 4, "revival": False}},  # 37M
    {"type": TileType.MONSTER, "name": "Ambush Spot",     "monster_formula": {"per": 2, "revival": False}},  # 38M
    {"type": TileType.MONSTER, "name": "Ogre Cave",       "monster_formula": {"per": 1, "revival": True}},   # 39M
    {"type": TileType.MONSTER, "name": "Cursed Hall",     "monster_formula": {"per": 4, "revival": False}},  # 40M
    {"type": TileType.MONSTER, "name": "Fire Pit",        "monster_formula": {"per": 1, "revival": False}},  # 41M
    {"type": TileType.MONSTER, "name": "Iron Cage",       "monster_formula": {"per": 2, "revival": False}},  # 42M
    {"type": TileType.MONSTER, "name": "Deep Warren",     "monster_formula": {"per": 4, "revival": False}},  # 43M
    {"type": TileType.MONSTER, "name": "Ruined Shrine",   "monster_formula": {"per": 1, "revival": False}},  # 44M
    {"type": TileType.MONSTER, "name": "Blood Altar",     "monster_formula": {"per": 2, "revival": False}},  # 45M
    {"type": TileType.MONSTER, "name": "Shadow Den",      "monster_formula": {"per": 4, "revival": True}},   # 46M
    {"type": TileType.MONSTER, "name": "Bone Yard",       "monster_formula": {"per": 1, "revival": False}},  # 47M
    {"type": TileType.MONSTER, "name": "Dragon Cult",     "monster_formula": {"per": 2, "revival": False}},  # 48M

    # 49–60: события
    {"type": TileType.EVENT,    "name": "Dark Passage",    "monster_formula": None},  # 49E
    {"type": TileType.EVENT,    "name": "Old Bridge",      "monster_formula": None},  # 50E
    {"type": TileType.EVENT,    "name": "Echoing Hall",    "monster_formula": None},  # 51E
    {"type": TileType.EVENT,    "name": "Forked Path",     "monster_formula": None},  # 52E
    {"type": TileType.EVENT,    "name": "Collapsed Arch",  "monster_formula": None},  # 53E
    {"type": TileType.EVENT,    "name": "Narrow Stair",    "monster_formula": None},  # 54E
    {"type": TileType.EVENT,    "name": "Misty Tunnel",    "monster_formula": None},  # 55E
    {"type": TileType.EVENT,    "name": "Broken Gate",     "monster_formula": None},  # 56E
    {"type": TileType.EVENT,    "name": "Ancient Road",    "monster_formula": None},  # 57E
    {"type": TileType.EVENT,    "name": "Shifting Walls",  "monster_formula": None},  # 58E
    {"type": TileType.EVENT,    "name": "Glowing Runes",   "monster_formula": None},  # 59E
    {"type": TileType.EVENT,    "name": "Whispering Dark", "monster_formula": None},  # 60E
]
# ============================================================
# Список действий
# ============================================================
class Action(IntEnum):
    SKIP = 0
    FORGE = 1
    FIGHT = 2
    FLEE = 3
    HIRE = 4
    EVENT = 5
    TREASURE = 6
    TRADE = 7

ACTION_NAMES = {
    Action.SKIP:    "Пропуск",
    Action.FORGE:   "Переход на этаж",
    Action.FIGHT:   "Бой",
    Action.FLEE:    "Побег",
    Action.HIRE:    "Найм",
    Action.EVENT:   "Событие",
    Action.TREASURE:"Сокровище",
    Action.TRADE:   "Торговля",
}   

# ============================================================
# ЛАГЕРЯ: таблицы бросков (RULES.md §5)
# ============================================================
# (б) Уровень обитателя: CAMP_LEVEL_TABLE[d6-1][floor_index]
#     строки -- d6 1..6, столбцы -- этажи 1..4 (floor_index 0..3).
CAMP_LEVEL_TABLE = [
    [1, 2, 3, 4],  # d6=1
    [1, 2, 3, 4],  # d6=2
    [1, 3, 4, 5],  # d6=3
    [2, 3, 4, 5],  # d6=4
    [2, 4, 5, 6],  # d6=5
    [2, 4, 6, 7],  # d6=6
]

# (в) Настрой обитателя: верхние границы диапазонов по числу бойцов.
#     enemy:   1..CAMP_ENEMY_MAX[n]
#     neutral: enemy_max+1..CAMP_NEUTRAL_MAX[n]
#     friend:  neutral_max+1..6
CAMP_ENEMY_MAX = {1: 1, 2: 2, 3: 3, 4: 4}
CAMP_NEUTRAL_MAX = {1: 3, 2: 4, 3: 5, 4: 6}

# ============================================================
# Таблицы распределений снаряжения и эликсиров в зависимости от этажа
# ============================================================
# Качество снаряжения в сокровищнице (RULES.md §6.2)
# EQUIPMENT_QUALITY_TABLE[d6-1][floor_index] -- качество ("U"/"R"/"V"/"L").
# Строки -- d6 1..6, столбцы -- этажи 1..4 (floor_index 0..3).
EQUIPMENT_QUALITY_TABLE = [
    ["U", "U", "U", "U"],  # d6=1
    ["U", "U", "U", "U"],  # d6=2
    ["U", "U", "U", "R"],  # d6=3
    ["U", "U", "R", "R"],  # d6=4
    ["U", "R", "R", "V"],  # d6=5
    ["U", "R", "V", "L"],  # d6=6
]
# Ассортимент эликсиров у торговца по этажу (RULES.md §3.6, §10.5).
# floor_index 0..3 (этажи 1..4): на 1-м — только обычные, на 4-м — все.
ELIXIR_QUALITY_BY_FLOOR = {
    0: ["U"],                # этаж 1
    1: ["U", "R"],           # этаж 2
    2: ["U", "R", "V"],      # этаж 3
    3: ["U", "R", "V", "L"], # этаж 4
}
# ============================================================
# Снаряжение
# ============================================================
# Формат записи:
#   {"code", "name", "class", "bonus", "price"}
#   code  -- единственный идентификатор (строка "UW01"), ссылка в состоянии/логах
#   class -- None (для всех) | "warrior" | "hunter" | "mage" | "priest"
#   bonus -- {"at": +N} | {"df": +N} | {"hp": +N} (в 0.5.0 только эти ключи)
#   price -- цена (для будущего торговца)
# Слот и качество разбираются из code при необходимости (parse_code, позже).
# В 0.5.0 -- только 4 стартовых предмета классов.

EQUIPMENT = [
    # --- обычные (U), §10.1 ---
    {"code": "UW01", "name": "Ржавый меч",               "class": None,     "bonus": {"at": 1}, "price": 2},
    {"code": "UW02", "name": "Короткий меч",             "class": None,     "bonus": {"at": 2}, "price": 4},
    {"code": "US01", "name": "Кожаный доспех",           "class": None,     "bonus": {"df": 1}, "price": 3},
    {"code": "US02", "name": "Кольчуга",                 "class": None,     "bonus": {"df": 2}, "price": 5},
    {"code": "US03", "name": "Мантия ученика",           "class": "mage",   "bonus": {"df": 1}, "price": 2},
    {"code": "UA01", "name": "Кольцо силы",              "class": None,     "bonus": {"hp": 2}, "price": 3},
    {"code": "UA02", "name": "Амулет удачи",             "class": None,     "bonus": {},        "price": 0},           # пропало: +1 к сокровищам
    {"code": "UA03", "name": "Святой символ",            "class": "priest", "bonus": {"df": 1}, "price": 2},

    # --- редкие (R), §10.2 ---
    {"code": "RW01", "name": "Боевой топор",             "class": None,     "bonus": {"at": 4, "df": -1},           "price": 5},
    {"code": "RW02", "name": "Копьё",                    "class": None,     "bonus": {"at": 1, "init": 1},          "price": 4},
    {"code": "RW03", "name": "Меч героя",                "class": "warrior","bonus": {"at": 5},                     "price": 8},
    {"code": "RW04", "name": "Составной лук",            "class": "hunter", "bonus": {"at": 4}, "price": 5},     # пропало: +1 к сокровищам, была цена 7
    {"code": "RS01", "name": "Щит",                      "class": None,     "bonus": {"df": 1, "hp": 1},            "price": 4},
    {"code": "RS02", "name": "Тяжёлый доспех",           "class": None,     "bonus": {"df": 3, "init": -1},         "price": 7},
    {"code": "RS03", "name": "Башенный щит",             "class": "warrior","bonus": {"df": 2, "hp": 2},            "price": 7},
    {"code": "RS04", "name": "Плащ следопыта",           "class": "hunter", "bonus": {"df": 1, "hp": 1, "init": 1}, "price": 6},
    {"code": "RS05", "name": "Святая броня",             "class": "priest", "bonus": {"df": 1, "hp": 1},            "price": 6},
    {"code": "RA01", "name": "Сапоги скорости",          "class": None,     "bonus": {"init": 1},                   "price": 4},
    {"code": "RA02", "name": "Сумка алхимика",           "class": None,     "bonus": {}, "price": 0},           # пропало: +1 к событиям

    # --- волшебные (V), §10.3 ---
    {"code": "VW01", "name": "Длинный лук",              "class": None,     "bonus": {"at": 1}, "price": 2},     # пропало: +1 к сокровищам, была цена 5
    {"code": "VW02", "name": "Кинжал",                   "class": None,     "bonus": {"at": 1}, "price": 2},     # пропало: первая атака игнорирует защиту, была цена 6
    {"code": "VW03", "name": "Посох пламени",            "class": "mage",   "bonus": {"at": 5}, "price": 8},
    {"code": "VW04", "name": "Булава света",             "class": "priest", "bonus": {"at": 6, "hp": 4}, "price": 8},
    {"code": "VS01", "name": "Плащ странника",           "class": None,     "bonus": {"df": 1}, "price": 3},     # пропало: +1 к событиям, была цена 4
    {"code": "VS02", "name": "Шлем",                     "class": None,     "bonus": {"df": 1}, "price": 3},     # пропало: иммунитет к первой атаке (раз за бой), была цена 5
    {"code": "VS03", "name": "Пояс силы",                "class": "warrior","bonus": {"at": 1, "hp": 1}, "price": 5},
    {"code": "VS04", "name": "Мантия архимага",          "class": "mage",   "bonus": {"df": 3, "hp": 2}, "price": 6},
    {"code": "VA01", "name": "Талисман защиты",          "class": None,     "bonus": {"df": 1}, "price": 3},
    {"code": "VA02", "name": "Медальон удачи",           "class": None,     "bonus": {}, "price": 0},           # пропало: +1 к сокровищам, +1 к событиям
    {"code": "VA03", "name": "Глаз ястреба",             "class": "hunter", "bonus": {"at": 3}, "price": 4},     # пропало: +1 к сокровищам, была цена 6

    # --- легендарные (L), §10.4 ---
    {"code": "LW01", "name": "Клинок зари",              "class": None,     "bonus": {"at": 6, "df": 1}, "price": 8},  # пропало: первая атака в бою игнорирует защиту, была цена 10
    {"code": "LW02", "name": "Молот грома",              "class": None,     "bonus": {"at": 7, "df": -1}, "price": 8}, # пропало: +2 урона при попадании, была цена 10
    {"code": "LS01", "name": "Броня предков",            "class": None,     "bonus": {"df": 4, "hp": 3}, "price": 8},  # пропало: иммунитет к первой атаке (раз за бой), была цена 10
    {"code": "LS02", "name": "Мифриловая кольчуга",      "class": None,   "bonus": {"df": 3, "hp": 2}, "price": 7},  # пропало: -1 к получаемому урону от огня, была цена 10
    {"code": "LA01", "name": "Сердце горы",              "class": None,     "bonus": {"hp": 4, "df": 1}, "price": 5},  # пропало: +2 к одному броску d6 в сокровищнице (раз за визит), была цена 10
    {"code": "LA02", "name": "Печать руны",              "class": None,     "bonus": {"at": 2, "df": 2}, "price": 6},  # пропало: +1 к золоту за бой, была цена 10
    {"code": "LA03", "name": "Кристалл маны",            "class": "mage",   "bonus": {"at": 3}, "price": 4},     # пропало: +1 использование «Искры», была цена 10
    {"code": "LA04", "name": "Символ веры",              "class": "priest", "bonus": {}, "price": 0},           # пропало: +1 использование «Молитвы»

    # --- эликсиры (E), §10.5 ---
    # Качество в code[0], слот E в code[1], номер типа в code[2:]:
    # 01 — лечение, 02 — скорость. Сортировка по номеру ~ по типу эффекта.
    # В колоды снаряжения НЕ попадают (см. ELIXIR_QUALITY_BY_FLOOR и
    # play_one_game): выдаются только торговцем.
    {"code": "UE01", "name": "Малый эликсир лечения",    "class": None, "bonus": {"hp": 3},  "price": 2},
    {"code": "RE01", "name": "Средний эликсир лечения",  "class": None, "bonus": {"hp": 6},  "price": 6},
    {"code": "VE01", "name": "Большой эликсир лечения",  "class": None, "bonus": {"hp": 10}, "price": 13},
    {"code": "LE01", "name": "Огромный эликсир лечения", "class": None, "bonus": {"hp": 20}, "price": 40},
    {"code": "RE02", "name": "Эликсир скорости",         "class": None, "bonus": {"init": 2},"price": 6},
]

# ============================================================
# СПОСОБНОСТИ (ability)
# ============================================================
# Способности -- то, что даёт выбор действия (атаковать / применить
# умение / использовать навык). Бонусы (bonus) -- числовые модификаторы
# (at/df/hp/init/x_att/dmg/...), живут в bonus у класса/монстра/предмета.
#
# Формат записи: "id": {"name", "params": [...], "rules": [...]}.
# params -- имена параметров, которые ability передаёт кортежем
# (id, *params). rules -- логика (как у событий), ПОКА ЗАГЛУШКА (6.3+).
# id короткие: stk, std, sprk, aura, chut, mg_v, flee, heal, smm, infr,
# ign_df, sprk_imm, fatk_imm, gb_atk, b_hit, hp_x_n, atk_rnd, breath, rat.

ABILITIES = {
    "stk":      {"name": "Стойкость",              "params": ["uses"],   "rules": []},
    "std":      {"name": "Стойкость духа",         "params": [],         "rules": []},
    "sprk":     {"name": "Искра",                  "params": ["dice", "uses"], "rules": []},
    "aura":     {"name": "Святая аура",            "params": ["threshold"], "rules": []},
    "chut":     {"name": "Чутьё",                  "params": [],         "rules": []},
    "mg_v":     {"name": "Волшебное зрение",       "params": [],         "rules": []},
    "flee":     {"name": "Сбегает при промахе",    "params": [],         "rules": []},
    "heal":     {"name": "Лечение",                "params": ["amount", "uses"], "rules": []},
    "smm":      {"name": "Призыв",                 "params": ["pool", "monster"], "rules": []},
    "infr":     {"name": "Инферно",                "params": [],         "rules": []},
    "ign_df":   {"name": "Игнор защиты (первая атака)", "params": [],    "rules": []},
    "sprk_imm": {"name": "Иммунитет к Искре",      "params": [],         "rules": []},
    "fatk_imm": {"name": "Иммунитет к первой атаке", "params": [],       "rules": []},
    "gb_atk":   {"name": "+ к атаке гоблинам",     "params": ["value"],  "rules": []},
    "hp_x_n":   {"name": "HP × число бойцов",      "params": [],         "rules": []},
    "atk_rnd":  {"name": "Атака по случайному",    "params": ["count"],  "rules": []},
    "breath":   {"name": "Пламенное дыхание",      "params": [],         "rules": []},
    "rat":      {"name": "Гигантская крыса",       "params": [],         "rules": []},
}

# ============================================================
# СОБЫТИЯ (20 карт)
# ============================================================
# Формат записи:
#   {"id", "name", "rules": [rule, ...]}
# rule:
#   {"select": sel, "condition": cond, "effects": {...}}
# sel:   {"all": True} | {"random": True} | {"max": field} | {"min": field}
# cond:  True | False
#        | {"<"|"<="|">"|">="|"=="|"!=": (left, right)}    # сравнение
#        | {"d6": (lo, hi)}                                # бросок d6 в [lo, hi]
#        | {"and": [expr, ...]}                            # все истинны
#        | {"or":  [expr, ...]}                            # хотя бы один
#        | {"not": expr}                                   # отрицание
# effect: {"gold": [..], "hp": [..], "xp": [..], "turns": int,
#          "monster": [(pool, index), ..], "guide": True, ...}
#   числа -- массивы из 4 (этажи 1..4), знак в числе.
#   "turns" -- длительный эффект (в floor_state["active_effects"]).
#   "monster" -- (pool, index) конкретный | (pool, None) случайный из пула |
#                (None, None) случайный из случайного пула.
#   "guide"   -- тянет тайл к правому свободному выходу.
# left/right/lo/hi/field: число | ид. бойца | массив из 4 (по этажам). 

EVENTS = [
    # --- позитивные ---
    # 1. Найденный клад: +золото
    {"id": 1, "name": "Найденный клад",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"gold": [3, 6, 12, 24]}},
     ]},

    # 2. Благословение храма: +HP
    {"id": 2, "name": "Благословение храма",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"hp": [3, 4, 5, 6]}},
     ]},

    # 3. Воодушевление: +XP
    {"id": 3, "name": "Воодушевление",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"xp": [2, 3, 4, 5]}},
     ]},

    # 4. Торговый караван: +1 карта снаряжения (заглушка 0.4.0)
    {"id": 4, "name": "Торговый караван",
     "rules": [
         {"select": {"random": True}, "condition": True,
          "effects": {"equipment": [1, 1, 1, 1]}},
     ]},

    # 5. Проводник: разведка ближайшего свободного выхода (особое)
    {"id": 5, "name": "Проводник",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"guide": True}},
     ]},

    # 6. Целебный источник: +HP и +золото
    {"id": 6, "name": "Целебный источник",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"hp": [2, 3, 4, 5], "gold": [1, 2, 4, 8]}},
     ]},

    # 7. Удачная сделка: продать 1 карту снаряжения (заглушка)
    {"id": 7, "name": "Удачная сделка",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"deals": [1, 2, 3, 4]}},
     ]},

    # --- негативные ---
    # 8. Засада разбойников: каждый платит золотом, если хватает; иначе -- HP
    {"id": 8, "name": "Засада разбойников",
     "rules": [
         {"select": {"all": True},
          "condition": {">=": ("gold", [3, 6, 12, 24])},
          "effects": {"gold": [-3, -6, -12, -24]}},
         {"select": {"all": True}, "condition": True,
          "effects": {"hp": [-1, -2, -4, -8]}},
     ]},

    # 9. Проклятие: -HP
    {"id": 9, "name": "Проклятие",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"hp": [-2, -3, -4, -5]}},
     ]},

    # 10. Налог гильдии: -золото
    {"id": 10, "name": "Налог гильдии",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"gold": [-4, -8, -16, -32]}},
     ]},

    # 11. Порча снаряжения: сбросить 1 карту снаряжения (заглушка)
    {"id": 11, "name": "Порча снаряжения",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"equipment": [-1, -1, -1, -1]}},
     ]},

    # 12. Ловушка: -HP и -золото
    {"id": 12, "name": "Ловушка",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"hp": [-1, -2, -3, -4], "gold": [-1, -2, -4, -8]}},
     ]},

    # 13. Болезнь: -HP всем в начале каждого из 3 ходов (over_time)
    {"id": 13, "name": "Болезнь",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"hp": [-1, -2, -3, -4], "turns": 3}},
     ]},

    # 14. Обвал в шахте: -золото и -HP
    {"id": 14, "name": "Обвал в шахте",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"gold": [-3, -6, -12, -24], "hp": [-1, -2, -3, -4]}},
     ]},

    # --- нейтральные ---
    # 15. Таинственный незнакомец: d6 1-3 -> +золото, 4-6 -> -золото
    {"id": 15, "name": "Таинственный незнакомец",
     "rules": [
         {"select": {"all": True}, "condition": {"d6": (1, 3)},
          "effects": {"gold": [2, 4, 8, 16]}},
         {"select": {"all": True}, "condition": True,
          "effects": {"gold": [-2, -4, -8, -16]}},
     ]},

    # 16. Развилка судьбы: выбор +XP или +HP -> теперь: d6 1-3 -> +XP, 4-6 -> +HP
    #     (выбор игроком убран; трактовка через условие d6)
    {"id": 16, "name": "Развилка судьбы",
     "rules": [
         {"select": {"all": True}, "condition": {"d6": (1, 3)},
          "effects": {"xp": [1, 2, 3, 4]}},
         {"select": {"all": True}, "condition": True,
          "effects": {"hp": [2, 3, 4, 5]}},
     ]},

    # 17. Испытание силы: боец с наибольшей AT бросает d6 >= AT -> -HP, иначе +золото
    {"id": 17, "name": "Испытание силы",
     "rules": [
         {"select": {"max": "at"}, "condition": {"d6": ("at", 6)},
          "effects": {"hp": [-2, -3, -4, -5]}},
         {"select": {"max": "at"}, "condition": True,
          "effects": {"gold": [2, 4, 8, 16]}},
     ]},

    # 18. Старый долг: d6 выбирает бойца; если золото >= порога -> -золото, иначе +золото
    {"id": 18, "name": "Старый долг",
     "rules": [
         {"select": {"random": True},
          "condition": {">=": ("gold", [5, 10, 20, 40])},
          "effects": {"gold": [-2, -4, -8, -16]}},
         {"select": {"random": True}, "condition": True,
          "effects": {"gold": [2, 4, 8, 16]}},
     ]},

    # 19. Случайная встреча: конкретный монстр по этажу (первый пул этажа)
    {"id": 19, "name": "Случайная встреча",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"monster": [(0, 0), (1, 0), (2, 0), (3, 0)]}},
     ]},

    # 20. Забытая карта: случайный монстр пула этажа
    {"id": 20, "name": "Забытая карта",
     "rules": [
         {"select": {"all": True}, "condition": True,
          "effects": {"monster": [(0, None), (1, None), (2, None), (3, None)]}},
     ]},
]