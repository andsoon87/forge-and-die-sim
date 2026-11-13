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
    {"xp_cost": 0,   "hp": 14, "at": 1, "df": 3, "ability": "stoykost_1"},      # уровень 1
    {"xp_cost": 8,   "hp": 17, "at": 1, "df": 4, "ability": None},              # уровень 2
    {"xp_cost": 18,  "hp": 20, "at": 2, "df": 4, "ability": "stoykost_duha"},   # уровень 3
    {"xp_cost": 30,  "hp": 24, "at": 3, "df": 5, "ability": "stoykost_2"},      # уровень 4
    {"xp_cost": 46,  "hp": 28, "at": 4, "df": 6, "ability": None},              # уровень 5
    {"xp_cost": 72,  "hp": 33, "at": 5, "df": 7, "ability": None},              # уровень 6
    {"xp_cost": 147, "hp": 42, "at": 7, "df": 9, "ability": "stoykost_3"},      # уровень 7
]
HUNTER = [
    {"xp_cost": 0,  "hp": 10, "at": 1,  "df": 1, "ability": None},
    {"xp_cost": 4,  "hp": 11, "at": 2,  "df": 1, "ability": "initiative_2"},
    {"xp_cost": 10, "hp": 13, "at": 3,  "df": 2, "ability": "double_shot"},
    {"xp_cost": 18, "hp": 15, "at": 5,  "df": 2, "ability": "chutye"},
    {"xp_cost": 28, "hp": 17, "at": 6,  "df": 3, "ability": "initiative_3"},
    {"xp_cost": 44, "hp": 19, "at": 7,  "df": 3, "ability": None},
    {"xp_cost": 84, "hp": 24, "at": 10, "df": 4, "ability": "triple_shot"},
]
MAGE = [
    {"xp_cost": 0,   "hp": 8,  "at": 2,  "df": 1, "ability": "spark_1d6_1"},
    {"xp_cost": 6,   "hp": 9,  "at": 3,  "df": 1, "ability": "magic_vision"},
    {"xp_cost": 14,  "hp": 11, "at": 5,  "df": 1, "ability": "spark_2d6_1"},
    {"xp_cost": 24,  "hp": 14, "at": 7,  "df": 2, "ability": "spark_2d6_2"},
    {"xp_cost": 36,  "hp": 16, "at": 9,  "df": 2, "ability": None},
    {"xp_cost": 55,  "hp": 18, "at": 11, "df": 3, "ability": "spark_3d6_2"},
    {"xp_cost": 109, "hp": 23, "at": 14, "df": 4, "ability": "spark_4d6_3"},
]
PRIEST = [
    {"xp_cost": 0,   "hp": 12, "at": 0, "df": 2, "ability": "prayer_2_1"},
    {"xp_cost": 7,   "hp": 14, "at": 0, "df": 3, "ability": None},
    {"xp_cost": 16,  "hp": 16, "at": 1, "df": 3, "ability": "prayer_3_1"},
    {"xp_cost": 26,  "hp": 19, "at": 2, "df": 4, "ability": "prayer_3_2"},
    {"xp_cost": 38,  "hp": 22, "at": 3, "df": 5, "ability": "aura_6"},
    {"xp_cost": 57,  "hp": 25, "at": 4, "df": 6, "ability": "prayer_4_2"},
    {"xp_cost": 114, "hp": 31, "at": 6, "df": 8, "ability": "prayer_6_3_aura_5"},
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
        {"name": "Гоблин-вор",       "at": 0, "df": 1, "hp": 5, "xp": 2, "gd": 2, "special": None},
        {"name": "Гоблин-лучник",    "at": 1, "df": 1, "hp": 4, "xp": 2, "gd": 2, "special": "initiative_3"},
        {"name": "Орк-новичок",      "at": 1, "df": 1, "hp": 7, "xp": 3, "gd": 3, "special": None},
        {"name": "Гоблин-шаман",     "at": 0, "df": 2, "hp": 6, "xp": 3, "gd": 3, "special": "heal_2"},
        {"name": "Орк-разведчик",    "at": 2, "df": 1, "hp": 6, "xp": 2, "gd": 2, "special": "flee_on_miss"},
        {"name": "Орк-дрессировщик", "at": 1, "df": 2, "hp": 4, "xp": 1, "gd": 1, "special": "rat_companion"},
    ],
    # Пул 2: Средние (этаж 2–3)
    [
        {"name": "Орк-ветеран",     "at": 2, "df": 3, "hp": 11, "xp": 4, "gd": 5,  "special": None},
        {"name": "Гоблин-берсерк",  "at": 4, "df": 1, "hp": 8,  "xp": 4, "gd": 4,  "special": "atk_2_bonus_dmg"},
        {"name": "Орк-шаман",       "at": 1, "df": 4, "hp": 10, "xp": 5, "gd": 5,  "special": "summon_1_2"},
        {"name": "Гоблин-ассасин",  "at": 3, "df": 2, "hp": 7,  "xp": 4, "gd": 4,  "special": "first_atk_ignore_df"},
        {"name": "Демон-имп",       "at": 3, "df": 3, "hp": 9,  "xp": 5, "gd": 5,  "special": "immune_spark"},
        {"name": "Каменный голем",  "at": 1, "df": 5, "hp": 12, "xp": 6, "gd": 6,  "special": "immune_first_atk"},
        {"name": "Гоблин-король",   "at": 2, "df": 4, "hp": 10, "xp": 5, "gd": 6,  "special": "goblins_atk_1"},
    ],
    # Пул 3: Сильные (этаж 3–4)
    [
        {"name": "Демон-страж",     "at": 4, "df": 5, "hp": 15, "xp": 7, "gd": 9,  "special": "immune_spark"},
        {"name": "Орк-вожак клана", "at": 5, "df": 4, "hp": 16, "xp": 7, "gd": 10, "special": "atk_2"},
        {"name": "Демон-палач",     "at": 6, "df": 3, "hp": 14, "xp": 8, "gd": 10, "special": "hit_bonus_2_immune_spark"},
        {"name": "Демон-колдун",    "at": 4, "df": 6, "hp": 13, "xp": 8, "gd": 11, "special": "inferno_immune_spark"},
        {"name": "Гоблин-титан",    "at": 5, "df": 6, "hp": 18, "xp": 9, "gd": 12, "special": None},
    ],
    # Пул 4: Элитные (этаж 4)
    [
        {"name": "Демон-лорд", "at": 7, "df": 6, "hp": 20, "xp": 10, "gd": 15, "special": "atk_2_immune_spark"},
        {"name": "Орк-бог",    "at": 9, "df": 8, "hp": 24, "xp": 12, "gd": 18, "special": "atk_2"},
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
    
ACTION_NAMES = {
    Action.SKIP:  "Пропуск",
    Action.FORGE: "Переход на этаж",
    Action.FIGHT: "Бой",
    Action.FLEE:  "Побег",
    Action.HIRE:  "Найм",
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
# Снаряжение (пока пусто)
# ============================================================

EQUIPMENT = []

# ============================================================
# СОБЫТИЯ (пока пусто)
# ============================================================

EVENTS = []